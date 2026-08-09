#!/bin/bash
# Estrategia B: restauración desde Restic + SFTP
set -uo pipefail

RUN_ID="${1:-run_000}"
mkdir -p /var/log/lab
T_FIRST_ACTION=$(date -u +%s%N)

log_event() {
    echo "{\"ts\":$(date -u +%s%N),\"run_id\":\"$RUN_ID\",\"strategy\":\"B\",\"event\":\"$1\"$([ -n "${2:-}" ] && echo ",\"data\":\"$2\"")}"
}

log_event "start"

# 1. Verificar si el repositorio existe y tiene snapshots
log_event "check_repository"
REPO_OK=$(docker exec fileserver bash -c "
    export RESTIC_REPOSITORY='sftp:restic-b@restic-sftp:/srv/backups/restic-b'
    export RESTIC_PASSWORD='ResticRepoLab2026Pass'
    restic snapshots 2>&1 | grep -c 'snapshot' || echo 0
" 2>/dev/null || echo "0")

# También verificar que el directorio tiene contenido (E2 puede haberlo vaciado)
DIR_OK=$(docker exec restic-sftp bash -c "ls /srv/backups/restic-b/ 2>/dev/null | wc -l")

if [ "$REPO_OK" = "0" ] || [ "$REPO_OK" = "" ] || [ "$DIR_OK" = "0" ]; then
    T_END=$(date -u +%s%N)
    log_event "repository_destroyed" "sftp_repo_unavailable"
    log_event "end"
    echo "{\"ts\":$T_END,\"run_id\":\"$RUN_ID\",\"strategy\":\"B\",\"event\":\"result\",\"recovery_status\":\"impossible\",\"t_restore_ns\":null,\"restored_files\":0,\"integrity_match\":false,\"t_first_action_ns\":$T_FIRST_ACTION}"
    exit 1
fi

# 2. Limpiar y restaurar
log_event "clear_target"
docker exec fileserver bash -c "rm -rf /opt/labprueba/* 2>/dev/null; mkdir -p /opt/labprueba"

log_event "restore_start"
docker exec fileserver bash -c "
    export RESTIC_REPOSITORY='sftp:restic-b@restic-sftp:/srv/backups/restic-b'
    export RESTIC_PASSWORD='ResticRepoLab2026Pass'
    restic restore latest --target / 2>&1 | tail -5
"
RESTORE_EXIT=$?
T_RESTORE=$(date -u +%s%N)
log_event "restore_done" "exit=$RESTORE_EXIT"

# 3. Verificar integridad
log_event "verify_start"
RESTORED=$(docker exec fileserver bash -c "ls /opt/labprueba/ | grep -v '.baseline_hashes' | wc -l" || echo "0")
HASH_MATCH=$(docker exec fileserver bash -c "
    sha256sum /opt/labprueba/* 2>/dev/null | grep -v '.baseline_hashes' | sort > /tmp/post_hashes_b.csv
    diff /opt/labprueba/.baseline_hashes.csv /tmp/post_hashes_b.csv > /dev/null 2>&1 && echo true || echo false
" || echo "false")

log_event "verify_done" "restored=$RESTORED,hash_match=$HASH_MATCH"

T_END=$(date -u +%s%N)
STATUS=$([ "$HASH_MATCH" = "true" ] && echo "success" || echo "partial")
echo "{\"ts\":$T_END,\"run_id\":\"$RUN_ID\",\"strategy\":\"B\",\"event\":\"result\",\"recovery_status\":\"$STATUS\",\"t_restore_ns\":$T_RESTORE,\"restored_files\":$RESTORED,\"integrity_match\":$HASH_MATCH,\"t_first_action_ns\":$T_FIRST_ACTION}"
