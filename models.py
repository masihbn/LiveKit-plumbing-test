from enum import Enum
from dataclasses import dataclass
from typing import Dict


@dataclass
class UserData:
    name: str = None
    phone_number: str = None
    address: str = None
    postal_code: str = None
    reason_of_call: str = None

    def validate_reason_of_call(self, reason: str) -> bool:
        """Validate that the reason is one of the ServiceType enum values"""
        return reason in [service.value for service in ServiceType]

    def set_reason_of_call(self, reason: str) -> bool:
        """Set reason_of_call only if it's a valid ServiceType"""
        if self.validate_reason_of_call(reason):
            self.reason_of_call = reason
            return True
        return False

    def summarize(self) -> Dict:
        return {
            "customer_name": self.name or "unknown",
            "customer_phone": self.phone_number or "unknown",
            "address": self.address,
            "postal_code": self.postal_code,
            "reason_of_call": self.reason_of_call
        }


class ServiceType(Enum):
    PLUMBING = "Plumbing"
    PEST_CONTROL = "Pest Control"
    ROOFING_ISSUES = "Roofing Issues"


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
