FROM ubuntu:24.04

LABEL pfg.role="restic-sftp-target"
LABEL pfg.version="2.0"

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Madrid

# ============================================================
# Paso 1: paquetes base
# ============================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
        openssh-server rsyslog \
        auditd audispd-plugins \
        curl \
        iputils-ping \
        iproute2 \
        adduser \
        lsb-release \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# Paso 2: Wazuh agent
# ============================================================
RUN apt-get update \
    && ARCH=$(dpkg --print-architecture) \
    && curl -sO https://packages.wazuh.com/4.x/apt/pool/main/w/wazuh-agent/wazuh-agent_4.7.5-1_${ARCH}.deb \
    && WAZUH_MANAGER="wazuh-manager" \
       WAZUH_AGENT_GROUP="lab-backup" \
       apt-get install -y ./wazuh-agent_4.7.5-1_${ARCH}.deb \
    && rm wazuh-agent_4.7.5-1_${ARCH}.deb \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# Paso 3: usuario dedicado para Restic B
# ============================================================
RUN useradd -m -s /bin/bash restic-b && \
    mkdir -p /srv/backups/restic-b /var/run/sshd /home/restic-b/.ssh && \
    chown -R restic-b:restic-b /srv/backups/restic-b /home/restic-b/.ssh && \
    chmod 750 /srv/backups/restic-b && \
    chmod 700 /home/restic-b/.ssh && \
    sed -i 's/#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config

# ============================================================
# Paso 4: reglas auditd para vigilar el repo (trabajos futuros)
# ============================================================
# RUN mkdir -p /etc/audit/rules.d
# COPY lab-config/wazuh/audit-rules-backup.rules /etc/audit/rules.d/lab.rules

# ============================================================
# Paso 5: entrypoint
# ============================================================
COPY scripts/restic-sftp-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22

ENTRYPOINT ["/entrypoint.sh"]
