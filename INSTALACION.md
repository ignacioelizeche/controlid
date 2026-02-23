# Control ID Monitor - Guía de Instalación Ubuntu 24.04

## Descripción
Este proyecto incluye mejoras significativas al monitor de Control ID:

1. **Reintentos automáticos**: El monitor ahora intenta reconectar automáticamente si la sesión se pierde
2. **Mejor manejo de errores**: Errores de sesión son capturados y recuperados sin necesidad de reinicio manual
3. **Systemd Service**: El monitor se ejecuta automáticamente al iniciar el sistema
4. **Logger mejorado**: Registro detallado de todas las operaciones

## Archivos Nuevos

- `monitor.py` - Monitor mejorado con reintentos y mejor gestión de errores
- `start_monitor.sh` - Script para iniciar/detener el monitor
- `install_service.sh` - Script de instalación del servicio systemd
- `monitor_ui.sh` - Interfaz gráfica (terminal) para gestionar el monitor
- `control-id-monitor.service` - Archivo de configuración del servicio systemd

## Requisitos

- Ubuntu 24.04 LTS
- Python 3.8 o superior
- Permisos de sudo para instalación

## Instalación

### Paso 1: Preparar el sistema

```bash
cd ~/Downloads/Temp/control\ ID/api
```

### Paso 2: Instalar el servicio systemd

```bash
sudo ./install_service.sh Ignacio
```

Reemplaza `Ignacio` con tu usuario si es diferente.

El script te preguntará si deseas:
1. Habilitar inicio automático ✓ (recomendado)
2. Iniciar el servicio ahora ✓ (recomendado)

### Paso 3: Verificar la instalación

```bash
sudo systemctl status control-id-monitor@Ignacio
```

## Uso

### Mediante Interface Gráfica (Recomendado)

```bash
./monitor_ui.sh
```

Esto abre un menú interactivo donde puedes:
- Iniciar/Detener el monitor
- Ver estado
- Habilitar/Deshabilitar inicio automático
- Ver logs en tiempo real

### Mediante Comandos Systemd

```bash
# Iniciar
sudo systemctl start control-id-monitor@Ignacio

# Detener
sudo systemctl stop control-id-monitor@Ignacio

# Reiniciar
sudo systemctl restart control-id-monitor@Ignacio

# Ver estado
sudo systemctl status control-id-monitor@Ignacio

# Ver logs en tiempo real
sudo journalctl -u control-id-monitor@Ignacio -f

# Habilitar inicio automático
sudo systemctl enable control-id-monitor@Ignacio

# Deshabilitar inicio automático
sudo systemctl disable control-id-monitor@Ignacio
```

### Mediante Script Manual

```bash
# Iniciar
./start_monitor.sh start

# Detener
./start_monitor.sh stop

# Reiniciar
./start_monitor.sh restart

# Ver estado
./start_monitor.sh status

# Ver logs
./start_monitor.sh logs
```

## Ubicación de Logs

Los logs se guardan en:

```
~/.local/share/control-id/monitor.log
```

Puedes verlos con:

```bash
# Últimas líneas
tail -50 ~/.local/share/control-id/monitor.log

# Seguimiento en tiempo real
tail -f ~/.local/share/control-id/monitor.log
```

## Troubleshooting

### El monitor no inicia

```bash
# Ver estado detallado
sudo systemctl status control-id-monitor@Ignacio

# Ver logs del sistema
sudo journalctl -u control-id-monitor@Ignacio -n 50

# Ver archivo de log local
tail -50 ~/.local/share/control-id/monitor.log
```

### Reiniciar completamente

```bash
# Detener
sudo systemctl stop control-id-monitor@Ignacio

# Esperar 5 segundos
sleep 5

# Iniciar
sudo systemctl start control-id-monitor@Ignacio

# Verificar
sudo systemctl status control-id-monitor@Ignacio
```

### Desinstalar (si es necesario)

```bash
# Detener el servicio
sudo systemctl stop control-id-monitor@Ignacio

# Deshabilitar
sudo systemctl disable control-id-monitor@Ignacio

# Eliminar archivo de servicio
sudo rm /etc/systemd/system/control-id-monitor@Ignacio.service

# Recargar systemd
sudo systemctl daemon-reload
```

## Mejoras Implementadas

### 1. Reintentos Automáticos
- Si la sesión se invalida, el monitor automáticamente intenta reconectarse 3 veces
- Espera 5 segundos entre reintentos

### 2. Mejor Manejo de Sesiones
- Detecta sesiones inválidas y las recupera automáticamente
- Cierra sesiones antiguas antes de abrir nuevas

### 3. Logging Mejorado
- Logs detallados de todas las operaciones
- Diferencia entre logs de debug e informativos
- Facilita troubleshooting

### 4. Monitoreo Robusto
- El servicio se reinicia automáticamente si cae
- Inicia automáticamente después de reiniciar el système
- Fácil de controlar desde terminal

## Configuración

La configuración se encuentra en `.env`. Asegúrate de tener:

```
MONITOR_URL=http://tu-url-aqui
```

## Soporte

Para más información, consulta los logs o edita los scripts anteriores según sea necesario.

---

**Instalado**: 2024
**Versión**: 1.1
