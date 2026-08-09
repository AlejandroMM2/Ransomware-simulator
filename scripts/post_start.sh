#!/bin/bash
# post_start.sh
# Comprobaciones y ajustes post-arranque del laboratorio PFG.
#
# Cuándo ejecutarlo: después de "docker compose up -d" o tras un reinicio
# del host. No hace falta ejecutarlo si los contenedores ya estaban corriendo.
#
# Es idempotente — se puede lanzar cuantas veces haga falta sin romper nada.

set -uo pipefail

echo "════════════════════════════════════════════════"
echo "  Post-start del laboratorio PFG"
echo "════════════════════════════════════════════════"

# ─── 1. Esperar a que el indexer esté sano ───
echo ""
echo "▶ 1/4: Esperando al indexer..."
while [ "$(docker inspect -f '{{.State.Health.Status}}' wazuh-indexer 2>/dev/null)" != "healthy" ]; do
    echo -n "."
    sleep 5
done
echo " ✓ indexer healthy"

# ─── 2. Verificar/inicializar security plugin ───
echo ""
echo "▶ 2/4: Comprobando configuración de seguridad..."
SEC_INDEX=$(docker exec wazuh-indexer curl -sk \
    --cacert /usr/share/wazuh-indexer/certs/root-ca.pem \
    --cert /usr/share/wazuh-indexer/certs/admin.pem \
    --key /usr/share/wazuh-indexer/certs/admin-key.pem \
    "https://localhost:9200/_cat/indices?h=index" 2>/dev/null | \
    grep -c "opendistro_security")

if [ "$SEC_INDEX" -ge 1 ]; then
    echo "  ✓ .opendistro_security ya inicializado"
else
    echo "  → Inicializando security plugin (primera vez o volumen borrado)..."
    docker exec wazuh-indexer bash -c '
        export OPENSEARCH_JAVA_HOME=/usr/share/wazuh-indexer/jdk
        bash /usr/share/wazuh-indexer/plugins/opensearch-security/tools/securityadmin.sh \
            -cd /usr/share/wazuh-indexer/opensearch-security/ \
            -nhnv \
            -cacert /usr/share/wazuh-indexer/certs/root-ca.pem \
            -cert /usr/share/wazuh-indexer/certs/admin.pem \
            -key /usr/share/wazuh-indexer/certs/admin-key.pem \
            -h localhost -p 9200 -icl
    ' 2>&1 | tail -3
fi

# ─── 3. Esperar al manager y verificar grupos de agentes ───
echo ""
echo "▶ 3/4: Esperando al manager y verificando grupos..."
while [ "$(docker inspect -f '{{.State.Health.Status}}' wazuh-manager 2>/dev/null)" != "healthy" ]; do
    echo -n "."
    sleep 5
done
echo " ✓ manager healthy"

for GROUP in lab-victims lab-attacker lab-backup; do
    if docker exec wazuh-manager /var/ossec/bin/agent_groups -l 2>/dev/null | grep -q "^$GROUP"; then
        echo "  ✓ Grupo '$GROUP' ya existe"
    else
        echo "  → Creando grupo '$GROUP'..."
        docker exec wazuh-manager /var/ossec/bin/agent_groups -a -g "$GROUP" -q
    fi
done

# ─── 4. Verificar agentes activos ───
echo ""
echo "▶ 4/4: Verificando agentes conectados..."
sleep 10  # Dale tiempo a los agentes a reconectar
ACTIVE=$(docker exec wazuh-manager /var/ossec/bin/agent_control -l 2>/dev/null | grep -c "Active")

if [ "$ACTIVE" -ge 4 ]; then
    echo "  ✓ $ACTIVE agentes activos"
else
    echo "  ⚠️  Solo $ACTIVE agentes activos (esperado 4+)"
    echo "  → Reiniciando contenedores agente para forzar reconexión..."
    docker compose restart fileserver workstation attacker restic-sftp
    sleep 20
    ACTIVE=$(docker exec wazuh-manager /var/ossec/bin/agent_control -l 2>/dev/null | grep -c "Active")
    echo "  ✓ Ahora $ACTIVE agentes activos"
fi

echo ""
echo "════════════════════════════════════════════════"
echo "  ✓ Laboratorio listo para experimentos"
echo "════════════════════════════════════════════════"
docker exec wazuh-manager /var/ossec/bin/agent_control -l 2>/dev/null | grep -E "ID:|Active"


