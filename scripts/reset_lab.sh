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
    rm -f /opt/labprueba/.snapshot_id
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
            restic init >/dev/null 2>&1 || true
            for intento in 1 2 3; do
                SID=\$(restic backup /opt/labprueba \\
                        --exclude '/opt/labprueba/.baseline_hashes.csv' \\
                        --exclude '/opt/labprueba/.snapshot_id' \\
                        --json 2>>/tmp/restic_backup.err \\
                      | grep -o '\"snapshot_id\":\"[0-9a-f]*\"' | cut -d'\"' -f4)
                if [ -n \"\$SID\" ]; then echo \$SID > /opt/labprueba/.snapshot_id; exit 0; fi
                sleep 3
            done
            exit 1
        " || { log "strategy_B_backup_FAILED"; exit 1; }
        log "strategy_B_done"
        ;;

    C)
        log "strategy_C_start"
        docker exec fileserver bash -c "
            export RESTIC_REPOSITORY='s3:http://minio:9000/restic-c'
            export RESTIC_PASSWORD='ResticRepoLab2026Pass'
            # Init con usuario root (solo la primera vez; luego falla y se ignora)
            export AWS_ACCESS_KEY_ID='pfgadmin'
            export AWS_SECRET_ACCESS_KEY='MinioLab2026Pass'
            restic init >/dev/null 2>&1 || true
            # Backup con usuario restringido (sin permiso de borrado)
            export AWS_ACCESS_KEY_ID='restic-c-user'
            export AWS_SECRET_ACCESS_KEY='ResticCLab2026Secret'
            for intento in 1 2 3; do
                SID=\$(restic backup /opt/labprueba \\
                        --exclude '/opt/labprueba/.baseline_hashes.csv' \\
                        --exclude '/opt/labprueba/.snapshot_id' \\
                        --no-lock --json 2>>/tmp/restic_backup.err \\
                      | grep -o '\"snapshot_id\":\"[0-9a-f]*\"' | cut -d'\"' -f4)
                if [ -n \"\$SID\" ]; then echo \$SID > /opt/labprueba/.snapshot_id; exit 0; fi
                sleep 3
            done
            exit 1
        " || { log "strategy_C_backup_FAILED"; exit 1; }
        log "strategy_C_done"
        ;;
esac

log "end"
echo "✓ Reset completado para estrategia $STRATEGY"
