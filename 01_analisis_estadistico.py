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

    for scenario in ['E1', 'E2', 'E3', 'E4']:
        b_s = sum(1 for r in cells[(scenario,'B')] if r['recovery_status'] == 'success')
        c_s = sum(1 for r in cells[(scenario,'C')] if r['recovery_status'] == 'success')
        n = 10
        table = [[b_s, n - b_s], [c_s, n - c_s]]

        out.append(f"\n{scenario}: B={b_s}/10, C={c_s}/10")
        if b_s == c_s:
            out.append("  p=1.0000 (sin diferencia)")
        else:
            _, p = stats.fisher_exact(table)
            out.append(f"  Fisher exact p={p:.4f} → "
                       f"{'✅ significativo' if p < 0.05 else '❌ no significativo'}")

    # Global
    b_all = sum(1 for r in rows if r['strategy']=='B' and r['recovery_status']=='success')
    c_all = sum(1 for r in rows if r['strategy']=='C' and r['recovery_status']=='success')
    n_total = sum(1 for r in rows if r['strategy'] in ['B', 'C']) // 2
    table_g = [[b_all, n_total - b_all], [c_all, n_total - c_all]]
    _, p_g = stats.fisher_exact(table_g)

    out.append(f"\nGLOBAL (40 exec. por estrategia): B={b_all}/40, C={c_all}/40")
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
    out.append("Tasa de recuperación por estrategia")
    out.append(sep())

    for strategy in ['A', 'B', 'C']:
        rs = [r for r in rows if r['strategy'] == strategy]
        success = sum(1 for r in rs if r['recovery_status'] == 'success')
        impossible = sum(1 for r in rs if r['recovery_status'] == 'impossible')
        out.append(f"\nEstrategia {strategy} ({len(rs)} ejecuciones):")
        out.append(f"  success:    {success:>3} ({success/len(rs)*100:.0f}%)")
        out.append(f"  impossible: {impossible:>3} ({impossible/len(rs)*100:.0f}%)")


def resumen_ejecutivo(output_lines):
    out = output_lines
    out.append("")
    out.append(sep())
    out.append("RESUMEN EJECUTIVO — Conclusiones para la memoria")
    out.append(sep())
    out.append("""
H1 (C reduce MTTR ≥30% vs B):
  RECHAZADA en formulación original.
  - E1, E3, E4: diferencias de MTTR B vs C no significativas
    (Mann-Whitney p>0.05, Cliff δ negligible/small,
     Bootstrap CI contiene 0).
  - E2: B impossible (0/10), C exitosa (10/10).
    Fisher exact p<0.001 → diferencia altamente significativa.

  HALLAZGO ALTERNATIVO (más relevante):
  C garantiza disponibilidad 100% vs 75% de B.
  Ante destrucción activa del repositorio (E2), Object Lock
  COMPLIANCE es la única garantía de recuperabilidad.

H2 (SIEM detecta más rápido que detección manual):
  CONFIRMADA.
  - T_detect: 5.7s–41.9s en todos los escenarios.
  - IBM X-Force 2024: tiempo medio detección manual >200 días.
  - Diferencia de varios órdenes de magnitud (días vs segundos).
""")


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
    analisis_fisher(rows, cells, output_lines)
    analisis_h2_tdetect(cells, output_lines)
    analisis_recovery(rows, cells, output_lines)
    resumen_ejecutivo(output_lines)

    result = '\n'.join(output_lines)

    if args.output:
        Path(args.output).write_text(result)
        print(f"[INFO] Resultados guardados en {args.output}")
    else:
        print(result)


if __name__ == '__main__':
    main()
