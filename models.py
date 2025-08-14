from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional


class ServiceType(Enum):
    PLUMBING = "Plumbing"
    PEST_CONTROL = "Pest Control"
    ROOFING_ISSUES = "Roofing Issues"


@dataclass
class UserData:
    name: str = None
    phone_number: str = None
    address: str = None
    postal_code: str = None
    reason_of_call: ServiceType = None
    appointment_time: str = None

    def validate_reason_of_call(self, reason: str) -> bool:
        return reason in [service.value for service in ServiceType]

    def set_reason_of_call(self, reason: str) -> Optional[ServiceType]:
        for service in ServiceType:
            if service.value == reason:
                self.reason_of_call = reason
                return service
        return None

    def summarize(self) -> Dict:
        return {
            "customer_name": self.name or "unknown",
            "customer_phone": self.phone_number or "unknown",
            "address": self.address,
            "postal_code": self.postal_code,
            "reason_of_call": self.reason_of_call,
            "appointment_time": self.appointment_time
        }


class Worker:
    def __init__(self, worker_id, name, skills):
        self.worker_id = worker_id
        self.name = name
        self.skills = skills
        self.availabilities = []

    def add_availability(self, day, at):
        self.availabilities.append((day, at))

    def get_availability(self):
        return self.availabilities
