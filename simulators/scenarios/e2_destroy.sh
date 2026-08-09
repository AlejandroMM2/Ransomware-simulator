#!/bin/bash
# E2 - Cifrado + intento de destruccion de copias
# Ataca tanto el repositorio Restic SFTP como el bucket MinIO

set -uo pipefail
LOG=/var/log/lab/runner.jsonl
mkdir -p "$(dirname $LOG)"

log_event() {
    ts=$(date -u +%s%N)
    echo "{\"ts\":$ts,\"scenario\":\"E2\",\"event\":\"$1\"$([ -n "${2:-}" ] && echo ",\"data\":\"$2\"")}" | tee -a "$LOG"
}

log_event "start"

# Fase 1: cifrado (equivalente E1)
log_event "phase1_encrypt_start"
bash /lab/simulators/scenarios/e1_local.sh >> "$LOG" 2>&1
log_event "phase1_encrypt_end"

# Fase 2: intento de borrar el repositorio SFTP (estrategia B)
# ESPERADO: exito (los backups convencionales no tienen proteccion)
log_event "phase2_sftp_delete_attempt"
ssh -i /etc/ssh-keys/lab_runner_key -o StrictHostKeyChecking=no \
    restic-b@restic-sftp \
    "rm -rf /srv/backups/restic-b/* 2>/dev/null; echo DELETED" \
    >> "$LOG" 2>&1
log_event "phase2_sftp_delete_end" "exit=$?"

# Fase 3: intento de borrar bucket MinIO C (estrategia C)
# ESPERADO: fallo con 403 (Object Lock COMPLIANCE bloquea)
log_event "phase3_minio_delete_attempt"

export AWS_ACCESS_KEY_ID="${RESTIC_C_USER:-restic-c-user}"
export AWS_SECRET_ACCESS_KEY="${RESTIC_C_SECRET:-ResticCLab2026Secret}"

aws --endpoint-url http://minio:9000 --no-verify-ssl \
    s3 rm s3://restic-c/ --recursive 2>&1 >> "$LOG"
MINIO_EXIT=$?

log_event "phase3_minio_delete_end" "exit=$MINIO_EXIT"

if [ $MINIO_EXIT -ne 0 ]; then
    log_event "immutability_verified" "object_lock_blocked_delete"
else
    log_event "immutability_FAILED" "delete_succeeded_check_config"
fi

log_event "end"
