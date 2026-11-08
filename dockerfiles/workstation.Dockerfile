FROM ubuntu:24.04

LABEL pfg.role="victim-workstation"
LABEL pfg.version="2.0"

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Madrid

# ============================================================
# Paso 1: paquetes base. En lugar de samba, instala cifs-utils para montar recursos compartidos Samba
# ============================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
        openssh-server openssh-client \
        cifs-utils \
        auditd audispd-plugins \
        python3 python3-pip python3-cryptography \
        restic \
        curl wget \
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
    && ARCH=$(dpkg --print-architecture) \
    && curl -sO https://packages.wazuh.com/4.x/apt/pool/main/w/wazuh-agent/wazuh-agent_4.7.5-1_${ARCH}.deb \
    && WAZUH_MANAGER="wazuh-manager" \
       WAZUH_AGENT_GROUP="lab-victims" \
       apt-get install -y ./wazuh-agent_4.7.5-1_${ARCH}.deb \
    && rm wazuh-agent_4.7.5-1_${ARCH}.deb \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# Paso 3: usuario y SSH
# ============================================================
RUN useradd -m -s /bin/bash lab && \
    echo "lab:CambiaEstaPassword" | chpasswd && \
    usermod -aG sudo lab && \
    mkdir -p /var/run/sshd /home/lab/.ssh /home/lab/labprueba && \
    chown -R lab:lab /home/lab && \
    chmod 700 /home/lab/.ssh && \
    sed -i 's/#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config

# ============================================================
# Paso 4: reglas auditd
# ============================================================
# COPY lab-config/wazuh/audit-rules-victim.rules /etc/audit/rules.d/lab.rules

# ============================================================
# Paso 5: scripts
# ============================================================
COPY scripts/generate_test_files.sh /usr/local/bin/generate_test_files.sh
RUN chmod +x /usr/local/bin/generate_test_files.sh

# ============================================================
# Paso 6: entrypoint
# ============================================================
COPY scripts/workstation-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22

ENTRYPOINT ["/entrypoint.sh"]
