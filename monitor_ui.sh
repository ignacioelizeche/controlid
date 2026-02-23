#!/bin/bash

# Script de interfaz de usuario para gestionar Control ID Monitor
# Proporciona un menú interactivo para controlar el servicio

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Obtener el usuario actual
CURRENT_USER="${SUDO_USER:-$(whoami)}"
SERVICE_NAME="control-id-monitor@$CURRENT_USER"
LOG_DIR="/home/$CURRENT_USER/.local/share/control-id"
LOG_FILE="$LOG_DIR/monitor.log"

clear_and_print_header() {
    clear
    echo -e "${CYAN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}   Control ID Monitor - Panel de Control  ${CYAN}║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════╝${NC}"
    echo ""
}

print_status() {
    echo -e "${BLUE}Estado del Servicio:${NC}"

    if systemctl is-active --quiet $SERVICE_NAME; then
        echo -e "  Status: ${GREEN}✓ EN EJECUCIÓN${NC}"
        PID=$(systemctl show -p MainPID --value $SERVICE_NAME)
        echo -e "  PID: $PID"
    else
        echo -e "  Status: ${RED}✗ DETENIDO${NC}"
    fi

    if systemctl is-enabled --quiet $SERVICE_NAME; then
        echo -e "  Inicio Automático: ${GREEN}✓ HABILITADO${NC}"
    else
        echo -e "  Inicio Automático: ${YELLOW}✗ DESHABILITADO${NC}"
    fi

    echo ""
}

show_menu() {
    echo -e "${BLUE}Opciones:${NC}"
    echo ""
    echo "  1) Iniciar Monitor"
    echo "  2) Detener Monitor"
    echo "  3) Reiniciar Monitor"
    echo "  4) Ver Estado"
    echo "  5) Habilitar Inicio Automático"
    echo "  6) Deshabilitar Inicio Automático"
    echo "  7) Ver Logs (últimas 50 líneas)"
    echo "  8) Seguimiento en tiempo real (Ctrl+C para salir)"
    echo "  9) Ver Logs del Sistema (journalctl)"
    echo "  0) Salir"
    echo ""
}

execute_action() {
    case $1 in
        1)
            clear_and_print_header
            echo -e "${YELLOW}Iniciando Monitor...${NC}"
            sudo systemctl start $SERVICE_NAME
            sleep 1
            print_status
            read -p "Presiona Enter para continuar..."
            ;;
        2)
            clear_and_print_header
            echo -e "${YELLOW}Deteniendo Monitor...${NC}"
            sudo systemctl stop $SERVICE_NAME
            sleep 1
            print_status
            read -p "Presiona Enter para continuar..."
            ;;
        3)
            clear_and_print_header
            echo -e "${YELLOW}Reiniciando Monitor...${NC}"
            sudo systemctl restart $SERVICE_NAME
            sleep 2
            print_status
            read -p "Presiona Enter para continuar..."
            ;;
        4)
            clear_and_print_header
            echo -e "${YELLOW}Verificando estado del servicio...${NC}"
            echo ""
            sudo systemctl status $SERVICE_NAME --no-pager
            echo ""
            read -p "Presiona Enter para continuar..."
            ;;
        5)
            clear_and_print_header
            echo -e "${YELLOW}Habilitando inicio automático...${NC}"
            sudo systemctl enable $SERVICE_NAME
            print_status
            read -p "Presiona Enter para continuar..."
            ;;
        6)
            clear_and_print_header
            echo -e "${YELLOW}Deshabilitando inicio automático...${NC}"
            sudo systemctl disable $SERVICE_NAME
            print_status
            read -p "Presiona Enter para continuar..."
            ;;
        7)
            clear_and_print_header
            echo -e "${YELLOW}Últimas 50 líneas del log...${NC}"
            echo ""
            if [ -f "$LOG_FILE" ]; then
                tail -50 "$LOG_FILE"
            else
                echo -e "${RED}No hay logs disponibles${NC}"
            fi
            echo ""
            read -p "Presiona Enter para continuar..."
            ;;
        8)
            clear_and_print_header
            echo -e "${YELLOW}Siguiendo logs en tiempo real (Ctrl+C para salir)...${NC}"
            echo ""
            if [ -f "$LOG_FILE" ]; then
                tail -f "$LOG_FILE"
            else
                echo -e "${RED}No hay logs disponibles${NC}"
                sleep 2
            fi
            ;;
        9)
            clear_and_print_header
            echo -e "${YELLOW}Logs del sistema (Ctrl+C para salir)...${NC}"
            echo ""
            sudo journalctl -u $SERVICE_NAME -f --no-pager
            ;;
        0)
            clear
            echo -e "${GREEN}¡Hasta luego!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Opción inválida${NC}"
            sleep 2
            ;;
    esac
}

# Main loop
while true; do
    clear_and_print_header
    print_status
    show_menu
    read -p "Selecciona una opción: " CHOICE
    execute_action "$CHOICE"
done
