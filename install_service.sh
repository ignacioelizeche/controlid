#!/bin/bash

# Script de instalación del servicio Control ID Monitor para Ubuntu 24.04
# Uso: sudo ./install_service.sh [username]

set -e

# Obtener el usuario
if [ -z "$1" ]; then
    CURRENT_USER="${SUDO_USER:-$(whoami)}"
else
    CURRENT_USER="$1"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$SCRIPT_DIR"

echo "====================================="
echo "Instalador del Servicio Control ID Monitor"
echo "====================================="
echo "Usuario: $CURRENT_USER"
echo "Ruta API: $API_DIR"
echo ""

# Verificar que se ejecuta con permisos de sudo
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Este script debe ejecutarse con sudo"
    echo "Uso: sudo $0 [username]"
    exit 1
fi

# Verificar que el usuario existe
if ! id "$CURRENT_USER" &>/dev/null; then
    echo "ERROR: Usuario '$CURRENT_USER' no existe"
    exit 1
fi

# Copiar y configurar el service file
echo "1. Configurando el systemd service..."
SERVICE_FILE="/etc/systemd/system/control-id-monitor@$CURRENT_USER.service"

# Crear archivo temporal con rutas reemplazadas
sed "s|%CURRENT_USER%|$CURRENT_USER|g" <<EOF > /tmp/control-id-monitor.service
[Unit]
Description=Control ID Monitor Service for %CURRENT_USER%
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$API_DIR
ExecStart=/bin/bash $API_DIR/start_monitor.sh start
ExecStop=/bin/bash $API_DIR/start_monitor.sh stop
ExecReload=/bin/bash $API_DIR/start_monitor.sh restart
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment="PATH=$API_DIR/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"

[Install]
WantedBy=multi-user.target
EOF

cp /tmp/control-id-monitor.service "$SERVICE_FILE"
chmod 644 "$SERVICE_FILE"
echo "✓ Service file instalado en: $SERVICE_FILE"

# Hacer ejecutable el script start_monitor.sh
echo "2. Configurando permisos del script..."
chmod +x "$API_DIR/start_monitor.sh"
chown "$CURRENT_USER:$CURRENT_USER" "$API_DIR/start_monitor.sh"
echo "✓ Script start_monitor.sh configurado"

# Crear directorio de logs
echo "3. Creando directorio de logs..."
LOG_DIR="/home/$CURRENT_USER/.local/share/control-id"
mkdir -p "$LOG_DIR"
chown "$CURRENT_USER:$CURRENT_USER" "$LOG_DIR"
chmod 755 "$LOG_DIR"
echo "✓ Directorio de logs: $LOG_DIR"

# Recargar systemd
echo "4. Recargando systemd..."
systemctl daemon-reload
echo "✓ Systemd recargado"

# Mostrar instrucciones finales
echo ""
echo "====================================="
echo "Instalación completada"
echo "====================================="
echo ""
echo "Comandos disponibles:"
echo ""
echo "  Iniciar el servicio:"
echo "    sudo systemctl start control-id-monitor@$CURRENT_USER"
echo ""
echo "  Detener el servicio:"
echo "    sudo systemctl stop control-id-monitor@$CURRENT_USER"
echo ""
echo "  Habilitar inicio automático:"
echo "    sudo systemctl enable control-id-monitor@$CURRENT_USER"
echo ""
echo "  Ver estado del servicio:"
echo "    sudo systemctl status control-id-monitor@$CURRENT_USER"
echo ""
echo "  Ver logs en tiempo real:"
echo "    sudo journalctl -u control-id-monitor@$CURRENT_USER -f"
echo ""
echo "  Ver logs del Monitor:"
echo "    tail -f /home/$CURRENT_USER/.local/share/control-id/monitor.log"
echo ""

# Preguntar si habilitar inicio automático
read -p "¿Habilitar inicio automático al reiniciar? (s/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
    systemctl enable "control-id-monitor@$CURRENT_USER"
    echo "✓ Inicio automático habilitado"

    # Iniciar el servicio
    read -p "¿Iniciar el servicio ahora? (s/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        systemctl start "control-id-monitor@$CURRENT_USER"
        sleep 2
        systemctl status "control-id-monitor@$CURRENT_USER"
    fi
fi

echo ""
echo "La instalación ha finalizado. El servicio está listo para usar."
