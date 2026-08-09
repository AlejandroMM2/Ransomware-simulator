#!/bin/bash
# ===============================================================
#  verify_lab.sh — Verifica que todo el laboratorio está sano
# ===============================================================

set -uo pipefail

# Cargar variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

INDEXER_PASS="${INDEXER_PASSWORD:-WazuhLab2026Pass}"
API_PASS="${API_PASSWORD:-WazuhApi2026Pass}"

pass() { echo "  ✓ $1"; }
fail() { echo "  ✗ $1"; FAILED=1; }
info() { echo "  · $1"; }

FAILED=0

echo "══════════════════════════════════════════════"
echo "  Verificación del laboratorio PFG"
echo "══════════════════════════════════════════════"

# ============================================================
# 1. Estado de contenedores
# ============================================================
echo ""
echo "▶ Estado de contenedores:"
docker compose ps --format "table {{.Name}}\t{{.State}}\t{{.Status}}"

# ============================================================
# 2. Health de servicios críticos
# ============================================================
echo ""
echo "▶ Health status:"
for svc in wazuh-indexer wazuh-manager minio; do
    status=$(docker inspect -f '{{.State.Health.Status}}' $svc 2>/dev/null || echo "no-health")
    if [ "$status" = "healthy" ]; then
        pass "$svc: $status"
    else
        fail "$svc: $status"
    fi
done

# ============================================================
# 3. Wazuh Indexer
# ============================================================
echo ""
echo "▶ Wazuh Indexer:"
cluster_status=$(docker exec wazuh-manager curl -sk -u "admin:$INDEXER_PASS" \
    https://wazuh-indexer:9200/_cluster/health 2>/dev/null | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])" 2>/dev/null)

if [ "$cluster_status" = "green" ] || [ "$cluster_status" = "yellow" ]; then
    pass "Cluster status: $cluster_status"
else
    fail "Cluster status: $cluster_status (esperado: yellow o green)"
fi

# Verificar índice de seguridad
sec_index=$(docker exec wazuh-manager curl -sk -u "admin:$INDEXER_PASS" \
    "https://wazuh-indexer:9200/_cat/indices?h=index" 2>/dev/null | \
    grep -c ".opendistro_security")

if [ "$sec_index" -ge 1 ]; then
    pass ".opendistro_security index existe"
else
    fail ".opendistro_security NO existe (falta ejecutar securityadmin.sh)"
fi

# ============================================================
# 4. Wazuh Manager
# ============================================================
echo ""
echo "▶ Wazuh Manager:"
manager_procs=$(docker exec wazuh-manager /var/ossec/bin/wazuh-control status 2>/dev/null | \
    grep -c "is running")

if [ "$manager_procs" -ge 5 ]; then
    pass "Procesos wazuh-*: $manager_procs corriendo"
else
    fail "Solo $manager_procs procesos wazuh corriendo (esperado 5+)"
fi

# Filebeat conectado
filebeat_ok=$(docker compose logs --tail 100 wazuh-manager 2>&1 | \
    grep -c "Connection to backoff(elasticsearch")

if [ "$filebeat_ok" -ge 1 ]; then
    pass "Filebeat conectado al indexer"
else
    fail "Filebeat SIN conexión estable al indexer"
fi

# ============================================================
# 5. Agentes
# ============================================================
echo ""
echo "▶ Agentes registrados:"
agents=$(docker exec wazuh-manager /var/ossec/bin/agent_control -l 2>/dev/null | \
    grep -c "Active")

if [ "$agents" -ge 4 ]; then
    pass "$agents agentes activos"
    docker exec wazuh-manager /var/ossec/bin/agent_control -l 2>/dev/null | \
        grep -E "ID:|Active" | while read line; do
        info "$line"
    done
else
    fail "Solo $agents agentes activos (esperado 4: manager + fileserver + workstation + attacker + restic-sftp)"
fi

# ============================================================
# 6. MinIO
# ============================================================
echo ""
echo "▶ MinIO:"
if docker exec minio mc ready local 2>/dev/null | grep -q "The cluster"; then
    pass "MinIO listo"
else
    # Alternativa: comprobar respuesta del API
    if docker exec minio mc alias set local http://localhost:9000 \
        "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1; then
        pass "MinIO responde"
    else
        fail "MinIO no responde"
    fi
fi

# Object Lock en restic-c
lock_status=$(docker exec minio mc retention info local/restic-c 2>&1 | \
    grep -c "COMPLIANCE")
if [ "$lock_status" -ge 1 ]; then
    pass "restic-c con Object Lock COMPLIANCE"
else
    fail "restic-c SIN Object Lock (falta init)"
fi

# ============================================================
# 7. Dashboard
# ============================================================
echo ""
echo "▶ Dashboard:"
http_code=$(curl -sk -o /dev/null -w "%{http_code}" https://localhost 2>/dev/null)
if [ "$http_code" = "200" ] || [ "$http_code" = "302" ]; then
    pass "Dashboard responde HTTP $http_code"
    info "Accede en: https://localhost (admin/$INDEXER_PASS)"
else
    fail "Dashboard responde HTTP $http_code"
fi

# ============================================================
# 8. Recursos
# ============================================================
echo ""
echo "▶ Recursos actuales:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# ============================================================
# Resumen
# ============================================================
echo ""
echo "══════════════════════════════════════════════"
if [ "$FAILED" -eq 0 ]; then
    echo "  ✓ LABORATORIO OPERATIVO"
    echo "══════════════════════════════════════════════"
    exit 0
else
    echo "  ✗ HAY PROBLEMAS QUE RESOLVER"
    echo "══════════════════════════════════════════════"
    exit 1
fi
