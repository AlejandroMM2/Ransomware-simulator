#!/bin/bash
# restic-sftp-entrypoint.sh
# Servidor SFTP que recibe los backups Restic de la estrategia B.
#
# El usuario restic-b tiene acceso SFTP pero no shell interactiva.
# El directorio /srv/backups/restic-b debe ser propiedad de restic-b
# o restic no puede crear el repositorio (falla con "permission denied").

echo "===> Iniciando restic-sftp..."

# Clave pública que autoriza al fileserver a conectarse como restic-b.
# Sin esta línea, restic backup desde fileserver falla con
# "Permission denied (publickey)".
if [ -f /etc/ssh-keys/restic_b_authorized_keys ]; then
    mkdir -p /home/restic-b/.ssh
    cat /etc/ssh-keys/restic_b_authorized_keys \
        > /home/restic-b/.ssh/authorized_keys
    chown restic-b:restic-b /home/restic-b/.ssh/authorized_keys
    chmod 600 /home/restic-b/.ssh/authorized_keys
fi

# Permisos del directorio de backups.
# Si se hace rm -rf en un reset o en E2, Docker recrea el directorio
# como root. Hay que devolvérselo a restic-b o el SFTP no puede escribir.
mkdir -p /srv/backups/restic-b
chown -R restic-b:restic-b /srv/backups/restic-b
chmod 750 /srv/backups/restic-b

echo "  → Esperando al manager..."
for i in $(seq 1 30); do
    if (echo > /dev/tcp/wazuh-manager/1514) 2>/dev/null; then
        break
    fi
    sleep 2
done

sed -i "/imklog/s/^/#/" /etc/rsyslog.conf
rsyslogd || true
service ssh start || true
/var/ossec/bin/wazuh-control start || true

echo "===> Restic-SFTP operativo en :22"
tail -f /var/ossec/logs/ossec.log 2>/dev/null || sleep infinity
