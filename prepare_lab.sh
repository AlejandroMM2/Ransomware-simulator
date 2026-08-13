#!/usr/bin/env bash
# =============================================================================
#  Preparación del laboratorio PFG en una máquina nueva (p.ej. Raspberry Pi)
#  Uso: sudo ./prepare_lab.sh
# =============================================================================
set -euo pipefail
 
# --- Configuración -----------------------------------------------------------
# Usuario de GitHub y token de acceso personal (PAT) con scope "repo".
# NO subas este fichero a git con los valores reales rellenos.
# Alternativa más segura: deja estas dos variables vacías y el script te las
# pedirá de forma interactiva (no quedan en el historial de bash).
GH_USER="${GH_USER:-}"
GH_TOKEN="${GH_TOKEN:-}"
 
# Nombre exacto del repositorio en GitHub — verifica que coincide con el actual
# antes de ejecutar (ha habido cambios de nombre: Ransomeware- vs Ransomware-).
REPO_OWNER="AlejandroMM2"
REPO_NAME="Ransomeware-simulator"
CLONE_DIR="pfg_contenedores"
 
# --- 0. Comprobación de privilegios ------------------------------------------
if [[ $EUID -ne 0 ]]; then
  echo "Este script necesita sudo para instalar paquetes y ajustar sysctl." >&2
  exit 1
fi
 
REAL_USER="${SUDO_USER:-$USER}"
 
# --- 1. Actualizar el sistema -------------------------------------------------
echo "==> Actualizando el sistema..."
apt update -y && apt upgrade -y
 
# --- 2. Instalar Docker y Compose v2 -----------------------------------------
echo "==> Instalando Docker y Compose v2..."
apt install -y docker.io docker-compose-v2 git curl
 
# Añadir al usuario real (no root) al grupo docker para no necesitar sudo
# en cada "docker compose ...". Requiere cerrar sesión y volver a entrar
# (o "newgrp docker") para que surta efecto.
if ! id -nG "$REAL_USER" | grep -qw docker; then
  usermod -aG docker "$REAL_USER"
  echo "    Usuario '$REAL_USER' añadido al grupo docker (requiere relogin)."
fi
 
systemctl enable --now docker
 
# --- 3. Requisito de kernel para el indexer (OpenSearch) ---------------------
echo "==> Ajustando vm.max_map_count..."
sysctl -w vm.max_map_count=262144
if ! grep -q "^vm.max_map_count" /etc/sysctl.conf; then
  echo "vm.max_map_count=262144" | tee -a /etc/sysctl.conf > /dev/null
fi
 
# --- 4. Dependencias Python para el análisis estadístico ---------------------
echo "==> Instalando dependencias Python..."
apt install -y python3-pip
pip3 install --break-system-packages scipy numpy pandas matplotlib
 
# --- 5. Clonar el repositorio -------------------------------------------------
if [[ -d "$CLONE_DIR" ]]; then
  echo "==> $CLONE_DIR ya existe, omito el clonado."
else
  if [[ -z "$GH_USER" ]]; then
    read -rp "Usuario de GitHub: " GH_USER
  fi
  if [[ -z "$GH_TOKEN" ]]; then
    read -rsp "Token de acceso (PAT, scope 'repo'): " GH_TOKEN
    echo
  fi
 
  echo "==> Clonando repositorio..."
  sudo -u "$REAL_USER" git clone \
    "https://${GH_USER}:${GH_TOKEN}@github.com/${REPO_OWNER}/${REPO_NAME}.git" \
    "$CLONE_DIR"
fi
 
chown -R "$REAL_USER":"$REAL_USER" "$CLONE_DIR"
 
# --- 6. Preparación previa al arranque ----------------------------------------
cd "$CLONE_DIR"
if [[ -f .env.example && ! -f .env ]]; then
  sudo -u "$REAL_USER" cp .env.example .env
  echo "    .env creado a partir de .env.example — revisa/edita las contraseñas antes de arrancar."
fi
sudo -u "$REAL_USER" chmod +x generate_certs.sh 2>/dev/null || true
 
echo
echo "==> Preparación completada."
echo "    Siguiente paso manual (no automatizado a propósito):"
echo "      cd $CLONE_DIR"
echo "      ./generate_certs.sh"
echo "      docker compose up -d wazuh-indexer   # esperar ~60s"
echo "      docker compose up -d"
echo
if ! id -nG "$REAL_USER" | grep -qw docker; then
  :
else
  echo "    Recuerda cerrar sesión y volver a entrar (o 'newgrp docker') para usar"
  echo "    'docker compose' sin sudo con el usuario '$REAL_USER'."
fi
