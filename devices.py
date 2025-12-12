import json
import os
from typing import Dict, Optional
from dataclasses import dataclass
import requests


@dataclass
class Device:
    ip: str
    login: str
    password: str
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
        self.devices: Dict[str, Device] = {}
        self.load_devices()

    def add_device(self, ip: str, login: str, password: str) -> Device:
        if ip in self.devices:
            raise ValueError(f"Device with IP {ip} already exists.")
        device = Device(ip=ip, login=login, password=password)
        self.devices[ip] = device
        self.save_devices()
        return device

    def get_device(self, ip: str) -> Device:
        if ip not in self.devices:
            raise ValueError(f"Device with IP {ip} not found.")
        return self.devices[ip]

    def remove_device(self, ip: str) -> None:
        if ip not in self.devices:
            raise ValueError(f"Device with IP {ip} not found.")
        del self.devices[ip]
        self.save_devices()

    def list_devices(self) -> list[Device]:
        return list(self.devices.values())

    def save_devices(self) -> None:
        data = {ip: device.to_dict() for ip, device in self.devices.items()}
        with open(self.storage_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    def load_devices(self) -> None:
        if os.path.exists(self.storage_file):
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for ip, device_data in data.items():
                self.devices[ip] = Device.from_dict(device_data)


# Global instance
device_manager = DeviceManager()