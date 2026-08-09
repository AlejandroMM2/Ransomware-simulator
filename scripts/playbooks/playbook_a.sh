#!/bin/bash
# Estrategia A: sin backup — recuperación imposible
set -uo pipefail

RUN_ID="${1:-run_000}"
mkdir -p /var/log/lab
T_FIRST_ACTION=$(date -u +%s%N)

log_event() {
    echo "{\"ts\":$(date -u +%s%N),\"run_id\":\"$RUN_ID\",\"strategy\":\"A\",\"event\":\"$1\"$([ -n "${2:-}" ] && echo ",\"data\":\"$2\"")}"
}

log_event "start"

# Verificar estado post-ataque
ENCRYPTED=$(docker exec fileserver bash -c "ls /opt/labprueba/*.encrypted 2>/dev/null | wc -l" 2>/dev/null || echo "0")
TOTAL=$(docker exec fileserver bash -c "ls /opt/labprueba/ 2>/dev/null | wc -l" 2>/dev/null || echo "0")

log_event "state_check" "encrypted=$ENCRYPTED,total=$TOTAL"

T_END=$(date -u +%s%N)

# Esta es la línea que parsea el runner (event=result)
echo "{\"ts\":$T_END,\"run_id\":\"$RUN_ID\",\"strategy\":\"A\",\"event\":\"result\",\"recovery_status\":\"impossible\",\"t_restore_ns\":null,\"restored_files\":0,\"integrity_match\":false,\"t_first_action_ns\":$T_FIRST_ACTION}"
