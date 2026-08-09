#!/bin/bash
# generate_test_files.sh
# Genera un conjunto de ficheros sintéticos para poblar el directorio víctima.
#
# Uso: generate_test_files.sh [directorio] [cantidad]
# Ejemplo: generate_test_files.sh /opt/labprueba 500
#
# Los ficheros son contenido aleatorio (/dev/urandom) para que Restic
# no los comprima demasiado y el tiempo de backup sea representativo.
# Los tamaños varían según el tipo para simular una distribución realista.

set -e

DEST="${1:-/opt/labprueba}"
COUNT="${2:-500}"

mkdir -p "$DEST"

for i in $(seq 1 $COUNT); do
    # Rotación cíclica de tipos — 1 de cada 5 ficheros es de cada tipo
    case $(( i % 5 )) in
        0) ext="txt";  size=$((RANDOM % 10 + 1))   ;;  #  1-10 KB
        1) ext="pdf";  size=$((RANDOM % 100 + 10))  ;;  # 10-110 KB
        2) ext="jpg";  size=$((RANDOM % 500 + 50))  ;;  # 50-550 KB
        3) ext="docx"; size=$((RANDOM % 200 + 20))  ;;  # 20-220 KB
        4) ext="bin";  size=$((RANDOM % 1000 + 100)) ;; # 100-1100 KB
    esac

    dd if=/dev/urandom \
       of="$DEST/file_$(printf '%04d' $i).$ext" \
       bs=1024 count=$size \
       status=none 2>/dev/null
done

echo "✓ Generados $COUNT ficheros en $DEST"
