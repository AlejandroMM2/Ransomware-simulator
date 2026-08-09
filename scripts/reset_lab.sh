#!/bin/bash
# reset_lab.sh — Restaura el laboratorio a estado limpio antes de cada ejecución
set -uo pipefail

STRATEGY="${1:-A}"
TIMESTAMP=$(date -u +%s%N)
mkdir -p /var/log/lab
LOG="/var/log/lab/reset.log"

log() {
    echo "{\"ts\":$(date -u +%s%N),\"event\":\"reset\",\"strategy\":\"$STRATEGY\",\"msg\":\"$1\"}" | tee -a "$LOG"
}

log "start"

# 1. Descifrar ficheros si quedaron cifrados
log "decrypt_labprueba"
docker exec fileserver bash -c "
    if ls /opt/labprueba/*.encrypted 2>/dev/null | head -1 > /dev/null; then
        python3 /tmp/encryptor.py --dir /opt/labprueba --action decrypt 2>/dev/null || true
    fi
" 2>/dev/null || true

# 2. Regenerar ficheros baseline
log "regenerate_files"
docker exec fileserver bash -c "rm -rf /opt/labprueba/*"
docker exec fileserver /usr/local/bin/generate_test_files.sh /opt/labprueba 500

# Calcular hashes baseline
docker exec fileserver bash -c "
    sha256sum /opt/labprueba/* 2>/dev/null | sort > /opt/labprueba/.baseline_hashes.csv
"
log "baseline_hash_computed"

# 3. Limpiar repositorio Restic SFTP
log "clean_restic_sftp"
# Anterior problematico
#docker exec restic-sftp bash -c "rm -rf /srv/backups/restic-b && mkdir -p /srv/backups/restic-b" 2>/dev/null || true
docker exec restic-sftp bash -c "
    rm -rf /srv/backups/restic-b
    mkdir -p /srv/backups/restic-b
    chown restic-b:restic-b /srv/backups/restic-b
    chmod 750 /srv/backups/restic-b
" 2>/dev/null || true

# 4. Crear backup según estrategia (desde fileserver que tiene acceso al volumen)
case "$STRATEGY" in
    A)
        log "strategy_A_no_backup"
        ;;

    B)
        log "strategy_B_start"
        docker exec fileserver bash -c "
            export RESTIC_REPOSITORY='sftp:restic-b@restic-sftp:/srv/backups/restic-b'
            export RESTIC_PASSWORD='ResticRepoLab2026Pass'
            restic init 2>/dev/null || true
            restic backup /opt/labprueba --exclude '/opt/labprueba/.baseline_hashes.csv' 2>&1 | tail -3
        "
        log "strategy_B_done"
        ;;

    C)
        log "strategy_C_start"
        docker exec fileserver bash -c "
            export RESTIC_REPOSITORY='s3:http://minio:9000/restic-c'
            export RESTIC_PASSWORD='ResticRepoLab2026Pass'
            # Init con usuario root (puede borrar locks de test)
            export AWS_ACCESS_KEY_ID='pfgadmin'
            export AWS_SECRET_ACCESS_KEY='MinioLab2026Pass'
            restic init 2>/dev/null || true
            # Backup con usuario restringido y --no-lock
            export AWS_ACCESS_KEY_ID='restic-c-user'
            export AWS_SECRET_ACCESS_KEY='ResticCLab2026Secret'
            restic backup /opt/labprueba \
                --exclude '/opt/labprueba/.baseline_hashes.csv' \
                --no-lock 2>&1 | tail -3
        "
        log "strategy_C_done"
        ;;
esac

log "end"
echo "✓ Reset completado para estrategia $STRATEGY"
