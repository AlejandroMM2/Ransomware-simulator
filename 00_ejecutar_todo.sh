#!/bin/bash
# 00_ejecutar_todo.sh
# Ejecuta todos los scripts de análisis del PFG en orden.
#
# Uso:
#   ./00_ejecutar_todo.sh
#   ./00_ejecutar_todo.sh --csv resultados/raw_experimento.csv
#   ./00_ejecutar_todo.sh --outdir resultados/ --dpi 300

set -uo pipefail

# ─── Argumentos ───────────────────────────────────────────────────────────────
CSV="results/raw_20260724_174113.csv"
OUTDIR="results"
DPI=150

while [[ $# -gt 0 ]]; do
    case $1 in
        --csv)    CSV="$2";    shift 2 ;;
        --outdir) OUTDIR="$2"; shift 2 ;;
        --dpi)    DPI="$2";    shift 2 ;;
        *) echo "Argumento desconocido: $1"; exit 1 ;;
    esac
done

# ─── Directorio del script ────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "════════════════════════════════════════════════════"
echo "  Análisis PFG Ransomware Lab"
echo "════════════════════════════════════════════════════"
echo "CSV:    $CSV"
echo "Salida: $OUTDIR"
echo "DPI:    $DPI"
echo ""

# ─── Dependencias ─────────────────────────────────────────────────────────────
echo "▶ Verificando dependencias Python..."
python3 -c "import scipy, matplotlib, numpy" 2>/dev/null || {
    echo "Instalando dependencias..."
    pip install scipy matplotlib numpy --break-system-packages -q
}
echo "  OK"
echo ""

# ─── Análisis estadístico ─────────────────────────────────────────────────────
echo "▶ 1/3 Análisis estadístico..."
python3 "$SCRIPT_DIR/01_analisis_estadistico.py" \
    --csv "$CSV" \
    --output "$OUTDIR/estadisticas.txt"
echo ""

# ─── Figuras ──────────────────────────────────────────────────────────────────
echo "▶ 2/3 Generando figuras..."
python3 "$SCRIPT_DIR/02_figuras.py" \
    --csv "$CSV" \
    --outdir "$OUTDIR" \
    --dpi "$DPI"
echo ""

# ─── Tabla LaTeX y CSV resumen ────────────────────────────────────────────────
echo "▶ 3/3 Tabla LaTeX y CSV resumen..."
python3 "$SCRIPT_DIR/03_tabla_latex.py" \
    --csv "$CSV" \
    --outdir "$OUTDIR"
echo ""

# ─── Resumen de ficheros generados ────────────────────────────────────────────
echo "════════════════════════════════════════════════════"
echo "  Ficheros generados en $OUTDIR/"
echo "════════════════════════════════════════════════════"
ls -lh "$OUTDIR/estadisticas.txt" \
       "$OUTDIR/figura1_mttr_boxplot.png" \
       "$OUTDIR/figura2_tasa_recuperacion.png" \
       "$OUTDIR/figura3_tdetect.png" \
       "$OUTDIR/figura4_mttr_scatter.png" \
       "$OUTDIR/tabla_resultados.tex" \
       "$OUTDIR/resumen_celdas.csv" 2>/dev/null
echo ""
echo "✓ Análisis completo"
