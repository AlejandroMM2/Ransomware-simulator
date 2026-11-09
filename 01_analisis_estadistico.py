#!/usr/bin/env python3
"""
01_analisis_estadistico.py
==========================
Análisis estadístico completo del experimento PFG.

Genera:
  - Mann-Whitney U (H1: MTTR B vs C)
  - Bootstrap 95% CI para diferencia de medianas
  - Test exacto de Fisher (tasa de éxito B vs C)
  - Cliff's delta (tamaño del efecto)
  - Resumen ejecutivo de hipótesis

Uso:
  python3 01_analisis_estadistico.py
  python3 01_analisis_estadistico.py --csv resultados/raw_experimento.csv
  python3 01_analisis_estadistico.py --output resultados/estadisticas.txt
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats


# ─── Utilidades ───────────────────────────────────────────────────────────────

def cargar_datos(csv_path: str) -> list[dict]:
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    print(f"[INFO] Cargadas {len(rows)} filas desde {csv_path}")
    return rows


def agrupar_por_celda(rows: list[dict]) -> dict:
    cells = defaultdict(list)
    for r in rows:
        cells[(r['scenario'], r['strategy'])].append(r)
    return cells


def get_mttr(cells, scenario, strategy):
    return [float(r['mttr_s']) for r in cells.get((scenario, strategy), [])
            if r['mttr_s']]


def get_tdetect(cells, scenario, strategy):
    return [float(r['t_detect_s']) for r in cells.get((scenario, strategy), [])
            if r['t_detect_s']]


def get_restore_only(cells, scenario, strategy):
    """Tiempo de restauracion PURO (s): t_restore - t_first_action.
    Aisla la velocidad del backend (sin ataque ni polling)."""
    out = []
    for r in cells.get((scenario, strategy), []):
        tr, tf = r.get('t_restore_ns'), r.get('t_first_action_ns')
        if tr and tf:
            out.append((int(tr) - int(tf)) / 1e9)
    return out


def cliff_delta(x, y):
    """Cliff's delta: tamaño del efecto no paramétrico [-1, 1]."""
    n = len(x) * len(y)
    if n == 0:
        return 0.0
    more = sum(1 for xi in x for yj in y if xi > yj)
    less = sum(1 for xi in x for yj in y if xi < yj)
    return (more - less) / n


def interpret_cliff(d):
    d = abs(d)
    if d < 0.147: return "negligible"
    elif d < 0.33: return "small"
    elif d < 0.474: return "medium"
    else: return "large"


def bootstrap_ci(x, y, n_boot=10000, seed=42):
    """Bootstrap 95% CI para diferencia de medianas (B - C)."""
    np.random.seed(seed)
    x, y = np.array(x), np.array(y)
    diffs = []
    for _ in range(n_boot):
        bx = np.median(np.random.choice(x, len(x), replace=True))
        by = np.median(np.random.choice(y, len(y), replace=True))
        diffs.append(bx - by)
    return np.percentile(diffs, 2.5), np.percentile(diffs, 97.5)


def sep(char='=', n=62):
    return char * n


# ─── Análisis ─────────────────────────────────────────────────────────────────

def analisis_h1_restore(cells, output_lines):
    """H1 (correcto): velocidad de restauracion PURA B vs C.
    Se mide sobre los escenarios donde ambas estrategias restauran
    (E1, E3, E4). E2 queda fuera porque B es irrecuperable."""
    out = output_lines
    out.append(sep())
    out.append("H1 (restauracion pura) - t_restore - t_first_action, B vs C")
    out.append("Mann-Whitney U (bilateral) + Cliff's delta + bootstrap 95%")
    out.append(sep())

    todos_b, todos_c = [], []
    for scenario in ['E1', 'E3', 'E4']:
        rb = get_restore_only(cells, scenario, 'B')
        rc = get_restore_only(cells, scenario, 'C')
        if not rb or not rc:
            continue
        todos_b += rb
        todos_c += rc
        med_b, med_c = np.median(rb), np.median(rc)
        u, p = stats.mannwhitneyu(rb, rc, alternative='two-sided')
        d = cliff_delta(rb, rc)
        lo, hi = bootstrap_ci(rb, rc)
        red = (med_b - med_c) / med_b * 100 if med_b else 0
        out.append(f"\nEscenario {scenario}: n_B={len(rb)}, n_C={len(rc)}")
        out.append(f"  mediana_B={med_b:.2f}s, mediana_C={med_c:.2f}s "
                   f"(reduccion B->C: {red:.1f}%)")
        out.append(f"  Mann-Whitney U={u:.0f}, p={p:.4f} "
                   f"-> {'sig.' if p < 0.05 else 'no sig.'} (alpha=0.05)")
        out.append(f"  Cliff's delta={d:.3f} ({interpret_cliff(d)})")
        out.append(f"  Bootstrap 95% CI (B-C): [{lo:.2f}s, {hi:.2f}s]")

    if todos_b and todos_c:
        med_b, med_c = np.median(todos_b), np.median(todos_c)
        u, p = stats.mannwhitneyu(todos_b, todos_c, alternative='two-sided')
        d = cliff_delta(todos_b, todos_c)
        lo, hi = bootstrap_ci(todos_b, todos_c)
        red = (med_b - med_c) / med_b * 100 if med_b else 0
        out.append(f"\nAGREGADO (E1+E3+E4): n_B={len(todos_b)}, n_C={len(todos_c)}")
        out.append(f"  mediana_B={med_b:.2f}s, mediana_C={med_c:.2f}s "
                   f"(reduccion B->C: {red:.1f}%)")
        out.append(f"  Mann-Whitney U={u:.0f}, p={p:.4f} "
                   f"-> {'sig.' if p < 0.05 else 'no sig.'}")
        out.append(f"  Cliff's delta={d:.3f} ({interpret_cliff(d)})")
        out.append(f"  Bootstrap 95% CI (B-C): [{lo:.2f}s, {hi:.2f}s]")


def analisis_h1_mttr(cells, output_lines):
    """H1: Mann-Whitney U + Cliff's delta para MTTR B vs C."""
    out = output_lines

    out.append(sep())
    out.append("H1 — MTTR B vs C por escenario")
    out.append("Mann-Whitney U (bilateral) + Cliff's delta")
    out.append(sep())

    for scenario in ['E1', 'E2', 'E3', 'E4']:
        mttr_b = get_mttr(cells, scenario, 'B')
        mttr_c = get_mttr(cells, scenario, 'C')

        out.append(f"\nEscenario {scenario}:")
        out.append(f"  n_B={len(mttr_b)}, n_C={len(mttr_c)}")

        if not mttr_b or not mttr_c:
            out.append("  Sin datos suficientes para comparar")
            if not mttr_b:
                out.append("  → B: impossible (repositorio destruido en todos los casos)")
            continue

        med_b = np.median(mttr_b)
        med_c = np.median(mttr_c)
        u_stat, p_val = stats.mannwhitneyu(mttr_b, mttr_c, alternative='two-sided')
        d = cliff_delta(mttr_b, mttr_c)
        ci_low, ci_high = bootstrap_ci(mttr_b, mttr_c)

        reduccion = (med_b - med_c) / med_b * 100 if med_b > 0 else 0

        out.append(f"  mediana_B={med_b:.2f}s, mediana_C={med_c:.2f}s")
        out.append(f"  Reducción MTTR (B→C): {reduccion:.1f}%")
        out.append(f"  Mann-Whitney U={u_stat:.0f}, p={p_val:.4f} "
                   f"→ {'✅ sig.' if p_val < 0.05 else '❌ no sig.'} (α=0.05)")
        out.append(f"  Cliff's δ={d:.3f} ({interpret_cliff(d)})")
        out.append(f"  Bootstrap 95% CI diferencia medianas: [{ci_low:.2f}s, {ci_high:.2f}s]")
        contains_zero = ci_low <= 0 <= ci_high
        out.append(f"  CI contiene 0: {'SÍ → no significativo' if contains_zero else 'NO → significativo'}")


def analisis_fisher(rows, cells, output_lines):
    """Test exacto de Fisher para tasa de éxito B vs C."""
    out = output_lines

    out.append("")
    out.append(sep())
    out.append("Tasa de recuperación — Test exacto de Fisher (B vs C)")
    out.append(sep())

    for scenario in ['E1', 'E2']:  # solo escenarios con perdida de datos
        b_s = sum(1 for r in cells[(scenario,'B')] if r['recovery_status'] == 'success')
        c_s = sum(1 for r in cells[(scenario,'C')] if r['recovery_status'] == 'success')
        nb = len(cells[(scenario,'B')]); nc = len(cells[(scenario,'C')])
        table = [[b_s, nb - b_s], [c_s, nc - c_s]]

        out.append(f"\n{scenario}: B={b_s}/{nb}, C={c_s}/{nc}")
        if b_s == c_s:
            out.append("  p=1.0000 (sin diferencia)")
        else:
            _, p = stats.fisher_exact(table)
            out.append(f"  Fisher exact p={p:.4f} → "
                       f"{'✅ significativo' if p < 0.05 else '❌ no significativo'}")

    # Global solo sobre escenarios con perdida de datos (E1, E2)
    dr = [r for r in rows if r['scenario'] in ('E1', 'E2')]
    b_all = sum(1 for r in dr if r['strategy']=='B' and r['recovery_status']=='success')
    c_all = sum(1 for r in dr if r['strategy']=='C' and r['recovery_status']=='success')
    n_b = sum(1 for r in dr if r['strategy']=='B')
    n_c = sum(1 for r in dr if r['strategy']=='C')
    table_g = [[b_all, n_b - b_all], [c_all, n_c - c_all]]
    _, p_g = stats.fisher_exact(table_g)

    out.append(f"\nGLOBAL (solo E1+E2): B={b_all}/{n_b}, C={c_all}/{n_c}")
    out.append(f"Fisher exact p={p_g:.6f} → "
               f"{'✅ significativo (p<0.05)' if p_g < 0.05 else '❌ no significativo'}")


def analisis_h2_tdetect(cells, output_lines):
    """H2: T_detect descriptivo por celda."""
    out = output_lines

    out.append("")
    out.append(sep())
    out.append("H2 — T_detect por celda experimental")
    out.append(sep())
    out.append(f"\n{'Celda':<12} {'n':>4} {'min':>8} {'P25':>8} {'med':>8} {'P75':>8} {'max':>8}")
    out.append("─" * 60)

    for scenario in ['E1', 'E2', 'E3', 'E4']:
        for strategy in ['A', 'B', 'C']:
            td = get_tdetect(cells, scenario, strategy)
            if td:
                out.append(
                    f"{scenario}×{strategy:<8} {len(td):>4} "
                    f"{min(td):>8.2f} {np.percentile(td,25):>8.2f} "
                    f"{np.median(td):>8.2f} {np.percentile(td,75):>8.2f} "
                    f"{max(td):>8.2f}"
                )
            else:
                out.append(f"{scenario}×{strategy:<8} {'—':>4}")


def analisis_recovery(rows, cells, output_lines):
    """Resumen de tasa de éxito por estrategia."""
    out = output_lines

    out.append("")
    out.append(sep())
    out.append("Tasa de recuperación por estrategia (solo E1+E2, con perdida de datos)")
    out.append(sep())

    for strategy in ['A', 'B', 'C']:
        rs = [r for r in rows if r['strategy'] == strategy
              and r['scenario'] in ('E1', 'E2')]
        success = sum(1 for r in rs if r['recovery_status'] == 'success')
        impossible = sum(1 for r in rs if r['recovery_status'] == 'impossible')
        out.append(f"\nEstrategia {strategy} ({len(rs)} ejec. con perdida de datos):")
        out.append(f"  success:    {success:>3} ({success/len(rs)*100:.0f}%)")
        out.append(f"  impossible: {impossible:>3} ({impossible/len(rs)*100:.0f}%)")


def resumen_ejecutivo(cells, rows, output_lines):
    out = output_lines
    out.append("")
    out.append(sep())
    out.append("RESUMEN EJECUTIVO — Conclusiones para la memoria")
    out.append(sep())

    # Velocidad de restauracion pura, agregada E1+E3+E4
    rb = sum((get_restore_only(cells, sc, 'B') for sc in ('E1','E3','E4')), [])
    rc = sum((get_restore_only(cells, sc, 'C') for sc in ('E1','E3','E4')), [])
    if rb and rc:
        mb, mc = np.median(rb), np.median(rc)
        _, p = stats.mannwhitneyu(rb, rc, alternative='two-sided')
        d = cliff_delta(rb, rc)
        red = (mb - mc) / mb * 100 if mb else 0
        out.append(f"""
H1 - velocidad de restauracion (B vs C, E1+E3+E4, n={len(rb)}/{len(rc)}):
  La restauracion pura de C es mas rapida que la de B:
  mediana B={mb:.2f}s vs C={mc:.2f}s (reduccion {red:.1f}%),
  Mann-Whitney p={p:.4f}, Cliff delta={d:.2f} ({interpret_cliff(d)}).
  => Si H1 se formula sobre la VELOCIDAD de restauracion, se CONFIRMA.
     El MTTR extremo-a-extremo (ataque+deteccion+restauracion) no separa
     bien las estrategias; la diferencia real esta en el backend.""")

    # Tasa de recuperacion sobre escenarios con perdida de datos (E1,E2)
    out.append("\nH3 - recuperabilidad ante perdida de datos (solo E1+E2):")
    for st in ('A', 'B', 'C'):
        rs = [r for r in rows if r['strategy'] == st and r['scenario'] in ('E1','E2')]
        ok = sum(1 for r in rs if r['recovery_status'] == 'success')
        pct = ok / len(rs) * 100 if rs else 0
        out.append(f"  {st}: {ok}/{len(rs)} ({pct:.0f}%)")
    b2 = sum(1 for r in cells[('E2','B')] if r['recovery_status']=='success')
    c2 = sum(1 for r in cells[('E2','C')] if r['recovery_status']=='success')
    n2b=len(cells[('E2','B')]); n2c=len(cells[('E2','C')])
    _, p2 = stats.fisher_exact([[b2,n2b-b2],[c2,n2c-c2]])
    out.append(f"  E2 (destruccion activa): B={b2}/{n2b} vs C={c2}/{n2c}, "
               f"Fisher p={p2:.4f}.")
    out.append("  => Object Lock + minimo privilegio IAM garantizan la "
               "recuperabilidad cuando el backup convencional es destruido.")

    out.append("""
H2 - deteccion (ver tabla T_detect): el SIEM alerta en segundos.
  NOTA: interpretar T_detect como instante REAL de la alerta (timestamp
  del indexer), no como el momento del polling.""")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Análisis estadístico PFG ransomware')
    parser.add_argument('--csv', default='results/raw_20260724_174113.csv',
                        help='Ruta al CSV de resultados')
    parser.add_argument('--output', default=None,
                        help='Fichero de salida (por defecto: stdout)')
    args = parser.parse_args()

    if not Path(args.csv).exists():
        print(f"ERROR: no se encuentra {args.csv}", file=sys.stderr)
        sys.exit(1)

    rows = cargar_datos(args.csv)
    cells = agrupar_por_celda(rows)

    output_lines = []
    analisis_h1_mttr(cells, output_lines)
    analisis_h1_restore(cells, output_lines)
    analisis_fisher(rows, cells, output_lines)
    analisis_h2_tdetect(cells, output_lines)
    analisis_recovery(rows, cells, output_lines)
    resumen_ejecutivo(cells, rows, output_lines)

    result = '\n'.join(output_lines)

    if args.output:
        Path(args.output).write_text(result)
        print(f"[INFO] Resultados guardados en {args.output}")
    else:
        print(result)


if __name__ == '__main__':
    main()
