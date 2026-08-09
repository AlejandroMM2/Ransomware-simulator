#!/bin/bash
# backup_volumes.sh — Guarda un snapshot de todos los volúmenes del laboratorio PFG
set -e

BACKUP_NAME="${1:-backup_$(date +%Y%m%d_%H%M%S)}"
BACKUP_DIR="/pfg/backups/${BACKUP_NAME}"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$BACKUP_DIR"
echo "→ Backup en: $BACKUP_DIR"

# 1. Config del proyecto
echo "[1/3] Guardando ficheros de config..."
tar czf "$BACKUP_DIR/project_config.tar.gz" \
    -C "$PROJECT_DIR" \
    docker-compose.yml \
    .env \
    generate_certs.sh \
    certs/ \
    lab-config/ \
    scripts/ \
    dockerfiles/ \
    simulators/ 2>/dev/null
echo "  ✓ project_config.tar.gz"

# 2. Volúmenes Docker
echo "[2/3] Guardando volúmenes Docker..."
VOLUMES=$(docker volume ls --format '{{.Name}}' | grep "pfg_contenedores")
for VOL in $VOLUMES; do
    echo -n "  - $VOL... "
    docker run --rm \
        -v "${VOL}:/source:ro" \
        -v "${BACKUP_DIR}:/backup" \
        alpine tar czf "/backup/volume_${VOL}.tar.gz" -C /source . 2>/dev/null
    echo "OK"
done

# 3. Metadata
echo "[3/3] Generando metadata..."
cat > "$BACKUP_DIR/metadata.txt" << META
=== Backup PFG ===
Fecha:    $(date -u +%Y-%m-%dT%H:%M:%SZ)
Nombre:   $BACKUP_NAME
Host:     $(hostname)
Docker:   $(docker --version)
Compose:  $(docker compose version --short 2>/dev/null)

=== Contenedores ===
$(docker compose -f "$PROJECT_DIR/docker-compose.yml" ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null)

=== Volúmenes ===
$(ls -lh "$BACKUP_DIR"/volume_*.tar.gz 2>/dev/null)
META

echo ""
echo "✓ Backup completado"
echo "  Ruta:   $BACKUP_DIR"
echo "  Tamaño: $(du -sh "$BACKUP_DIR" | cut -f1)"
