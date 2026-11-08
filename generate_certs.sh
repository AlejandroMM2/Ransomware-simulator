#!/bin/bash
# ==============================================================================
#  Genera toda la cadena PKI del laboratorio con OpenSSL.
#  - Una sola CA raíz.
#  - Todos los certs firmados por esa CA (Issuer consistente).
#  - DN del admin adaptado al que espera la imagen wazuh-indexer por defecto.
#  - SAN con DNS del hostname interno para que Filebeat encuentre al indexer.
# ==============================================================================

set -e

CERT_DIR=./certs
rm -rf $CERT_DIR
mkdir -p $CERT_DIR/{wazuh-indexer,wazuh-manager,wazuh-dashboard}

# ============================================================
# CA raíz
# ============================================================
echo "[1/6] CA raíz..."
openssl genrsa -out $CERT_DIR/root-ca-key.pem 4096 2>/dev/null
openssl req -new -x509 -sha256 -days 3650 -nodes \
    -key $CERT_DIR/root-ca-key.pem \
    -out $CERT_DIR/root-ca.pem \
    -subj "/C=US/L=California/O=Wazuh/OU=Wazuh/CN=Wazuh-Lab-CA"

# ============================================================
# Función helper para generar cert de servidor
# ============================================================
generate_server_cert() {
    local NAME=$1
    local OUTDIR=$2
    local FILENAME=$3
    
    cat > /tmp/${NAME}.cnf <<EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no
[req_distinguished_name]
C = US
L = California
O = Wazuh
OU = Wazuh
CN = ${NAME}
[v3_req]
keyUsage = keyEncipherment, dataEncipherment, digitalSignature
extendedKeyUsage = serverAuth, clientAuth
subjectAltName = @alt_names
[alt_names]
DNS.1 = ${NAME}
DNS.2 = localhost
IP.1 = 127.0.0.1
EOF

    openssl genrsa -out $OUTDIR/${FILENAME}-key.pem 2048 2>/dev/null
    openssl req -new -key $OUTDIR/${FILENAME}-key.pem \
        -out /tmp/${NAME}.csr -config /tmp/${NAME}.cnf
    openssl x509 -req -in /tmp/${NAME}.csr \
        -CA $CERT_DIR/root-ca.pem \
        -CAkey $CERT_DIR/root-ca-key.pem \
        -CAcreateserial \
        -out $OUTDIR/${FILENAME}.pem \
        -days 3650 -sha256 \
        -extensions v3_req -extfile /tmp/${NAME}.cnf 2>/dev/null
    
    cp $CERT_DIR/root-ca.pem $OUTDIR/root-ca.pem
    rm -f /tmp/${NAME}.cnf /tmp/${NAME}.csr
}

# ============================================================
# Certificados
# ============================================================
echo "[2/6] Cert wazuh-indexer..."
generate_server_cert "wazuh-indexer" "$CERT_DIR/wazuh-indexer" "indexer"

echo "[3/6] Cert admin (DN preconfigurado en la imagen Wazuh)..."
cat > /tmp/admin.cnf <<EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no
[req_distinguished_name]
C = US
L = California
O = Wazuh
OU = Wazuh
CN = admin
[v3_req]
keyUsage = keyEncipherment, dataEncipherment, digitalSignature
extendedKeyUsage = clientAuth, serverAuth
EOF

openssl genrsa -out $CERT_DIR/wazuh-indexer/admin-key.pem 2048 2>/dev/null
openssl req -new -key $CERT_DIR/wazuh-indexer/admin-key.pem \
    -out /tmp/admin.csr -config /tmp/admin.cnf
openssl x509 -req -in /tmp/admin.csr \
    -CA $CERT_DIR/root-ca.pem \
    -CAkey $CERT_DIR/root-ca-key.pem \
    -CAcreateserial \
    -out $CERT_DIR/wazuh-indexer/admin.pem \
    -days 3650 -sha256 \
    -extensions v3_req -extfile /tmp/admin.cnf 2>/dev/null
rm /tmp/admin.cnf /tmp/admin.csr

echo "[4/6] Cert wazuh-manager (para Filebeat)..."
generate_server_cert "wazuh-manager" "$CERT_DIR/wazuh-manager" "filebeat"
# Filebeat espera extensión .key, no -key.pem
mv $CERT_DIR/wazuh-manager/filebeat-key.pem $CERT_DIR/wazuh-manager/filebeat.key

echo "[5/6] Cert wazuh-dashboard..."
generate_server_cert "wazuh-dashboard" "$CERT_DIR/wazuh-dashboard" "dashboard"

echo "[6/6] Permisos..."
chown -R 1000:1000 $CERT_DIR
chmod -R 500 $CERT_DIR
find $CERT_DIR -type f -exec chmod 400 {} \;

# Limpieza
rm -f $CERT_DIR/root-ca.srl 2>/dev/null

# ============================================================
# Verificación
# ============================================================
echo ""
echo "════════════════ Verificación ════════════════"
echo ""
echo "Issuer del root CA:"
openssl x509 -in $CERT_DIR/root-ca.pem -noout -subject
echo ""
echo "Issuer de cada cert (TODOS deben ser el mismo):"
for f in $CERT_DIR/wazuh-indexer/indexer.pem \
         $CERT_DIR/wazuh-indexer/admin.pem \
         $CERT_DIR/wazuh-manager/filebeat.pem \
         $CERT_DIR/wazuh-dashboard/dashboard.pem; do
    echo "  $f:"
    openssl x509 -in $f -noout -issuer
done
echo ""
echo "DN del admin (debe coincidir con lo que espera la imagen Wazuh):"
openssl x509 -in $CERT_DIR/wazuh-indexer/admin.pem -noout -subject
echo ""
echo "SAN del indexer (debe incluir DNS:wazuh-indexer):"
openssl x509 -in $CERT_DIR/wazuh-indexer/indexer.pem -noout -ext subjectAltName
echo ""
echo "✓ Certificados generados. Revisa arriba que TODO es consistente."
