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
    && ARCH=$(dpkg --print-architecture) \
    && curl -sO https://packages.wazuh.com/4.x/apt/pool/main/w/wazuh-agent/wazuh-agent_4.7.5-1_${ARCH}.deb \
    && WAZUH_MANAGER="wazuh-manager" \
       WAZUH_AGENT_GROUP="lab-backup" \
       apt-get install -y ./wazuh-agent_4.7.5-1_${ARCH}.deb \
    && rm wazuh-agent_4.7.5-1_${ARCH}.deb \
    && rm -rf /var/lib/apt/lists/*

ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1

# ============================================================
# Paso 3: Powershell
# ============================================================

RUN apt-get update && apt-get install -y wget curl ca-certificates \
    && ARCH=$(dpkg --print-architecture) \
    && case "$ARCH" in \
         amd64) PWSH_ARCH="x64" ;; \
         arm64) PWSH_ARCH="arm64" ;; \
         *) echo "Arquitectura no soportada: $ARCH" && exit 1 ;; \
       esac \
    && wget https://github.com/PowerShell/PowerShell/releases/download/v7.4.6/powershell-7.4.6-linux-${PWSH_ARCH}.tar.gz \
    && mkdir -p /opt/microsoft/powershell/7 \
    && tar zxf powershell-7.4.6-linux-${PWSH_ARCH}.tar.gz -C /opt/microsoft/powershell/7 \
    && chmod +x /opt/microsoft/powershell/7/pwsh \
    && ln -s /opt/microsoft/powershell/7/pwsh /usr/bin/pwsh \
    && rm powershell-7.4.6-linux-${PWSH_ARCH}.tar.gz

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
