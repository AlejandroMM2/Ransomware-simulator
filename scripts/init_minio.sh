#!/bin/sh
# init_minio.sh
# Inicialización de MinIO para el laboratorio PFG.
# Se ejecuta como initContainer o en el entrypoint de MinIO.
#
# Resultado esperado:
#   - restic-c: Object Lock COMPLIANCE 30 días (estrategia C)
#   - restic-b: bucket convencional sin protección (estrategia B)
#   - restic-c-user: puede leer y escribir, NO puede borrar
#   - restic-b-user: lectura y escritura estándar
#
# El "|| true" al final de cada mc admin evita que el script falle
# si el usuario o la política ya existen de una ejecución anterior.

# Arrancar → Esperar a MinIO → Crear buckets → Crear políticas → Crear usuarios → Asignar políticas → Listo

set -e
ALIAS="local"

echo "===> Configurando MinIO..."

until mc alias set $ALIAS "http://minio:9000" \
    "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" 2>/dev/null; do
    echo "  → esperando a MinIO..."
    sleep 2
done

# Bucket C — con Object Lock. La flag --with-lock es obligatoria
# en la creación; no se puede añadir a posteriori.
if ! mc ls $ALIAS/restic-c >/dev/null 2>&1; then
    echo "  → Creando restic-c con Object Lock COMPLIANCE (30 días)..."
    mc mb --with-lock $ALIAS/restic-c
    mc retention set --default COMPLIANCE "30d" $ALIAS/restic-c
fi

# Bucket B — convencional, sin ninguna protección
if ! mc ls $ALIAS/restic-b >/dev/null 2>&1; then
    echo "  → Creando restic-b (sin protección)..."
    mc mb $ALIAS/restic-b
fi

# Políticas IAM desde ficheros JSON en /policies/
mc admin policy create $ALIAS restic-c-policy \
    /policies/restic-c-policy.json 2>/dev/null || true
mc admin policy create $ALIAS restic-b-policy \
    /policies/restic-b-policy.json 2>/dev/null || true

mc admin user add $ALIAS "$RESTIC_C_USER" "$RESTIC_C_SECRET" \
    2>/dev/null || true
mc admin user add $ALIAS "$RESTIC_B_USER" "$RESTIC_B_SECRET" \
    2>/dev/null || true

mc admin policy attach $ALIAS restic-c-policy \
    --user "$RESTIC_C_USER" 2>/dev/null || true
mc admin policy attach $ALIAS restic-b-policy \
    --user "$RESTIC_B_USER" 2>/dev/null || true

echo "✓ MinIO configurado"
