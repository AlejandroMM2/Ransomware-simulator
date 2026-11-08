#!/bin/bash
# fileserver-entrypoint.sh
# Arranque del contenedor fileserver para el laboratorio PFG.
#
# Orden de arranque:
#   1. Claves SSH para acceso del atacante
#   2. Ficheros de prueba (solo si el volumen está vacío)
#   3. Espera activa al manager Wazuh (puerto 1514)
#   4. SSH + Samba + agente Wazuh
#
# Se usa "|| true" en todos los servicios para que el contenedor
# no muera si algo falla al arrancar — el laboratorio es tolerante
# a fallos parciales durante el inicio.

echo "===> Iniciando fileserver..."

# --- Clave SSH autorizada para el usuario lab ---
# El atacante y el runner usan esta clave para conectarse.
# Se monta en /etc/ssh-keys/ como bind mount de solo lectura
# desde lab-config/ssh-keys/ en el host.
if [ -f /etc/ssh-keys/lab_authorized_keys ]; then
    cat /etc/ssh-keys/lab_authorized_keys > /home/lab/.ssh/authorized_keys
    chown lab:lab /home/lab/.ssh/authorized_keys
    chmod 600 /home/lab/.ssh/authorized_keys
fi

# --- Ficheros sintéticos ---
# Si el volumen labprueba-fs está vacío (primer arranque o volumen borrado),
# generamos 500 ficheros de distintos tipos y tamaños.
# El hash baseline sirve para verificar integridad después de restaurar.
if [ -z "$(ls -A /opt/labprueba 2>/dev/null)" ]; then
    echo "  → Volumen vacío, generando ficheros de prueba..."
    /usr/local/bin/generate_test_files.sh /opt/labprueba 500 2>/dev/null || true
    chown -R lab:lab /opt/labprueba
fi
sha256sum /opt/labprueba/* 2>/dev/null > /opt/labprueba/.hashes_baseline.csv || true

# --- Espera al manager ---
# Los agentes Wazuh no pueden registrarse si el manager no está escuchando.
# Esperamos hasta 60s antes de continuar de todas formas.
echo "  → Esperando a wazuh-manager:1514..."
for i in $(seq 1 30); do
    if (echo > /dev/tcp/wazuh-manager/1514) 2>/dev/null; then
        echo "  ✓ Manager accesible en intento $i"
        break
    fi
    sleep 2
done

# --- Servicios ---
sed -i "/imklog/s/^/#/" /etc/rsyslog.conf
service rsyslog start || true
service ssh start || true
service smbd start || true
service nmbd start || true

# auditd falla en contenedores sin privilegio completo de kernel;
# se intenta igualmente pero no es crítico (usamos FIM en su lugar)
auditctl -R /etc/audit/rules.d/lab.rules 2>/dev/null || true
service auditd start 2>/dev/null || true

/var/ossec/bin/wazuh-control start || true
echo "===> Fileserver listo"

# Mantener el contenedor vivo con tail de logs útiles
tail -f /var/log/syslog /var/log/samba/log.smbd \
        /var/ossec/logs/ossec.log 2>/dev/null || sleep infinity
