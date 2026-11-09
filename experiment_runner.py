#!/usr/bin/env python3
"""
experiment_runner.py — Orquestador del diseño experimental del PFG

Diseño factorial:
  4 escenarios × 3 estrategias × 20 repeticiones = 240 ejecuciones

Por cada ejecución:
  1. reset_lab.sh <estrategia>      → estado limpio + backup
  2. Lanza escenario E1-E4          → T_launch
  3. Polling a Wazuh indexer        → T_detect (primera alerta del grupo)
  4. Ejecuta playbook A/B/C         → T_restore, recovery_status, integrity
  5. Escribe fila en raw.csv

Uso:
  python3 experiment_runner.py                     # 240 ejecuciones completas
  python3 experiment_runner.py --dry-run           # sin ejecutar, solo imprime plan
  python3 experiment_runner.py --scenario E1       # solo escenario E1
  python3 experiment_runner.py --strategy C        # solo estrategia C
  python3 experiment_runner.py --reps 3            # 3 repeticiones por celda
  python3 experiment_runner.py --resume run_045    # reanuda desde un run_id

Prerequisitos:
  - Laboratorio arrancado y calibrado
  - Volúmenes con datos de agentes activos
  - Wazuh indexer accesible en https://wazuh-indexer:9200
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import urllib.request
import ssl
import random
from datetime import datetime, timezone
from pathlib import Path

# ─── Configuración ────────────────────────────────────────────────────────────

SCENARIOS = ["E1", "E2", "E3", "E4"]
STRATEGIES = ["A", "B", "C"]
REPETITIONS = 20

# Comandos de escenario (ejecutados desde el host via docker exec)
SCENARIO_CMD = {
    "E1": "docker exec attacker /lab/simulators/scenarios/e1_local.sh",
    "E2": "docker exec attacker /lab/simulators/scenarios/e2_destroy.sh",
    "E3": "docker exec attacker /lab/simulators/scenarios/e3_lateral.sh",
    "E4": "docker exec attacker /lab/simulators/scenarios/e4_exfil.sh",
}

# Grupos de reglas Wazuh por escenario (para polling T_detect)
SCENARIO_GROUPS = {
    "E1": "e1_local",
    "E2": "e2_destroy",
    "E3": "e3_lateral",
    "E4": "e4_exfil",
}

# Tiempo máximo de espera para T_detect (segundos)
DETECT_TIMEOUT = {
    "E1": 180,
    "E2": 180,
    "E3": 90,
    "E4": 120,
}

# Timeout del ataque por escenario (segundos)
ATTACK_TIMEOUT = {
    "E1": 120,
    "E2": 180,
    "E3": 60,
    "E4": 600,
}

# Tiempo de espera entre ejecuciones (segundos)
COOLDOWN = 30

# Wazuh indexer
INDEXER_URL = "https://localhost:9200"
INDEXER_USER = "admin"
INDEXER_PASS = "admin"

# Rutas
BASE_DIR = Path(__file__).parent
RESULTS_DIR = BASE_DIR / "results"
SCRIPTS_DIR = BASE_DIR / "scripts"
LOG_DIR = Path("/var/log/lab")

# ─── Utilidades ───────────────────────────────────────────────────────────────

def ts_ns() -> int:
    """Timestamp en nanosegundos."""
    return time.time_ns()


def ts_utc() -> str:
    """Timestamp ISO 8601 UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def run(cmd: str, timeout: int = 300) -> tuple[int, str, str]:
    """Ejecuta un comando shell y devuelve (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=timeout
    )
    return result.returncode, result.stdout, result.stderr


def log(msg: str, level: str = "INFO"):
    """Log con timestamp."""
    print(f"[{ts_utc()}] [{level}] {msg}", flush=True)


def log_json(event: dict):
    """Escribe evento JSON al log del laboratorio."""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / "experiment_runner.jsonl", "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass


# ─── Wazuh Indexer ────────────────────────────────────────────────────────────

def query_indexer(group: str, since_ts_ns: int = 0) -> int:
    """
    Consulta el número total de alertas del grupo en el indexer.
    Usa docker exec para acceder desde la red Docker interna.
    """
    cmd = (
        f"docker exec wazuh-manager curl -sk -u {INDEXER_USER}:{INDEXER_PASS} "
        f"https://wazuh-indexer:9200/wazuh-alerts-*/_count"
        f"?q=rule.groups:{group}"
    )
    try:
        rc, stdout, stderr = run(cmd, timeout=15)
        if rc == 0 and stdout.strip():
            result = json.loads(stdout)
            return result.get("count", 0)
        return 0
    except Exception as e:
        log(f"Error consultando indexer: {e}", "WARN")
        return 0


def query_first_alert_ts(group: str, t_launch_ns: int) -> float | None:
    """Epoch (s) de la PRIMERA alerta del grupo con timestamp >= t_launch.
    None si aun no hay ninguna. Usa el instante REAL de la alerta, no el
    momento en que el polling la descubre."""
    gte_ms = t_launch_ns // 1_000_000
    body = json.dumps({
        "size": 1,
        "sort": [{"timestamp": {"order": "asc"}}],
        "query": {"bool": {"filter": [
            {"term": {"rule.groups": group}},
            {"range": {"timestamp": {"gte": gte_ms, "format": "epoch_millis"}}},
        ]}},
    })
    cmd = (
        f"docker exec wazuh-manager curl -sk -u {INDEXER_USER}:{INDEXER_PASS} "
        f"-H 'Content-Type: application/json' "
        f"-X POST 'https://wazuh-indexer:9200/wazuh-alerts-*/_search' "
        f"-d '{body}'"
    )
    try:
        rc, out, err = run(cmd, timeout=15)
        if rc != 0 or not out.strip():
            return None
        hits = json.loads(out).get("hits", {}).get("hits", [])
        if not hits:
            return None
        ts = hits[0]["_source"]["timestamp"]   # 2026-07-24T15:41:42.600+0000
        ts = ts.replace("Z", "+0000")
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()
    except Exception as e:
        log(f"Error consultando timestamp de alerta: {e}", "WARN")
        return None


def wait_for_detection(group: str, t_launch_ns: int, timeout: int) -> tuple[int | None, int]:
    """Sondea cada 5 s si ya existe una alerta del grupo posterior al ataque.
    Devuelve (t_detect_ns, 1) con el timestamp REAL de la alerta, o (None, 0).
    El filtro timestamp>=t_launch excluye por si solo los eventos del reset."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        alert_epoch = query_first_alert_ts(group, t_launch_ns)
        if alert_epoch is not None:
            return int(alert_epoch * 1e9), 1
        time.sleep(5)
    return None, 0



def wait_until_quiescent(group: str, stable_s: int = 15, max_wait: int = 180):
    """Bloquea hasta que el conteo de alertas del grupo no cambie durante
    stable_s segundos seguidos (o hasta max_wait). Garantiza que los eventos
    FIM del reset se han procesado antes de lanzar el ataque, con el MISMO
    criterio para A, B y C (sustituye la antigua espera fija asimetrica)."""
    deadline = time.time() + max_wait
    last = query_indexer(group)
    stable_since = time.time()
    while time.time() < deadline:
        time.sleep(5)
        now = query_indexer(group)
        if now != last:
            last = now
            stable_since = time.time()
        elif time.time() - stable_since >= stable_s:
            return


# ─── Fases del experimento ────────────────────────────────────────────────────

def phase_reset(strategy: str) -> bool:
    """Fase 1: Reset del laboratorio y creación de backup según estrategia."""
    log(f"Reset laboratorio → estrategia {strategy}")
    script = SCRIPTS_DIR / "reset_lab.sh"
    rc, stdout, stderr = run(f"bash {script} {strategy}", timeout=600)
    if rc != 0:
        log(f"reset_lab.sh falló (rc={rc}): {stderr[:200]}", "ERROR")
        return False
    log(f"Reset OK → estrategia {strategy}")
    return True


def phase_attack(scenario: str) -> tuple[int, int]:
    """
    Fase 2: Lanza el escenario de ataque.
    Retorna (T_launch_ns, T_attack_end_ns).
    """
    log(f"Lanzando escenario {scenario}")
    t_launch = ts_ns()
    cmd = SCENARIO_CMD[scenario]
    rc, stdout, stderr = run(cmd, timeout=ATTACK_TIMEOUT.get(scenario, 300))
    t_end = ts_ns()
    log(f"Escenario {scenario} terminó (rc={rc})")
    return t_launch, t_end


def phase_detect(scenario: str, t_launch: int, baseline: int = 0) -> tuple[int | None, int]:
    """
    Fase 3: Espera la primera alerta en Wazuh.
    baseline = conteo tomado ANTES del ataque en run_experiment.
    Retorna (T_detect_ns, alert_count_nuevas).
    """
    group = SCENARIO_GROUPS[scenario]
    timeout = DETECT_TIMEOUT[scenario]
    log(f"Esperando detección (grupo={group}, baseline={baseline}, timeout={timeout}s)")
    t_detect, count = wait_for_detection(group, t_launch, timeout)
    if t_detect:
        elapsed = (t_detect - t_launch) / 1e9
        log(f"Detección en {elapsed:.1f}s ({count} alertas nuevas)")
    else:
        log(f"Sin detección en {timeout}s", "WARN")
    return t_detect, count


def phase_recover(strategy: str, run_id: str) -> dict:
    """
    Fase 4: Ejecuta el playbook de recuperación.
    Retorna el resultado parseado del JSON final del playbook.
    """
    log(f"Ejecutando playbook {strategy}")
    t_first_action = ts_ns()

    playbook = SCRIPTS_DIR / "playbooks" / f"playbook_{strategy.lower()}.sh"
    rc, stdout, stderr = run(f"bash {playbook} {run_id}", timeout=600)

    # Busca la línea JSON con "event":"result"
    result_line = None
    for line in stdout.splitlines():
        try:
            data = json.loads(line)
            if data.get("event") == "result":
                result_line = data
                break
        except json.JSONDecodeError:
            continue

    if result_line:
        log(f"Playbook {strategy}: {result_line.get('recovery_status')} "
            f"({result_line.get('restored_files', 0)} ficheros, "
            f"integrity={result_line.get('integrity_match')})")
        return result_line
    else:
        log(f"Playbook {strategy} no devolvió resultado JSON", "WARN")
        return {
            "recovery_status": "error",
            "t_restore_ns": None,
            "restored_files": 0,
            "integrity_match": False,
            "t_first_action_ns": t_first_action,
        }


# ─── CSV ──────────────────────────────────────────────────────────────────────

FIELDNAMES = [
    "run_id",
    "timestamp_utc",
    "scenario",
    "strategy",
    "repetition",
    "t_launch_ns",
    "t_attack_end_ns",
    "t_detect_ns",
    "t_detect_s",           # T_detect en segundos (para análisis)
    "t_first_action_ns",
    "t_restore_ns",
    "t_restore_s",          # T_restore en segundos (para análisis)
    "mttr_s",               # T_restore - T_launch en segundos
    "alert_count",
    "recovery_status",      # success | partial | impossible | error | skipped
    "restored_files",
    "integrity_match",
    "notes",
]


def write_csv_row(csv_path: Path, row: dict):
    """Escribe una fila en el raw.csv."""
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def build_row(
    run_id: str,
    scenario: str,
    strategy: str,
    rep: int,
    t_launch: int,
    t_attack_end: int,
    t_detect: int | None,
    alert_count: int,
    playbook_result: dict,
    notes: str = "",
) -> dict:
    """Construye la fila del raw.csv."""
    t_first_action = playbook_result.get("t_first_action_ns")
    t_restore = playbook_result.get("t_restore_ns")

    t_detect_s = (t_detect - t_launch) / 1e9 if t_detect else None
    t_restore_s = (t_restore - t_launch) / 1e9 if t_restore else None
    mttr_s = (t_restore - t_launch) / 1e9 if t_restore else None

    return {
        "run_id": run_id,
        "timestamp_utc": ts_utc(),
        "scenario": scenario,
        "strategy": strategy,
        "repetition": rep,
        "t_launch_ns": t_launch,
        "t_attack_end_ns": t_attack_end,
        "t_detect_ns": t_detect if t_detect else "",
        "t_detect_s": f"{t_detect_s:.3f}" if t_detect_s else "",
        "t_first_action_ns": t_first_action if t_first_action else "",
        "t_restore_ns": t_restore if t_restore else "",
        "t_restore_s": f"{t_restore_s:.3f}" if t_restore_s else "",
        "mttr_s": f"{mttr_s:.3f}" if mttr_s else "",
        "alert_count": alert_count,
        "recovery_status": playbook_result.get("recovery_status", "error"),
        "restored_files": playbook_result.get("restored_files", 0),
        "integrity_match": playbook_result.get("integrity_match", False),
        "notes": notes,
    }


# ─── Runner principal ─────────────────────────────────────────────────────────

def build_execution_plan(
    scenarios: list[str],
    strategies: list[str],
    reps: int,
    resume_from: str | None = None,
    seed: int = 42,
) -> list[tuple]:
    """Plan en orden ALEATORIO con semilla fija (42) para que la estrategia
    no quede confundida con el momento de ejecucion. Reproducible: la misma
    semilla da siempre el mismo orden."""
    combos = [
        (scenario, strategy, rep)
        for strategy in strategies
        for scenario in scenarios
        for rep in range(1, reps + 1)
    ]
    random.Random(seed).shuffle(combos)
    plan = [
        (f"run_{i:03d}", sc, st, rep)
        for i, (sc, st, rep) in enumerate(combos, start=1)
    ]

    if resume_from:
        try:
            resume_idx = next(i for i, (rid, *_) in enumerate(plan) if rid == resume_from)
            log(f"Reanudando desde {resume_from} (indice {resume_idx})")
            plan = plan[resume_idx:]
        except StopIteration:
            log(f"run_id {resume_from} no encontrado en el plan", "ERROR")
            sys.exit(1)

    return plan


def run_experiment(args):
    """Bucle principal del experimento."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Fichero de resultados con timestamp del inicio
    session_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = RESULTS_DIR / f"raw_{session_ts}.csv"

    log(f"Iniciando experimento — {len(args.scenarios)} escenarios × "
        f"{len(args.strategies)} estrategias × {args.reps} repeticiones")
    log(f"Plan: {len(args.scenarios) * len(args.strategies) * args.reps} ejecuciones")
    log(f"Resultados: {csv_path}")

    plan = build_execution_plan(
        args.scenarios, args.strategies, args.reps, args.resume
    )

    if args.dry_run:
        log("=== DRY RUN — plan de ejecución ===")
        for run_id, scenario, strategy, rep in plan:
            print(f"  {run_id}: {scenario} × {strategy} × rep{rep}")
        return

    total = len(plan)
    completed = 0
    failed = 0

    for run_id, scenario, strategy, rep in plan:
        log(f"{'─'*60}")
        log(f"{run_id} — {scenario} × estrategia {strategy} × rep {rep}/{args.reps} "
            f"[{completed+1}/{total}]")

        event = {
            "ts": ts_ns(),
            "run_id": run_id,
            "scenario": scenario,
            "strategy": strategy,
            "rep": rep,
            "event": "start",
        }
        log_json(event)

        notes = []
        success = True

        # ── Fase 1: Reset ──────────────────────────────────────────────
        if not phase_reset(strategy):
            notes.append("reset_failed")
            success = False

        # ── Drenar el ruido FIM del reset antes de lanzar (igual A/B/C) ──
        group = SCENARIO_GROUPS[scenario]
        log("Esperando a que se drene el FIM del reset (mismo criterio A/B/C)...")
        wait_until_quiescent(group, stable_s=15, max_wait=180)

        baseline_count = query_indexer(group)
        log(f"Baseline pre-ataque: {baseline_count} alertas en grupo {group}")

        # ── Fase 2: Ataque ─────────────────────────────────────────────
        t_launch = t_attack_end = ts_ns()
        if success:
            try:
                t_launch, t_attack_end = phase_attack(scenario)
            except subprocess.TimeoutExpired:
                notes.append("attack_timeout")
                success = False
                log(f"Timeout en escenario {scenario}", "ERROR")

        # ── Fase 3: Detección ──────────────────────────────────────────
        t_detect = None
        alert_count = 0
        if success:
            t_detect, alert_count = phase_detect(scenario, t_launch, baseline_count)
            if not t_detect:
                notes.append("no_detection")
                log(f"Sin detección para {scenario} (esto es válido para análisis)", "WARN")

        # ── Fase 4: Recuperación ───────────────────────────────────────
        playbook_result = {
            "recovery_status": "skipped",
            "t_restore_ns": None,
            "restored_files": 0,
            "integrity_match": False,
            "t_first_action_ns": ts_ns(),
        }
        if success:
            try:
                playbook_result = phase_recover(strategy, run_id)
            except subprocess.TimeoutExpired:
                notes.append("playbook_timeout")
                log(f"Timeout en playbook {strategy}", "ERROR")

        # ── Escribir resultado ─────────────────────────────────────────
        row = build_row(
            run_id, scenario, strategy, rep,
            t_launch, t_attack_end,
            t_detect, alert_count,
            playbook_result,
            notes=";".join(notes),
        )
        write_csv_row(csv_path, row)

        log_json({**event, "ts": ts_ns(), "event": "end",
                  "recovery_status": row["recovery_status"],
                  "t_detect_s": row["t_detect_s"],
                  "mttr_s": row["mttr_s"]})

        status_icon = "✓" if row["recovery_status"] == "success" else "✗"
        log(f"{status_icon} {run_id} → detect={row['t_detect_s']}s "
            f"mttr={row['mttr_s']}s status={row['recovery_status']}")

        completed += 1
        if row["recovery_status"] == "error":
            failed += 1

        # Cooldown entre ejecuciones
        if completed < total:
            log(f"Cooldown {COOLDOWN}s")
            time.sleep(COOLDOWN)

    log(f"{'═'*60}")
    log(f"Experimento completado: {completed}/{total} ejecuciones "
        f"({failed} con error)")
    log(f"Resultados en: {csv_path}")

    # Resumen rápido por celda
    print_summary(csv_path)


def print_summary(csv_path: Path):
    """Imprime un resumen de los resultados por celda experimental."""
    if not csv_path.exists():
        return

    from collections import defaultdict
    cells = defaultdict(list)

    with open(csv_path) as f:
        for row in csv.DictReader(f):
            key = (row["scenario"], row["strategy"])
            cells[key].append(row)

    log("=== Resumen por celda (escenario × estrategia) ===")
    print(f"{'Celda':<12} {'N':>4} {'Éxito':>6} {'T_detect(s)':>12} {'MTTR(s)':>10}")
    print("─" * 50)

    for (scenario, strategy), rows in sorted(cells.items()):
        n = len(rows)
        success = sum(1 for r in rows if r["recovery_status"] == "success")

        detects = [float(r["t_detect_s"]) for r in rows if r["t_detect_s"]]
        mttrs = [float(r["mttr_s"]) for r in rows if r["mttr_s"]]

        det_med = f"{sorted(detects)[len(detects)//2]:.1f}" if detects else "N/A"
        mttr_med = f"{sorted(mttrs)[len(mttrs)//2]:.1f}" if mttrs else "N/A"

        print(f"{scenario}×{strategy:<8} {n:>4} {success:>6} {det_med:>12} {mttr_med:>10}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    global COOLDOWN
    parser = argparse.ArgumentParser(
        description="Orquestador del experimento PFG — 240 ejecuciones factorial"
    )
    parser.add_argument(
        "--scenario", "-s",
        choices=SCENARIOS + ["all"],
        default="all",
        help="Escenario a ejecutar (default: all)",
    )
    parser.add_argument(
        "--strategy", "-t",
        choices=STRATEGIES + ["all"],
        default="all",
        help="Estrategia a ejecutar (default: all)",
    )
    parser.add_argument(
        "--reps", "-r",
        type=int,
        default=REPETITIONS,
        help=f"Repeticiones por celda (default: {REPETITIONS})",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Solo imprime el plan sin ejecutar",
    )
    parser.add_argument(
        "--resume",
        metavar="RUN_ID",
        help="Reanuda desde un run_id específico (e.g. run_045)",
    )
    parser.add_argument(
        "--cooldown",
        type=int,
        default=COOLDOWN,
        help=f"Segundos entre ejecuciones (default: {COOLDOWN})",
    )

    args = parser.parse_args()

    # Expandir 'all'
    args.scenarios = SCENARIOS if args.scenario == "all" else [args.scenario]
    args.strategies = STRATEGIES if args.strategy == "all" else [args.strategy]


    return args


if __name__ == "__main__":
    args = parse_args()
    run_experiment(args)
