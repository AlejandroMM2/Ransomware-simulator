# PFG Laboratorio

Construcción del laboratorio con orden de arranque garantizado, sin los problemas anteriores.

## Filosofía de este diseño

**Principios que sigo aquí:**

1. **Cada servicio empieza cuando su dependencia está *sana*, no solo *arrancada*.** Uso healthchecks reales, no `depends_on` simple.
2. **Todas las contraseñas alfanuméricas simples.** Sin `!`, `$`, `#`, `:`, `'` o comillas. Esto evita que sed, awk o entrypoints las corrompan.
3. **Certificados generados con OpenSSL, no con el script de Wazuh.** Cadena única, DN admin que la imagen de Wazuh ya acepta por defecto.
4. **Sin chrony en los contenedores.** El host provee la hora, los contenedores la heredan.
5. **Entrypoints tolerantes a fallos parciales.** Si un servicio ya está arriba, no aborta; usa `|| true`.
6. **Bind mounts sobre ficheros clave** que la imagen Wazuh podría reescribir en el arranque (filebeat.yml, opensearch_dashboards.yml). Así los cambios sobreviven.

## Orden de arranque garantizado

```
FASE 1 (0-90s):    wazuh-indexer         → healthy (puerto 9200)
FASE 2 (90-180s):  wazuh-manager         → healthy (puertos 1514, 55000)
FASE 3 (180s+):    wazuh-dashboard, fileserver, workstation, attacker, restic-sftp
FASE 4 (paralelo): minio → healthy → minio-init crea buckets y usuarios
```

## Cómo usar este paquete

### Paso 1: preparar el sistema

```bash
# Espacio libre suficiente
df -h /pfg   # al menos 30 GB libres

# Docker moderno con Compose v2
docker compose version
# Debe decir v2.x

# vm.max_map_count para OpenSearch
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

### Paso 2: colocar el paquete

```bash
# Reemplaza tu directorio de proyecto
mv /pfg/pfg_contenedores /pfg/pfg_contenedores.OLD
mkdir /pfg/pfg_contenedores
cd /pfg/pfg_contenedores

# Copia todo lo del zip aquí
```

### Paso 3: limpiar estado anterior

```bash
# Para el laboratorio antiguo si sigue vivo
cd /pfg/pfg_contenedores.OLD
docker compose down 2>/dev/null

# Borrar volúmenes antiguos (contienen configuraciones rotas)
docker volume ls -q | grep -iE "pfg|wazuh|minio|restic|labprueba" | \
    xargs -r docker volume rm 2>/dev/null

# Verificar limpio
docker volume ls
docker ps -a
```

### Paso 4: generar certificados

```bash
cd /pfg/pfg_contenedores
chmod +x generate_certs.sh
./generate_certs.sh
```

Verifica que los tres certificados de servicio tienen el mismo Issuer.

### Paso 5: preparar el .env

```bash
cp .env.example .env
# El .env.example ya tiene contraseñas válidas alfanuméricas.
# Si quieres cambiarlas, hazlo antes de arrancar:
nano .env
```

### Paso 6: construir imágenes

```bash
docker compose build
```

Debe terminar sin errores. Tarda 15-20 minutos la primera vez.

### Paso 7: arranque en dos etapas

**Etapa A**: solo el indexer, y ejecutar securityadmin una vez.

```bash
docker compose up -d wazuh-indexer

# Esperar activamente a que esté sano
echo "Esperando al indexer..."
while [ "$(docker inspect -f '{{.State.Health.Status}}' wazuh-indexer 2>/dev/null)" != "healthy" ]; do
    sleep 5
    echo -n "."
done
echo " healthy"

# Inicializar plugin de seguridad
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

Debe terminar con `Done with success`.

**Etapa B**: arrancar el resto.

```bash
docker compose up -d
```

Espera 3-5 minutos.

### Paso 8: verificar

```bash
chmod +x scripts/verify_lab.sh
./scripts/verify_lab.sh
```

Todos los checks deben pasar.

### Paso 9: crear grupos de agentes y esperar a que se registren

```bash
docker exec wazuh-manager /var/ossec/bin/agent_groups -a -g lab-victims -q
docker exec wazuh-manager /var/ossec/bin/agent_groups -a -g lab-attacker -q
docker exec wazuh-manager /var/ossec/bin/agent_groups -a -g lab-backup -q

# Reiniciar las víctimas para que se registren en el grupo correcto
docker compose restart fileserver workstation attacker restic-sftp

sleep 30

# Ver estado de agentes
docker exec wazuh-manager /var/ossec/bin/agent_control -l
```

Los 4 agentes deben aparecer como `Active`.

## Si algo falla

Cada fase tiene su comando de verificación. Si el flujo se atasca en la fase X, mira específicamente esa. Los mensajes anteriores del chat cubren la mayoría de errores comunes con soluciones concretas.

## Estructura del paquete

```
pfg_contenedores/
├── README.md                          ← este fichero
├── docker-compose.yml
├── .env.example
├── generate_certs.sh                  ← genera toda la PKI con OpenSSL
├── dockerfiles/
│   ├── fileserver.Dockerfile
│   ├── workstation.Dockerfile
│   ├── attacker.Dockerfile
│   └── restic-sftp.Dockerfile
├── scripts/
│   ├── verify_lab.sh                  ← script de verificación
│   ├── fileserver-entrypoint.sh
│   ├── workstation-entrypoint.sh
│   ├── attacker-entrypoint.sh
│   ├── restic-sftp-entrypoint.sh
│   ├── init_minio.sh
│   └── generate_test_files.sh
├── lab-config/
│   ├── wazuh/
│   │   ├── local_rules.xml
│   │   └── audit-rules-victim.rules
│   ├── minio/
│   │   ├── restic-c-policy.json
│   │   └── restic-b-policy.json
│   └── ssh-keys/                      ← aquí van las claves cuando las generes
└── simulators/
    └── scenarios/                     ← e1, e2, e3, e4 (ya tienes)
```
