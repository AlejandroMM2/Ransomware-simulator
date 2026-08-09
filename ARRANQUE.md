# Guía de arranque paso a paso

Esta es la secuencia exacta que debes seguir tras copiar todo a `/pfg/pfg_contenedores`. Cada paso tiene su verificación. **No pases al siguiente hasta que el actual esté OK**.

## Paso 0: preparación del sistema

```bash
# Verificar Docker Compose v2
docker compose version
# Debe decir "v2.x.x"

# Parámetro del kernel para OpenSearch
sudo sysctl -w vm.max_map_count=262144
grep -q "vm.max_map_count" /etc/sysctl.conf || \
    echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf

# Espacio libre
df -h /pfg
# Al menos 30 GB libres
```

## Paso 1: limpiar estado anterior

⚠️ Esto borra tus volúmenes actuales. Si tienes datos que conservar, sáltatelo.

```bash
cd /pfg/pfg_contenedores.OLD 2>/dev/null || cd /pfg/pfg_contenedores
docker compose down -v 2>/dev/null

# Borrar volúmenes por si quedaron huérfanos
docker volume ls -q | grep -iE "pfg|wazuh|minio|restic|labprueba" | \
    xargs -r docker volume rm 2>/dev/null

# Comprobar
docker volume ls
docker ps -a
```

## Paso 2: colocar el nuevo proyecto

```bash
# Si tenías el proyecto en /pfg/pfg_contenedores, muévelo antes:
mv /pfg/pfg_contenedores /pfg/pfg_contenedores.OLD 2>/dev/null

# Nuevo directorio
mkdir -p /pfg/pfg_contenedores
cd /pfg/pfg_contenedores

# Copia aquí todo el zip que te di, o los ficheros individuales
```

## Paso 3: generar certificados

```bash
chmod +x generate_certs.sh
./generate_certs.sh
```

**Verificación crítica**: al final del output debe aparecer:

- El mismo Issuer en TODOS los certificados
- El DN del admin exactamente: `subject=CN = admin, OU = Wazuh, O = Wazuh, L = California, C = US`
- El SAN del indexer con `DNS:wazuh-indexer`

Si alguna verificación falla, PARA AQUÍ. No sigas.

## Paso 4: preparar el .env

```bash
cp .env.example .env
# Las contraseñas del example son alfanuméricas y funcionan. Si quieres cambiarlas:
nano .env
```

⚠️ Regla dorada: contraseñas SOLO alfanuméricas (letras + números). Sin símbolos.

## Paso 5: dar permisos de ejecución a scripts

```bash
chmod +x scripts/*.sh
chmod +x generate_certs.sh
```

## Paso 6: construir las imágenes

```bash
docker compose build
```

**Tiempo esperado**: 15-20 minutos la primera vez (baja Wazuh, Kali, Ubuntu, MinIO...).

Si algún build falla, no sigas hasta arreglarlo.

## Paso 7: arranque en dos etapas

### Etapa A — Solo el indexer

```bash
docker compose up -d wazuh-indexer
```

Esperar activamente:

```bash
echo "Esperando indexer healthy..."
while [ "$(docker inspect -f '{{.State.Health.Status}}' wazuh-indexer 2>/dev/null)" != "healthy" ]; do
    sleep 5
    echo -n "."
done
echo " ✓ healthy"
```

**Verificar el estado del indexer**:

```bash
docker compose logs --tail 20 wazuh-indexer | grep -iE "error|opendistro" | head -10
```

Errores como `no such index [.opendistro_security]` son ESPERADOS aquí porque falta el siguiente paso.

### Etapa A.1 — Inicializar security plugin

Esto solo se hace UNA vez por instalación:

```bash
docker exec wazuh-indexer bash -c '
    export OPENSEARCH_JAVA_HOME=/usr/share/wazuh-indexer/jdk
    bash /usr/share/wazuh-indexer/plugins/opensearch-security/tools/securityadmin.sh \
        -cd /usr/share/wazuh-indexer/opensearch-security/ \
        -nhnv \
        -cacert /usr/share/wazuh-indexer/certs/root-ca.pem \
        -cert /usr/share/wazuh-indexer/certs/admin.pem \
        -key /usr/share/wazuh-indexer/certs/admin-key.pem \
        -h localhost -p 9200 -icl
'
```

**Debe terminar con**: `Done with success`

Si sale `is not an admin user`, el DN del cert admin es incorrecto. Regenera con `generate_certs.sh`.

Si sale error de conexión, espera 30s más y reintenta.

**Verificar índice creado**:

```bash
docker exec wazuh-manager curl -sk -u admin:WazuhLab2026Pass \
    "https://wazuh-indexer:9200/_cat/indices?v" 2>/dev/null | \
    grep opendistro
# Debe aparecer .opendistro_security
```

⚠️ Espera, aquí `wazuh-manager` aún no existe. Usa esto en su lugar:

```bash
# Desde el host, si el puerto 9200 está expuesto:
# NO está expuesto según el compose, así que usaremos temporalmente el contenedor init de minio
docker run --rm --network pfg_contenedores_lab-net curlimages/curl:latest \
    -sk -u admin:WazuhLab2026Pass \
    "https://wazuh-indexer:9200/_cat/indices?v"
```

### Etapa B — Arrancar el resto

```bash
docker compose up -d
```

Esperar unos minutos:

```bash
echo "Esperando manager healthy..."
while [ "$(docker inspect -f '{{.State.Health.Status}}' wazuh-manager 2>/dev/null)" != "healthy" ]; do
    sleep 5
    echo -n "."
done
echo " ✓ healthy"
```

## Paso 8: crear grupos de agentes

```bash
docker exec wazuh-manager /var/ossec/bin/agent_groups -a -g lab-victims -q
docker exec wazuh-manager /var/ossec/bin/agent_groups -a -g lab-attacker -q
docker exec wazuh-manager /var/ossec/bin/agent_groups -a -g lab-backup -q

# Verificar
docker exec wazuh-manager /var/ossec/bin/agent_groups -l
```

## Paso 9: reiniciar víctimas para registro

Los agentes intentaron registrarse antes de que existieran los grupos, así que los reiniciamos:

```bash
docker compose restart fileserver workstation attacker restic-sftp
sleep 30

# Verificar registro
docker exec wazuh-manager /var/ossec/bin/agent_control -l
```

**Esperado**: los 4 agentes como `Active`.

## Paso 10: verificación completa

```bash
./scripts/verify_lab.sh
```

Todos los checks deben pasar.

## Paso 11: acceso al dashboard

Abre en el navegador:

```
https://localhost
```

- Usuario: `admin`
- Password: `WazuhLab2026Pass` (o la que hayas puesto en `.env`)

## Solución rápida de problemas

### El indexer no llega a healthy

```bash
docker compose logs --tail 100 wazuh-indexer
```

Busca `bootstrap check failure`, `max_map_count`, errores de certificados.

### `securityadmin.sh` falla con "is not an admin user"

El DN del cert admin no coincide con el esperado. Regenera:

```bash
./generate_certs.sh
docker compose down
docker volume rm pfg_contenedores_wazuh-indexer-data
docker compose up -d wazuh-indexer
# Reintentar securityadmin.sh
```

### Filebeat no conecta (Unauthorized)

Verifica que la contraseña que Filebeat envía coincide con la del indexer:

```bash
# La que envía Filebeat
docker exec wazuh-manager grep "^  password" /etc/filebeat/filebeat.yml

# La que espera el indexer (por defecto = el hash del internal_users.yml)
# Prueba directa:
docker exec wazuh-manager curl -sk -u "admin:WazuhLab2026Pass" \
    https://wazuh-indexer:9200/_cluster/health
```

Si la contraseña que espera el indexer es diferente, cambia la de Filebeat con:

```bash
docker exec wazuh-manager sed -i "s|^  password:.*|  password: 'admin'|" /etc/filebeat/filebeat.yml
docker exec wazuh-manager service filebeat restart
```

### Los agentes aparecen como Disconnected

```bash
docker exec fileserver tail -30 /var/ossec/logs/ossec.log
```

Habitual: manager no accesible, esperar más tiempo.

## Backup del estado limpio

Cuando `verify_lab.sh` pase todos los checks, guarda un backup:

```bash
mkdir -p /pfg/backups
tar czf /pfg/backups/setup_ok_$(date +%Y%m%d_%H%M%S).tar.gz \
    docker-compose.yml .env certs/ lab-config/ scripts/ generate_certs.sh
```

Si algo se rompe, tienes de dónde recuperar la configuración exacta que funcionó.
