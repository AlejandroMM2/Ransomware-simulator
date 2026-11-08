#!/bin/bash
# workstation-entrypoint.sh
# Arranque de la workstation (víctima secundaria, objetivo de E3).
#
# Genera menos ficheros que el fileserver (300 vs 500) porque
# la workstation es principalmente el destino del salto lateral,
# no el objetivo del cifrado.

echo "===> Iniciando workstation..."

if [ -f /etc/ssh-keys/lab_authorized_keys ]; then
    cat /etc/ssh-keys/lab_authorized_keys > /home/lab/.ssh/authorized_keys
    chown lab:lab /home/lab/.ssh/authorized_keys
    chmod 600 /home/lab/.ssh/authorized_keys
fi

if [ -z "$(ls -A /home/lab/labprueba 2>/dev/null)" ]; then
    /usr/local/bin/generate_test_files.sh /home/lab/labprueba 300 \
        2>/dev/null || true
    chown -R lab:lab /home/lab/labprueba
fi
sha256sum /home/lab/labprueba/* 2>/dev/null \
    > /home/lab/labprueba/.hashes_baseline.csv || true

echo "  → Esperando al manager..."
for i in $(seq 1 30); do
    if (echo > /dev/tcp/wazuh-manager/1514) 2>/dev/null; then
        break
    fi
    sleep 2
done

sed -i "/imklog/s/^/#/" /etc/rsyslog.conf
service rsyslog start || true
service ssh start || true
# auditd falla por capabilities; sin impacto porque usamos FIM
auditctl -R /etc/audit/rules.d/lab.rules 2>/dev/null || true
service auditd start 2>/dev/null || true
/var/ossec/bin/wazuh-control start || true

echo "===> Workstation operativa"
tail -f /var/log/syslog /var/ossec/logs/ossec.log 2>/dev/null \
    || sleep infinity
