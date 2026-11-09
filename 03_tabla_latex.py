#!/usr/bin/env python3
"""
03_tabla_latex.py
=================
Genera la tabla LaTeX de resultados y un CSV resumido por celda.

Salidas:
  tabla_resultados.tex   — tabla LaTeX lista para incluir en la memoria
  resumen_celdas.csv     — CSV con estadísticos descriptivos por celda

Uso:
  python3 03_tabla_latex.py
  python3 03_tabla_latex.py --csv resultados/raw_experimento.csv
  python3 03_tabla_latex.py --outdir resultados/
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np


def cargar(csv_path):
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    cells = defaultdict(list)
    for r in rows:
        cells[(r['scenario'], r['strategy'])].append(r)
    return rows, cells


def generar_latex(cells, output_path):
    lines = []
    lines.append(r"% Tabla generada automáticamente por 03_tabla_latex.py")
    lines.append(r"% Incluir en la memoria con: \input{tabla_resultados.tex}")
    lines.append(r"")
    lines.append(r"\begin{table}[htbp]")
    lines.append(r"\centering")
    lines.append(r"\caption{Resultados experimentales por celda. "
                 r"T\_detect y MTTR expresados como mediana (s). "
                 r"N=10 repeticiones por celda.}")
    lines.append(r"\label{tab:resultados_experimento}")
    lines.append(r"\begin{tabular}{llS[table-format=2.1]S[table-format=3.1]cc}")
    lines.append(r"\toprule")
    lines.append(r"Escenario & Estrategia & {T\_detect med. (s)} & "
                 r"{MTTR med. (s)} & N éxito & Status \\")
    lines.append(r"\midrule")

    scenario_names = {
        'E1': 'E1 — Cifrado local',
        'E2': 'E2 — Destrucción copias',
        'E3': 'E3 — Mov. lateral',
        'E4': 'E4 — Exfiltración',
    }
    strategy_names = {
        'A': 'A (sin backup)',
        'B': 'B (Restic+SFTP)',
        'C': 'C (MinIO ObjLock)',
    }

    for si, scenario in enumerate(['E1', 'E2', 'E3', 'E4']):
        if si > 0:
            lines.append(r"\midrule")
        for strategy in ['A', 'B', 'C']:
            rs = cells.get((scenario, strategy), [])
            td = [float(r['t_detect_s']) for r in rs if r['t_detect_s']]
            mt = [float(r['mttr_s']) for r in rs if r['mttr_s']]
            success = sum(1 for r in rs if r['recovery_status'] == 'success')
            statuses = set(r['recovery_status'] for r in rs)

            td_str = f"{np.median(td):.1f}" if td else r"\textemdash"
            mt_str = f"{np.median(mt):.1f}" if mt else r"\textemdash"

            # Resaltar E2×C como el resultado clave
            if scenario == 'E2' and strategy == 'C':
                row_prefix = r"\rowcolor{green!15}"
                lines.append(row_prefix)

            if scenario == 'E2' and strategy == 'B':
                row_prefix = r"\rowcolor{red!10}"
                lines.append(row_prefix)

            scen_label = scenario_names[scenario] if strategy == 'A' else ''
            lines.append(
                f"{scen_label} & {strategy_names[strategy]} & "
                f"{td_str} & {mt_str} & "
                f"{success}/{len(rs)} & "
                f"{'/'.join(sorted(statuses))} \\\\"
            )

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")

    output_path.write_text('\n'.join(lines))
    print(f"✓ Tabla LaTeX: {output_path}")


def generar_resumen_csv(cells, rows, output_path):
    fieldnames = [
        'scenario', 'strategy', 'n_total', 'n_success', 'n_impossible',
        'tdetect_min', 'tdetect_p25', 'tdetect_med', 'tdetect_p75', 'tdetect_max',
        'mttr_min', 'mttr_p25', 'mttr_med', 'mttr_p75', 'mttr_max',
        'recovery_rate_pct',
    ]

    summary_rows = []
    for scenario in ['E1', 'E2', 'E3', 'E4']:
        for strategy in ['A', 'B', 'C']:
            rs = cells.get((scenario, strategy), [])
            td = [float(r['t_detect_s']) for r in rs if r['t_detect_s']]
            mt = [float(r['mttr_s']) for r in rs if r['mttr_s']]
            success = sum(1 for r in rs if r['recovery_status'] == 'success')
            impossible = sum(1 for r in rs if r['recovery_status'] == 'impossible')

            row = {
                'scenario': scenario,
                'strategy': strategy,
                'n_total': len(rs),
                'n_success': success,
                'n_impossible': impossible,
                'recovery_rate_pct': round(success / len(rs) * 100, 1) if rs else 0,
            }

            for name, data in [('tdetect', td), ('mttr', mt)]:
                if data:
                    row[f'{name}_min'] = round(min(data), 3)
                    row[f'{name}_p25'] = round(float(np.percentile(data, 25)), 3)
                    row[f'{name}_med'] = round(float(np.median(data)), 3)
                    row[f'{name}_p75'] = round(float(np.percentile(data, 75)), 3)
                    row[f'{name}_max'] = round(max(data), 3)
                else:
                    for stat in ['min', 'p25', 'med', 'p75', 'max']:
                        row[f'{name}_{stat}'] = ''

            summary_rows.append(row)

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"✓ Resumen CSV: {output_path}")


def imprimir_tabla_consola(cells):
    """Imprime la tabla de resultados en formato legible por consola."""
    print()
    print(f"{'Celda':<12} {'T_det med(s)':>13} {'MTTR med(s)':>12} "
          f"{'Éxito':>7} {'Status'}")
    print("─" * 60)
    for scenario in ['E1', 'E2', 'E3', 'E4']:
        for strategy in ['A', 'B', 'C']:
            rs = cells.get((scenario, strategy), [])
            td = [float(r['t_detect_s']) for r in rs if r['t_detect_s']]
            mt = [float(r['mttr_s']) for r in rs if r['mttr_s']]
            success = sum(1 for r in rs if r['recovery_status'] == 'success')
            statuses = '/'.join(set(r['recovery_status'] for r in rs))

            td_str = f"{np.median(td):.1f}" if td else "—"
            mt_str = f"{np.median(mt):.1f}" if mt else "—"

            print(f"{scenario}×{strategy:<9} {td_str:>13} {mt_str:>12} "
                  f"{success}/{len(rs)}{' ':>2} {statuses}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description='Genera tabla LaTeX y CSV resumen del experimento PFG')
    parser.add_argument('--csv', default='results/raw_20260724_174113.csv',
                        help='Ruta al CSV de resultados')
    parser.add_argument('--outdir', default='results',
                        help='Directorio de salida')
    args = parser.parse_args()

    csv_path = Path(args.csv)
    outdir = Path(args.outdir)

    if not csv_path.exists():
        print(f"ERROR: no se encuentra {csv_path}", file=sys.stderr)
        sys.exit(1)

    outdir.mkdir(parents=True, exist_ok=True)
    rows, cells = cargar(csv_path)

    imprimir_tabla_consola(cells)
    generar_latex(cells, outdir / 'tabla_resultados.tex')
    generar_resumen_csv(cells, rows, outdir / 'resumen_celdas.csv')
    print("\n✓ Todo generado")


if __name__ == '__main__':
    main()
