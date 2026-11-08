#!/usr/bin/env python3
"""
02_figuras.py
=============
Genera las figuras del experimento PFG para la memoria.

Figuras generadas:
  figura1_mttr_boxplot.png     — Boxplot MTTR B vs C por escenario
  figura2_tasa_recuperacion.png — Tasa de éxito por estrategia
  figura3_tdetect.png          — T_detect mediana por celda
  figura4_mttr_scatter.png     — Scatter MTTR por repetición

Uso:
  python3 02_figuras.py
  python3 02_figuras.py --csv resultados/raw_experimento.csv
  python3 02_figuras.py --outdir imagenes/ --dpi 300
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


# ─── Paleta de colores consistente ────────────────────────────────────────────
COLORS = {
    'A': '#F44336',   # rojo  — sin backup
    'B': '#2196F3',   # azul  — Restic SFTP
    'C': '#4CAF50',   # verde — MinIO Object Lock
}
SCENARIO_LABELS = {
    'E1': 'E1\nCifrado local',
    'E2': 'E2\nDestrucción copias',
    'E3': 'E3\nMov. lateral',
    'E4': 'E4\nExfiltración',
}


# ─── Carga de datos ───────────────────────────────────────────────────────────

def cargar(csv_path):
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    cells = defaultdict(list)
    for r in rows:
        cells[(r['scenario'], r['strategy'])].append(r)
    return rows, cells


def mttr(cells, scenario, strategy):
    return [float(r['mttr_s']) for r in cells.get((scenario, strategy), [])
            if r['mttr_s']]


def tdetect(cells, scenario, strategy):
    return [float(r['t_detect_s']) for r in cells.get((scenario, strategy), [])
            if r['t_detect_s']]


# ─── Figura 1: Boxplot MTTR B vs C ───────────────────────────────────────────

def figura1_mttr_boxplot(cells, outdir, dpi):
    fig, axes = plt.subplots(1, 4, figsize=(16, 6))
    fig.suptitle(
        'MTTR por Escenario y Estrategia de Backup\n'
        'Laboratorio Ransomware — PFG Ciberseguridad',
        fontsize=13, fontweight='bold', y=1.02
    )

    for ax, scenario in zip(axes, ['E1', 'E2', 'E3', 'E4']):
        data_b = mttr(cells, scenario, 'B')
        data_c = mttr(cells, scenario, 'C')

        if data_b and data_c:
            bp = ax.boxplot(
                [data_b, data_c],
                patch_artist=True,
                widths=0.5,
                medianprops=dict(color='black', linewidth=2),
            )
            ax.set_xticks([1, 2])
            ax.set_xticklabels([
                f'Restic\nSFTP (B)\nn={len(data_b)}',
                f'MinIO\nObj.Lock (C)\nn={len(data_c)}'
            ], fontsize=8)
            for patch, strategy in zip(bp['boxes'], ['B', 'C']):
                patch.set_facecolor(COLORS[strategy])
                patch.set_alpha(0.75)

        elif data_c:
            # B imposible — solo mostrar C
            bp = ax.boxplot([data_c], patch_artist=True, widths=0.4,
                            medianprops=dict(color='black', linewidth=2))
            ax.set_xticks([1])
            ax.set_xticklabels([f'MinIO\nObj.Lock (C)\nn={len(data_c)}'], fontsize=8)
            bp['boxes'][0].set_facecolor(COLORS['C'])
            bp['boxes'][0].set_alpha(0.75)
            ax.text(0.5, 0.72,
                    'B: recuperación\nIMPOSIBLE\n(repo destruido)',
                    transform=ax.transAxes, ha='center', va='center',
                    color='#D32F2F', fontsize=8, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.4', facecolor='#FFEBEE',
                              edgecolor='#D32F2F', alpha=0.9))
        else:
            ax.text(0.5, 0.5, 'Sin datos', transform=ax.transAxes,
                    ha='center', va='center', color='gray')

        ax.set_title(SCENARIO_LABELS[scenario], fontweight='bold', fontsize=10)
        ax.set_ylabel('MTTR (segundos)')
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    plt.tight_layout()
    outpath = outdir / 'figura1_mttr_boxplot.png'
    plt.savefig(outpath, dpi=dpi, bbox_inches='tight')
    plt.close()
    print(f"✓ {outpath}")


# ─── Figura 2: Tasa de recuperación ──────────────────────────────────────────

def figura2_tasa_recuperacion(rows, outdir, dpi):
    fig, ax = plt.subplots(figsize=(9, 6))

    strategies = ['A', 'B', 'C']
    labels = ['A — Sin backup', 'B — Restic+SFTP', 'C — MinIO Object Lock']
    rates = []
    counts = []

    # Solo escenarios con perdida de datos (E1, E2): en E3/E4 no se destruye
    # nada, asi que la "tasa de recuperacion" alli no tiene sentido.
    for strategy in strategies:
        rs = [r for r in rows if r['strategy'] == strategy
              and r['scenario'] in ('E1', 'E2')]
        s = sum(1 for r in rs if r['recovery_status'] == 'success')
        rates.append(s / len(rs) * 100 if rs else 0)
        counts.append((s, len(rs)))

    bars = ax.bar(labels, rates,
                  color=[COLORS[s] for s in strategies],
                  alpha=0.85, width=0.5,
                  edgecolor='white', linewidth=1.5)

    for bar, rate, (s, n) in zip(bars, rates, counts):
        ax.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + 2,
                f'{rate:.0f}%\n({s}/{n})',
                ha='center', va='bottom',
                fontweight='bold', fontsize=11)

    ax.set_ylabel('Tasa de Recuperación Exitosa (%)', fontsize=11)
    ax.set_title(
        'Tasa de Recuperación por Estrategia de Backup\n'
        '(solo escenarios con pérdida de datos: E1 y E2, n=20 por estrategia)',
        fontweight='bold', fontsize=12
    )
    ax.set_ylim(0, 120)
    ax.axhline(y=100, color='green', linestyle='--', alpha=0.5,
               linewidth=1.5, label='100% — objetivo')
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=10)

    plt.tight_layout()
    outpath = outdir / 'figura2_tasa_recuperacion.png'
    plt.savefig(outpath, dpi=dpi, bbox_inches='tight')
    plt.close()
    print(f"✓ {outpath}")


# ─── Figura 3: T_detect por celda ────────────────────────────────────────────

def figura3_tdetect(cells, outdir, dpi):
    fig, ax = plt.subplots(figsize=(14, 6))

    labels, medians, iqr_low, iqr_high, bar_colors = [], [], [], [], []

    for scenario in ['E1', 'E2', 'E3', 'E4']:
        for strategy in ['A', 'B', 'C']:
            td = tdetect(cells, scenario, strategy)
            if td:
                labels.append(f"{scenario}×{strategy}")
                medians.append(np.median(td))
                iqr_low.append(np.percentile(td, 25))
                iqr_high.append(np.percentile(td, 75))
                bar_colors.append(COLORS[strategy])

    x = np.arange(len(labels))
    bars = ax.bar(x, medians, alpha=0.8, color=bar_colors, edgecolor='white')
    ax.errorbar(
        x, medians,
        yerr=[np.array(medians) - np.array(iqr_low),
              np.array(iqr_high) - np.array(medians)],
        fmt='none', color='#333333', capsize=5, linewidth=1.5
    )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
    ax.set_ylabel('T_detect mediana (segundos)', fontsize=11)
    ax.set_title(
        'Tiempo de Detección (T_detect) por Celda Experimental\n'
        'Barras de error = IQR [P25–P75]',
        fontweight='bold', fontsize=12
    )
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.axhline(y=60, color='red', linestyle='--', alpha=0.6,
               linewidth=1.5, label='1 minuto')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    legend_patches = [
        mpatches.Patch(color=COLORS['A'], label='A — Sin backup'),
        mpatches.Patch(color=COLORS['B'], label='B — Restic+SFTP'),
        mpatches.Patch(color=COLORS['C'], label='C — MinIO Object Lock'),
    ]
    ax.legend(handles=legend_patches + [
        plt.Line2D([0], [0], color='red', linestyle='--', label='1 minuto')
    ], fontsize=9)

    plt.tight_layout()
    outpath = outdir / 'figura3_tdetect.png'
    plt.savefig(outpath, dpi=dpi, bbox_inches='tight')
    plt.close()
    print(f"✓ {outpath}")


# ─── Figura 4: Scatter MTTR por repetición ───────────────────────────────────

def figura4_mttr_scatter(cells, outdir, dpi):
    fig, axes = plt.subplots(1, 4, figsize=(16, 5))
    fig.suptitle(
        'Variabilidad del MTTR por Repetición\n'
        'Cada punto = una ejecución del experimento',
        fontsize=13, fontweight='bold'
    )

    for ax, scenario in zip(axes, ['E1', 'E2', 'E3', 'E4']):
        for i, strategy in enumerate(['B', 'C']):
            data = mttr(cells, scenario, strategy)
            if data:
                reps = list(range(1, len(data) + 1))
                ax.scatter(reps, data, color=COLORS[strategy], alpha=0.8,
                           s=50, label=f'Estrategia {strategy}', zorder=3)
                ax.axhline(y=np.median(data), color=COLORS[strategy],
                           linestyle='--', alpha=0.6, linewidth=1.5)

        ax.set_title(SCENARIO_LABELS[scenario], fontweight='bold', fontsize=10)
        ax.set_xlabel('Repetición', fontsize=9)
        ax.set_ylabel('MTTR (s)', fontsize=9)
        ax.grid(alpha=0.3, linestyle='--')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        if scenario == 'E2':
            ax.text(0.5, 0.5, 'B: impossible',
                    transform=ax.transAxes, ha='center', va='center',
                    color='#D32F2F', fontsize=9, fontweight='bold',
                    bbox=dict(boxstyle='round', facecolor='#FFEBEE', alpha=0.9))

    handles = [
        mpatches.Patch(color=COLORS['B'], label='B — Restic+SFTP'),
        mpatches.Patch(color=COLORS['C'], label='C — MinIO Object Lock'),
    ]
    fig.legend(handles=handles, loc='lower center', ncol=2,
               fontsize=10, bbox_to_anchor=(0.5, -0.05))

    plt.tight_layout()
    outpath = outdir / 'figura4_mttr_scatter.png'
    plt.savefig(outpath, dpi=dpi, bbox_inches='tight', pad_inches=0.3)
    plt.close()
    print(f"✓ {outpath}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Genera figuras del experimento PFG')
    parser.add_argument('--csv', default='results/raw_20260724_174113.csv',
                        help='Ruta al CSV de resultados')
    parser.add_argument('--outdir', default='results',
                        help='Directorio de salida para las figuras')
    parser.add_argument('--dpi', type=int, default=150,
                        help='Resolución de las figuras (default: 150)')
    args = parser.parse_args()

    csv_path = Path(args.csv)
    outdir = Path(args.outdir)

    if not csv_path.exists():
        print(f"ERROR: no se encuentra {csv_path}", file=sys.stderr)
        sys.exit(1)

    outdir.mkdir(parents=True, exist_ok=True)

    rows, cells = cargar(csv_path)

    print(f"\n[INFO] Generando figuras en {outdir}/ (dpi={args.dpi})\n")
    figura1_mttr_boxplot(cells, outdir, args.dpi)
    figura2_tasa_recuperacion(rows, outdir, args.dpi)
    figura3_tdetect(cells, outdir, args.dpi)
    figura4_mttr_scatter(cells, outdir, args.dpi)

    print(f"\n✓ 4 figuras generadas en {outdir}/")


if __name__ == '__main__':
    main()
