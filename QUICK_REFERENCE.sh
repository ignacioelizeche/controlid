#!/bin/bash
# REFERENCIA RÁPIDA - Control ID Monitor

# INSTALACIÓN (ejecutar una sola vez):
# cd ~/Downloads/Temp/control\ ID/api
# sudo ./install_service.sh Ignacio

# INTERFAZ GRÁFICA (RECOMENDADO - ejecutar siempre):
./monitor_ui.sh

# COMANDOS RÁPIDOS:
# Iniciar:      sudo systemctl start control-id-monitor@Ignacio
# Detener:      sudo systemctl stop control-id-monitor@Ignacio
# Reiniciar:    sudo systemctl restart control-id-monitor@Ignacio
# Estado:       sudo systemctl status control-id-monitor@Ignacio
# Logs (tiempo real): tail -f ~/.local/share/control-id/monitor.log
# Logs (journalctl):  sudo journalctl -u control-id-monitor@Ignacio -f
# Habilitar auto:    sudo systemctl enable control-id-monitor@Ignacio
# Deshabilitar auto: sudo systemctl disable control-id-monitor@Ignacio

# Ver archivo completo (INSTALACION.md):
# cat ~/Downloads/Temp/control\ ID/api/INSTALACION.md
