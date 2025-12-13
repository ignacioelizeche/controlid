import json
import os
from typing import Dict, Optional
from dataclasses import dataclass
import requests


@dataclass
class Device:
    id: int
    name: str
    ip: str
    login: str
    password: str
    device_id: Optional[int] = None
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, str]:
        return {
            "ip": self.ip,
            "login": self.login,
            "password": self.password
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'Device':
        return cls(
            ip=data["ip"],
            login=data["login"],
            password=data["password"]
        )


class DeviceManager:
    def __init__(self, storage_file: str = "devices.json"):
        self.storage_file = storage_file
        self.devices: Dict[int, Device] = {}
        self.next_id = 1
        self.load_devices()

    def add_device(self, name: str, ip: str, login: str, password: str) -> Device:
        device = Device(id=self.next_id, name=name, ip=ip, login=login, password=password)
        self.devices[self.next_id] = device
        self.next_id += 1
        self.save_devices()
        return device

    def get_device(self, device_id: int) -> Device:
        if device_id not in self.devices:
            raise ValueError(f"Device with ID {device_id} not found.")
        return self.devices[device_id]

    def remove_device(self, device_id: int) -> None:
        if device_id not in self.devices:
            raise ValueError(f"Device with ID {device_id} not found.")
        del self.devices[device_id]
        self.save_devices()

    def list_devices(self) -> list[Device]:
        return list(self.devices.values())

    def save_devices(self) -> None:
        data = {device.id: {"id": device.id, "name": device.name, "ip": device.ip, "login": device.login, "password": device.password, "device_id": device.device_id} for device in self.devices.values()}
        with open(self.storage_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    def load_devices(self) -> None:
        if os.path.exists(self.storage_file):
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for device_data in data.values():
                device = Device(**device_data)
                self.devices[device.id] = device
                if device.id >= self.next_id:
                    self.next_id = device.id + 1


# Global instance
device_manager = DeviceManager()