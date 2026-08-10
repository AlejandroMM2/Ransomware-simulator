FROM kalilinux/kali-rolling

LABEL pfg.role="attacker"
LABEL pfg.version="2.0"

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Madrid

# ============================================================
# Paso 1: paquetes base
# ============================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
        openssh-client openssh-server \
        netcat-traditional \
        nmap \
        curl wget \
        python3 python3-pip \
        awscli \
        restic \
        iputils-ping \
        iproute2 \
        git \
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
       WAZUH_AGENT_GROUP="lab-attacker" \
       apt-get install -y ./wazuh-agent_4.7.5-1_amd64.deb \
    && rm wazuh-agent_4.7.5-1_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1

# ============================================================
# Paso 3: Powershell
# ============================================================

RUN apt-get update && apt-get install -y wget curl ca-certificates \
 && wget https://github.com/PowerShell/PowerShell/releases/download/v7.4.6/powershell-7.4.6-linux-x64.tar.gz -O /tmp/pwsh.tar.gz \
 && mkdir -p /opt/microsoft/powershell/7 \
 && tar zxf /tmp/pwsh.tar.gz -C /opt/microsoft/powershell/7 \
 && ln -s /opt/microsoft/powershell/7/pwsh /usr/bin/pwsh \
 && rm /tmp/pwsh.tar.gz

RUN pwsh -Command "Install-Module -Name powershell-yaml -Force -Scope AllUsers; \
    IEX (IWR 'https://raw.githubusercontent.com/redcanaryco/invoke-atomicredteam/master/install-atomicredteam.ps1' -UseBasicParsing); \
    Install-AtomicRedTeam -getAtomics -Force -InstallPath /root/AtomicRedTeam"


# ============================================================
# Paso 4: usuario y directorios de laboratorio
# ============================================================
RUN useradd -m -s /bin/bash lab && \
    mkdir -p /home/lab/.ssh /lab/scenarios /lab/stolen /var/log/lab && \
    chown -R lab:lab /home/lab /lab && \
    chmod 700 /home/lab/.ssh

# ============================================================
# Paso 5: entrypoint
# ============================================================
COPY scripts/attacker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
