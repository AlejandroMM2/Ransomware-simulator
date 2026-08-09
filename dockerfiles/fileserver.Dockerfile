FROM ubuntu:24.04

LABEL pfg.role="victim-fileserver"
LABEL pfg.version="2.0"

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Madrid

# ============================================================
# Paso 1: paquetes base
# ============================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
        openssh-server \
        samba \
        auditd audispd-plugins \
        python3 python3-pip \
        restic \
        rsyslog \
        curl wget \
        netcat-openbsd \
        rsync \
        iputils-ping \
        iproute2 \
        sudo \
        adduser \
        lsb-release \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# Paso 2: Wazuh agent
# ============================================================
RUN apt-get update \
    && curl -sO https://packages.wazuh.com/4.x/apt/pool/main/w/wazuh-agent/wazuh-agent_4.7.5-1_amd64.deb \
    && WAZUH_MANAGER="wazuh-manager" \
       WAZUH_AGENT_GROUP="lab-victims" \
       apt-get install -y ./wazuh-agent_4.7.5-1_amd64.deb \
    && rm wazuh-agent_4.7.5-1_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# Paso 3: usuario y SSH
# ============================================================
RUN useradd -m -s /bin/bash lab && \
    echo "lab:CambiaEstaPassword" | chpasswd && \
    usermod -aG sudo lab && \
    mkdir -p /var/run/sshd /home/lab/.ssh /opt/labprueba && \
    chown -R lab:lab /home/lab /opt/labprueba && \
    chmod 700 /home/lab/.ssh && \
    sed -i 's/#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config

# ============================================================
# Paso 4: Samba
# ============================================================
COPY lab-config/samba/smb.conf /etc/samba/smb.conf

# ============================================================
# Paso 5: reglas auditd
# ============================================================
COPY lab-config/wazuh/audit-rules-victim.rules /etc/audit/rules.d/lab.rules

# ============================================================
# Paso 6: scripts helpers
# ============================================================
COPY scripts/generate_test_files.sh /usr/local/bin/generate_test_files.sh
RUN chmod +x /usr/local/bin/generate_test_files.sh

# ============================================================
# Paso 7: entrypoint
# ============================================================
COPY scripts/fileserver-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22 139 445

ENTRYPOINT ["/entrypoint.sh"]
