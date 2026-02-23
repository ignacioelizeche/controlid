# CAMBIOS TÉCNICOS - Control ID Monitor

## Resumen de Cambios en monitor.py

### 1. Importaciones Nuevas
```python
import asyncio  # Para manejo de delays en ciclos de reintentos
```

### 2. Configuración de Reintentos Globales (línea 21-22)
```python
MAX_RETRIES = 3      # Número máximo de intentos
RETRY_DELAY = 5      # Segundos entre cada intento
```

### 3. Nueva Función: `send_logs_to_monitor()`
Responsable de enviar logs a la URL del monitor con reintentos integrados.

**Cambios clave:**
- Implementa reintentos automáticos (3 intentos)
- Aumenta timeout a 30 segundos (antes: 10 segundos)
- Manejo specifico de errores httpx
- Logging detallado con `logger.debug()`

**Ubicación:** línea 157-194

### 4. Función `fetch_and_save_logs()` - Mejorada
Ahora implementa un ciclo completo de reintentos:

**Cambios:**
```python
# ANTES: Un solo intento
try:
    # código
except Exception as e:
    logger.error()

# AHORA: Múltiples intentos con delay
while retry_count < MAX_RETRIES:
    try:
        # código
    except Exception as e:
        retry_count += 1
        if retry_count < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY)
```

**Ubicación:** línea 87-155

**Mejoras específicas:**
- Verifica sesión válida con logger.info() en lugar de silent
- Maneja desconexiones de sesión sin provocar fallo total
- Pausas de 1 segundo tras logout antes de login (mejor estabilidad)
- Llama a `send_logs_to_monitor()` separado (reutilización de código)
- Logging en DEBUG cuando no hay nuevos logs (menos ruido)

### 5. Función `fetch_initial_logs()` - Mejorada
Similar a `fetch_and_save_logs()` pero para logs iniciales.

**Cambios:**
- Implementa reintentos (máximo 3 intentos)
- Manejo mejorado de errores de sesión
- Usa `send_logs_to_monitor()` si hay MONITOR_URL
- Logging estructurado: info/warning/error/debug

**Ubicación:** línea 46-85

---

## Cambios en Flujo de Control

### Antes (Problema Original)
```
Monitor inicia → Obtiene logs → Envía logs → ¿Error? → Falla silenciosa
                                                          ↓
                                                    Monitor sigue corriendo
                                                    pero NO envía logs
```

### Ahora (Solución)
```
Monitor inicia → Obtiene logs (con reintentos) → Envía logs (con reintentos)
                     ↓
        Si error, intenta 3 veces
        Aguarda 5s entre intentos
        Si falla completamente → Registra error → Continúa en siguiente ciclo
```

---

## Configuración del Servicio Systemd

### Archivo: `control-id-monitor.service`

**Configuraciones críticas:**
```ini
# Reinicia automáticamente si el proceso muere
Restart=always
RestartSec=10

# Ejecuta con el usuario especificado
User=%i

# Logs a journalctl (accesibles con journalctl)
StandardOutput=journal
StandardError=journal
```

---

## Timeouts Ajustados

| Operación | Antes | Después | Razón |
|-----------|-------|---------|-------|
| Envío de logs | 10s | 30s | Evitar timeouts en conexiones lentas |
| Entre reintentos | N/A | 5s | Dar tiempo al dispositivo a recuperarse |
| Entre logout/login | N/A | 1s | Evitar conflictos de sesión |

---

## Logging Mejorado

### Niveles de Log Usados

- **ERROR**: Fallos críticos después de agotar reintentos
- **WARNING**: Intentos fallidos pero continuables
- **INFO**: Eventos normales e importantes (logs guardados, enviados)
- **DEBUG**: Información adicional (sin nuevos logs, respuestas detalladas)

### Ejemplo de Logs

```
[INFO] Guardados 5 nuevos logs para dispositivo 1
[DEBUG] No hay nuevos logs para dispositivo 1
[WARNING] Intento 1/3 falló para dispositivo 1: Connection timeout
[WARNING] Intento 2/3 falló para dispositivo 1: Connection timeout
[ERROR] Error crítico al obtener logs para dispositivo 1 después de 3 intentos
[INFO] Enviados 5 logs a http://monitor-url
[DEBUG] Log 123 enviado con status success
```

---

## Scripts Complementarios

### start_monitor.sh
- Manejo de PID en archivo
- Funciones: start, stop, restart, status, logs
- Crea/mantiene archivo de log local
- Compatible con systemd

### install_service.sh
- Automatiza instalación de systemd service
- Crea directorios necesarios
- Configura permisos correctos
- Pregunta por inicio automático

### monitor_ui.sh
- Interface de menú interactivo en terminal
- Colores ANSI para mejor legibilidad
- Llamadas a systemctl para control
- Muestra logs en tiempo real

---

## Directorio de Configuración

```
~/.local/share/control-id/
├── monitor.log           # Log local del monitor
└── monitor.pid          # PID del proceso
```

---

## Compatibilidad

- ✓ Ubuntu 24.04 LTS
- ✓ Python 3.8+
- ✓ AsyncIO (ya usado en el proyecto)
- ✓ httpx (ya usado en el proyecto)
- ✓ APScheduler (ya usado en el proyecto)

---

## Comportamiento Esperado

### Ciclo Normal
1. Monitor inicia (crea job con APScheduler)
2. Cada minuto: obtiene logs con reintentos
3. Si tiene logs: intenta enviarlos con reintentos
4. Registra resultados en logs
5. Continúa infinitamente

### Ante Error de Sesión
1. Detecta sesión inválida
2. Hace logout (con manejo de excepciones)
3. Espera 1 segundo
4. Hace login
5. Reintenta obtener logs
6. Si falla: reintentos adicionales hasta MAX_RETRIES
7. Si persiste: registra error y continúa en siguiente ciclo

### Ante Reinicio del Sistema
1. Systemd inicia el servicio automáticamente
2. El monitor se ejecuta con el usuario configurado
3. Recupera el último timestamp de logs envíados
4. Continúa desde ese punto

---

## Monitoring del Servicio

### Ver Estado
```bash
sudo systemctl status control-id-monitor@Ignacio
```

### Ver Logs en Tiempo Real
```bash
sudo journalctl -u control-id-monitor@Ignacio -f
```

### Ver Logs Históricos
```bash
sudo journalctl -u control-id-monitor@Ignacio --since "24 hours ago"
```

---

## Modificaciones Futuras Posibles

Si necesitas ajustar:

1. **Número de reintentos:**
   ```python
   MAX_RETRIES = 5  # Cambiar este número
   ```

2. **Tiempo entre reintentos:**
   ```python
   RETRY_DELAY = 10  # Cambiar este número
   ```

3. **Timeout de conexión:**
   ```python
   response = await client.post(..., timeout=60.0)  # Cambiar timeout
   ```

4. **Frecuencia de polling:**
   ```python
   IntervalTrigger(minutes=2)  # Cambiar de 1 a 2 minutos, por ejemplo
   ```

Luego, reinicia:
```bash
sudo systemctl restart control-id-monitor@Ignacio
```

---

## Testing Recomendado

Para verificar que funciona correctamente:

1. **Verificar logs iniciales:**
   ```bash
   tail -20 ~/.local/share/control-id/monitor.log
   ```

2. **Simular desconexión de red:**
   - Desconecta temporalmente la red
   - Verifica que intenta reconectar
   - Verifica que continúa cuando hay conexión

3. **Revisar que reinicia correctamente:**
   ```bash
   sudo systemctl restart control-id-monitor@Ignacio
   sleep 2
   sudo systemctl status control-id-monitor@Ignacio
   ```

4. **Monitorear durante 24 horas:**
   - Verifica que continúa enviando logs
   - Revisa los logs para mensajes de reintentos
   - Confirma que no hay aumentos de consumo de memoria
