#!/bin/bash

# Script para iniciar el monitor de Control ID
# Este script se ejecuta automáticamente en el startup del sistema

# Obtener el directorio del script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Variables de configuración
LOG_DIR="${HOME}/.local/share/control-id"
LOG_FILE="${LOG_DIR}/monitor.log"
PID_FILE="${LOG_DIR}/monitor.pid"

# Crear directorio de logs si no existe
mkdir -p "$LOG_DIR"

# Función para registrar eventos
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Función para comprobar si el proceso está corriendo
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Función para iniciar el monitor
start_monitor() {
    if is_running; then
        log_message "Monitor ya está en ejecución (PID: $(cat $PID_FILE))"
        return 0
    fi

    log_message "Iniciando Monitor Control ID..."

    # Activar el entorno virtual si existe
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    fi

    # Iniciar el monitor en background
    nohup python3 app.py >> "$LOG_FILE" 2>&1 &
    NEW_PID=$!
    echo $NEW_PID > "$PID_FILE"

    log_message "Monitor iniciado con PID: $NEW_PID"
    sleep 2

    if is_running; then
        log_message "Monitor iniciado correctamente"
        return 0
    else
        log_message "ERROR: Monitor falló al iniciar"
        return 1
    fi
}

# Función para detener el monitor
stop_monitor() {
    if ! is_running; then
        log_message "Monitor no está en ejecución"
        return 0
    fi

    PID=$(cat "$PID_FILE")
    log_message "Deteniendo Monitor (PID: $PID)..."

    kill $PID 2>/dev/null
    sleep 2

    if is_running; then
        log_message "Forzando parada del Monitor..."
        kill -9 $PID 2>/dev/null
    fi

    rm -f "$PID_FILE"
    log_message "Monitor detenido"
    return 0
}

# Función para reiniciar el monitor
restart_monitor() {
    stop_monitor
    sleep 2
    start_monitor
}

# Función para mostrar estado
status_monitor() {
    if is_running; then
        echo "✓ Monitor Control ID está corriendo (PID: $(cat $PID_FILE))"
        return 0
    else
        echo "✗ Monitor Control ID no está corriendo"
        return 1
    fi
}

# Main - procesar argumentos
case "${1:-start}" in
    start)
        start_monitor
        ;;
    stop)
        stop_monitor
        ;;
    restart)
        restart_monitor
        ;;
    status)
        status_monitor
        ;;
    logs)
        if [ -f "$LOG_FILE" ]; then
            tail -f "$LOG_FILE"
        else
            echo "No hay logs disponibles aún"
        fi
        ;;
    *)
        echo "Uso: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac

exit $?
