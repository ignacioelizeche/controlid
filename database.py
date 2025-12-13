import sqlite3
import os
from typing import List, Optional
from objects import AccessLog

DB_FILE = "access_logs.db"

def init_db():
    """Inicializa la base de datos y crea la tabla si no existe."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY,
            time INTEGER,
            event INTEGER,
            device_id INTEGER,
            identifier_id INTEGER,
            user_id INTEGER,
            portal_id INTEGER,
            identification_rule_id INTEGER,
            qrcode_value TEXT,
            pin_value TEXT,
            card_value INTEGER,
            confidence INTEGER,
            mask INTEGER,
            log_type_id INTEGER,
            component_id INTEGER,
            device_internal_id INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def get_last_log_id(device_internal_id: int) -> Optional[int]:
    """Obtiene el último ID de log guardado para el dispositivo."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(id) FROM access_logs WHERE device_internal_id = ?", (device_internal_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result and result[0] else None

def save_logs(logs: List[AccessLog], device_internal_id: int):
    """Guarda los logs en la base de datos, evitando duplicados."""
    if not logs:
        return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    for log in logs:
        # Verificar si ya existe
        cursor.execute("SELECT id FROM access_logs WHERE id = ? AND device_internal_id = ?", (log.id, device_internal_id))
        if cursor.fetchone():
            continue  # Ya existe
        cursor.execute('''
            INSERT INTO access_logs (id, time, event, device_id, identifier_id, user_id, portal_id, identification_rule_id, qrcode_value, pin_value, card_value, confidence, mask, log_type_id, component_id, device_internal_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (log.id, log.time, log.event, log.device_id, log.identifier_id, log.user_id, log.portal_id, log.identification_rule_id, log.qrcode_value, log.pin_value, log.card_value, log.confidence, log.mask, log.log_type_id, log.component_id, device_internal_id))
    conn.commit()
    conn.close()

def get_new_logs(device_internal_id: int, last_id: Optional[int]) -> List[AccessLog]:
    """Obtiene logs nuevos desde la base de datos (para debug)."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if last_id:
        cursor.execute("SELECT * FROM access_logs WHERE device_internal_id = ? AND id > ?", (device_internal_id, last_id))
    else:
        cursor.execute("SELECT * FROM access_logs WHERE device_internal_id = ?", (device_internal_id,))
    rows = cursor.fetchall()
    conn.close()
    logs = []
    for row in rows:
        logs.append(AccessLog(
            id=row[0], time=row[1], event=row[2], device_id=row[3], identifier_id=row[4], user_id=row[5],
            portal_id=row[6], identification_rule_id=row[7], qrcode_value=row[8], pin_value=row[9],
            card_value=row[10], confidence=row[11], mask=row[12], log_type_id=row[13], component_id=row[14]
        ))
    return logs