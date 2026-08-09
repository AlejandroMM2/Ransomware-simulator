#!/bin/bash
# attacker-entrypoint.sh
# Arranque del contenedor atacante.
#
# El atacante necesita la clave privada lab_runner_key para conectarse
# a fileserver y workstation sin contraseña. Esta clave se comparte con
# el host (bind mount :ro) para que experiment_runner.py también pueda
# usarla si necesita invocar comandos remotos.

echo "===> Iniciando attacker..."

if [ -f /etc/ssh-keys/lab_runner_key ]; then
    mkdir -p /root/.ssh
    cp /etc/ssh-keys/lab_runner_key /root/.ssh/id_ed25519
    chmod 600 /root/.ssh/id_ed25519
    # Registrar fingerprints de las víctimas para evitar el prompt
    # "Are you sure you want to continue connecting?" en los escenarios
    ssh-keyscan -H fileserver workstation restic-sftp \
        2>/dev/null > /root/.ssh/known_hosts || true
fi

echo "  → Esperando al manager..."
for i in $(seq 1 30); do
    if (echo > /dev/tcp/wazuh-manager/1514) 2>/dev/null; then
        break
    fi
    sleep 2
done

service ssh start 2>/dev/null || true
/var/ossec/bin/wazuh-control start 2>/dev/null || true

echo "===> Attacker listo. Los escenarios se lanzan con docker exec."
sleep infinity
