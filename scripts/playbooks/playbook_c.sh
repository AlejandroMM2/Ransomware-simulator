#!/bin/bash
# Estrategia C: restauración desde MinIO con Object Lock
# Usa --no-lock porque restic-c-user no tiene permisos de borrado de locks
set -uo pipefail

RUN_ID="${1:-run_000}"
mkdir -p /var/log/lab
T_FIRST_ACTION=$(date -u +%s%N)

log_event() {
    echo "{\"ts\":$(date -u +%s%N),\"run_id\":\"$RUN_ID\",\"strategy\":\"C\",\"event\":\"$1\"$([ -n "${2:-}" ] && echo ",\"data\":\"$2\"")}"
}

log_event "start"

# 1. Verificar snapshots con --no-lock
log_event "check_repository"
SNAPSHOTS=$(docker exec fileserver bash -c "
    export RESTIC_REPOSITORY='s3:http://minio:9000/restic-c'
    export RESTIC_PASSWORD='ResticRepoLab2026Pass'
    export AWS_ACCESS_KEY_ID='restic-c-user'
    export AWS_SECRET_ACCESS_KEY='ResticCLab2026Secret'
    restic snapshots --no-lock 2>&1 | grep -c 'snapshot' || echo 0
" 2>/dev/null | tail -1)
log_event "snapshots_found" "count=$SNAPSHOTS"

# 2. Limpiar y restaurar
log_event "clear_target"
docker exec fileserver bash -c "rm -rf /opt/labprueba/* 2>/dev/null; mkdir -p /opt/labprueba"

log_event "restore_start"
docker exec fileserver bash -c "
    export RESTIC_REPOSITORY='s3:http://minio:9000/restic-c'
    export RESTIC_PASSWORD='ResticRepoLab2026Pass'
    export AWS_ACCESS_KEY_ID='restic-c-user'
    export AWS_SECRET_ACCESS_KEY='ResticCLab2026Secret'
    restic restore latest --target / --no-lock 2>&1 | tail -5
"
RESTORE_EXIT=$?
T_RESTORE=$(date -u +%s%N)
log_event "restore_done" "exit=$RESTORE_EXIT"

# 3. Verificar integridad
log_event "verify_start"
RESTORED=$(docker exec fileserver bash -c "ls /opt/labprueba/ | grep -v '.baseline_hashes' | wc -l" || echo "0")
HASH_MATCH=$(docker exec fileserver bash -c "
    sha256sum /opt/labprueba/* 2>/dev/null | grep -v '.baseline_hashes' | sort > /tmp/post_hashes_c.csv
    diff /opt/labprueba/.baseline_hashes.csv /tmp/post_hashes_c.csv > /dev/null 2>&1 && echo true || echo false
" || echo "false")

log_event "verify_done" "restored=$RESTORED,hash_match=$HASH_MATCH"
T_END=$(date -u +%s%N)
STATUS=$([ "$HASH_MATCH" = "true" ] && echo "success" || echo "partial")
echo "{\"ts\":$T_END,\"run_id\":\"$RUN_ID\",\"strategy\":\"C\",\"event\":\"result\",\"recovery_status\":\"$STATUS\",\"t_restore_ns\":$T_RESTORE,\"restored_files\":$RESTORED,\"integrity_match\":$HASH_MATCH,\"t_first_action_ns\":$T_FIRST_ACTION}"
