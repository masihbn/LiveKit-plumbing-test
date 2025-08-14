"""
Fake database class
Ideally we'd have a SQL database here to get the data from a table properly
"""
from datetime import date, time
from typing import Tuple, List

from models import Worker, ServiceType


prompts = {
    'greetings':
        f"You're a respectful voice agents who receives calls from clients who want to set an appointment for one of your company's services.\n"
        f"These services include {[e.value for e in ServiceType]}.\n"
        f"Start by asking how you can help the client.\n"
        f"If client tries to ask irrelevant questions, kindly ask to report which one of the services he/she is looking for and lead the conversation.\n"
        f"Speak like a human, don't use phrases like \"You're information has been corrected\". Talk friendly.\n"
        f"When the user appears done OR asks to end, you MUST call the tool `final_double_check` to confirm all details. "
        f"Only after the user confirms, say goodbye (or call end_call)."
}


class WorkersTable:
    @staticmethod
    def _get_workers():
        """Just a fake static DB of workers and their free time"""
        masih = Worker(0, "Masih", [ServiceType.PLUMBING, ServiceType.PEST_CONTROL])
        ali = Worker(1, "Ali", [ServiceType.PLUMBING, ServiceType.ROOFING_ISSUES])

        # Add times
        masih.add_availability(date(2025, 8, 21), time(16, 0))
        masih.add_availability(date(2025, 8, 21), time(17, 0))
        masih.add_availability(date(2025, 8, 22), time(10, 0))
        masih.add_availability(date(2025, 8, 22), time(12, 0))

        ali.add_availability(date(2025, 8, 22), time(12, 0))
        ali.add_availability(date(2025, 8, 23), time(18, 0))
        ali.add_availability(date(2025, 8, 23), time(11, 0))

        return [masih, ali]

    @staticmethod
    def get_next_free_worker(appointment_time: Tuple) -> Worker:
        """Returns the first next free worker for the specified time """
        for worker in WorkersTable._get_workers():
            if appointment_time in worker.get_availability():
                return worker

        return None

    @staticmethod
    def get_all_availabilities(skill: ServiceType) -> List[Tuple]:
        """Returns all the available times for workers with the given skill."""
        slots = {slot for w in WorkersTable._get_workers() if skill in w.skills for slot in w.get_availability()}

        return sorted(slots, key=lambda s: (s[0], s[1]))


if __name__ == '__main__':
    a = WorkersTable.get_all_availabilities(ServiceType.PEST_CONTROL)
    nw = WorkersTable.get_next_free_worker(a[0])

    pass
