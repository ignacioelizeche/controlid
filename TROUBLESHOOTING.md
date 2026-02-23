# TROUBLESHOOTING - Control ID Monitor

## Problema: El monitor no envía logs después de cierto tiempo

### Causa
La sesión con el dispositivo Control ID se invalida y el código anterior no la recuperaba automáticamente.

### Solución
✓ **RESUELTA** - El nuevo `monitor.py` ahora:
- Detecta sesiones inválidas automáticamente
- Intenta reconectar hasta 3 veces
- Aguarda 5 segundos entre reintentos
- Continúa enviando logs sin necesidad de intervención manual

---

## Problema: El sistema se reinicia y el monitor no arranca

### Causa
No hay un servicio systemd configurado para auto-inicio.

### Solución
✓ **RESUELTA** - Sigue estos pasos:

1. Ejecuta el instalador:
   ```bash
   cd ~/Downloads/Temp/control\ ID/api
   sudo ./install_service.sh Ignacio
   ```

2. Habilita el inicio automático:
   ```bash
   sudo systemctl enable control-id-monitor@Ignacio
   ```

3. Verifica que está habilitado:
   ```bash
   sudo systemctl is-enabled control-id-monitor@Ignacio
   ```
   Debería mostrar: `enabled`

---

## Problema: Necesito reiniciar manualmente el monitor

### Causa
El servicio systemd no está reiniciando automáticamente cuando falla.

### Solución
✓ **RESUELTA** - El servicio está configurado con:
- `Restart=always` - Se reinicia automáticamente si falla
- `RestartSec=10` - Espera 10 segundos antes de reintentar

Para forzar un reinicio manual:
```bash
sudo systemctl restart control-id-monitor@Ignacio
```

---

## Problema: No sé si el monitor está corriendo

### Solución
Usa la interfaz gráfica:
```bash
./monitor_ui.sh
```

Selecciona opción `4) Ver Estado`

O verifica con systemd:
```bash
sudo systemctl status control-id-monitor@Ignacio
```

---

## Problema: Los logs no se guardan

### Solución
Comprueba el directorio de logs:
```bash
mkdir -p ~/.local/share/control-id
ls -la ~/.local/share/control-id/
```

Si no existen pero el monitor está corriendo, verifica los permisos:
```bash
chmod 755 ~/.local/share/control-id
```

Ver los últimos logs:
```bash
tail -50 ~/.local/share/control-id/monitor.log
```

---

## Problema: El monitor arranca pero se detiene inmediatamente

### Causa
Posible error en las dependencias de Python o en el .env

### Solución
1. Verifica el .env:
   ```bash
   cat .env
   ```
   Debe tener `MONITOR_URL` configurado

2. Verifica las dependencias:
   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Intenta ejecutar directamente:
   ```bash
   cd ~/Downloads/Temp/control\ ID/api
   source .venv/bin/activate
   python3 app.py
   ```

4. Verifica los errores en los logs del sistema:
   ```bash
   sudo journalctl -u control-id-monitor@Ignacio -n 100
   ```

---

## Problema: El monitor consume muchos recursos

### Causa
Posible bucle infinito o conexiones no cerradas.

### Solución
1. Detén el monitor:
   ```bash
   sudo systemctl stop control-id-monitor@Ignacio
   ```

2. Espera 10 segundos

3. Reinicia:
   ```bash
   sudo systemctl start control-id-monitor@Ignacio
   ```

4. Si persiste, revisa los logs:
   ```bash
   tail -100 ~/.local/share/control-id/monitor.log
   ```

---

## Problema: El monitor está corriendo pero no responde

### Causa
Podría estar en un estado de bloqueo o conexión colgada.

### Solución
Mata el proceso y reinicia:
```bash
sudo systemctl kill -s 9 control-id-monitor@Ignacio
sudo systemctl start control-id-monitor@Ignacio
```

---

## Problema: INSTALACIÓN - El script install_service.sh falla

### Causa
Permisos insuficientes o usuario incorrecto.

### Solución
1. Ejecuta con tu usuario correcto:
   ```bash
   sudo ./install_service.sh $(whoami)
   ```

2. O especifica el usuario explícitamente:
   ```bash
   sudo ./install_service.sh Ignacio
   ```

3. Verifica que tienes sudo configurado correctamente:
   ```bash
   sudo whoami
   ```

---

## Problema: Desinstalar completamente

### Solución
```bash
# Detener el servicio
sudo systemctl stop control-id-monitor@Ignacio

# Deshabilitar
sudo systemctl disable control-id-monitor@Ignacio

# Eliminar el archivo de servicio
sudo rm /etc/systemd/system/control-id-monitor@Ignacio.service

# Recargar systemd daemon
sudo systemctl daemon-reload

# Limpiar logs (opcional)
rm -rf ~/.local/share/control-id
```

---

## Logs Útiles

### Ver logs del monitor (archivo local):
```bash
tail -f ~/.local/share/control-id/monitor.log
```

### Ver logs del sistema (journalctl):
```bash
# Últimas 50 líneas
sudo journalctl -u control-id-monitor@Ignacio -n 50

# Tiempo real
sudo journalctl -u control-id-monitor@Ignacio -f

# Desde las últimas 2 horas
sudo journalctl -u control-id-monitor@Ignacio --since "2 hours ago"
```

### Ver logs con más detalle (DEBUG):
```bash
sudo journalctl -u control-id-monitor@Ignacio -o verbose
```

---

## Configuración de Reintentos

En `monitor.py`, línea 21-22:
```python
MAX_RETRIES = 3      # Número de intentos (cambiar este número)
RETRY_DELAY = 5      # Segundos entre intentos
```

Para cambiar estos valores:
1. Edita `monitor.py`
2. Modifica las líneas anteriores
3. Reinicia con: `sudo systemctl restart control-id-monitor@Ignacio`

---

## Contacto y Soporte

Para más ayuda:
1. Revisa los logs completos: `tail -100 ~/.local/share/control-id/monitor.log`
2. Verifica el estado del sistema: `sudo systemctl status control-id-monitor@Ignacio`
3. Lee la guía de instalación: `INSTALACION.md`
