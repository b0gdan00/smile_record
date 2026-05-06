from datetime import datetime
from pathlib import Path
from uuid import uuid4

from tinydb import Query, TinyDB


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "smile.json"

DEFAULT_SERVICES = [
    "Огляд та консультація",
    "Пломбування",
    "Професійна чистка",
    "Лікування карієсу",
    "Видалення зуба",
]


def db():
    DATA_DIR.mkdir(exist_ok=True)
    return TinyDB(DB_PATH, encoding="utf-8", ensure_ascii=False, indent=2)


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def init_storage():
    DATA_DIR.mkdir(exist_ok=True)
    database = db()
    patients = database.table("patients")
    doctors = database.table("doctors")
    doctor_days = database.table("doctor_days")
    services = database.table("services")
    appointments = database.table("appointments")

    if len(patients) == 0:
        first_patient_id = str(uuid4())
        second_patient_id = str(uuid4())
        patients.insert_multiple(
            [
                {
                    "id": first_patient_id,
                    "full_name": "Марія Савчук",
                    "phone": "+380671112233",
                    "birth_date": "1992-04-18",
                    "notes": "Чутливість до холодного.",
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                },
                {
                    "id": second_patient_id,
                    "full_name": "Андрій Бойко",
                    "phone": "+380501234567",
                    "birth_date": "",
                    "notes": "",
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                },
            ]
        )

    ensure_doctors(doctors, appointments)
    ensure_doctor_days(doctor_days)
    ensure_services(services, appointments)

    if len(appointments) == 0:
        patient_list = patients.all()
        doctor_list = active_doctors()
        if len(patient_list) >= 2 and len(doctor_list) >= 2:
            appointments.insert_multiple(
                [
                    {
                        "id": str(uuid4()),
                        "patient_id": patient_list[0]["id"],
                        "doctor_id": doctor_list[0]["id"],
                        "date": datetime.now().date().isoformat(),
                        "time": "09:30",
                        "service_name": "Огляд та консультація",
                        "reason": "Огляд та консультація",
                        "comments": "Пацієнтка просила ранковий час.",
                        "status": "planned",
                        "visited": False,
                        "created_at": now_iso(),
                        "updated_at": now_iso(),
                    },
                    {
                        "id": str(uuid4()),
                        "patient_id": patient_list[1]["id"],
                        "doctor_id": doctor_list[1]["id"],
                        "date": datetime.now().date().isoformat(),
                        "time": "12:00",
                        "service_name": "Пломбування",
                        "reason": "Пломбування",
                        "comments": "",
                        "status": "planned",
                        "visited": False,
                        "created_at": now_iso(),
                        "updated_at": now_iso(),
                    },
                ]
            )


def ensure_doctors(doctors_table, appointments_table):
    doctors_by_name = {
        item.get("full_name"): item for item in doctors_table.all() if item.get("full_name")
    }

    for appointment in appointments_table.all():
        updates = {}
        doctor_id = appointment.get("doctor_id")
        doctor_name = appointment.get("doctor")

        if not doctor_id and doctor_name:
            doctor = doctors_by_name.get(doctor_name)
            if not doctor:
                doctor = {
                    "id": str(uuid4()),
                    "full_name": doctor_name,
                    "phone": "",
                    "notes": "",
                    "active": True,
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
                doctors_table.insert(doctor)
                doctors_by_name[doctor_name] = doctor
            updates["doctor_id"] = doctor["id"]

        if "status" not in appointment:
            updates["status"] = "attended" if appointment.get("visited") else "planned"

        if updates:
            appointments_table.update(updates, doc_ids=[appointment.doc_id])


def ensure_doctor_days(doctor_days_table):
    # Touching the table is enough for TinyDB to create it lazily when needed.
    len(doctor_days_table)


def ensure_services(services_table, appointments_table):
    Service = Query()
    for service_name in DEFAULT_SERVICES:
        if not services_table.get(Service.name == service_name):
            services_table.insert(
                {
                    "id": str(uuid4()),
                    "name": service_name,
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
            )

    for appointment in appointments_table.all():
        service_name = appointment.get("service_name") or appointment.get("reason")
        if not service_name:
            continue
        if "service_name" not in appointment:
            appointments_table.update(
                {"service_name": service_name},
                doc_ids=[appointment.doc_id],
            )
        if not services_table.get(Service.name == service_name):
            services_table.insert(
                {
                    "id": str(uuid4()),
                    "name": service_name,
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
            )


def add_service_if_missing(name):
    service_name = (name or "").strip()
    if not service_name:
        return None

    Service = Query()
    services = db().table("services")
    existing = services.get(Service.name == service_name)
    if existing:
        return existing

    service = {
        "id": str(uuid4()),
        "name": service_name,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    services.insert(service)
    return service


def all_services():
    return sorted(
        db().table("services").all(),
        key=lambda service: service.get("name", "").lower(),
    )


def find_patient(patient_id):
    Patient = Query()
    return db().table("patients").get(Patient.id == patient_id)


def patient_doc_id(patient_id):
    Patient = Query()
    item = db().table("patients").get(Patient.id == patient_id)
    return item.doc_id if item else None


def find_doctor(doctor_id):
    Doctor = Query()
    return db().table("doctors").get(Doctor.id == doctor_id)


def doctor_doc_id(doctor_id):
    Doctor = Query()
    item = db().table("doctors").get(Doctor.id == doctor_id)
    return item.doc_id if item else None


def active_doctors():
    return sorted(
        [doctor for doctor in db().table("doctors").all() if doctor.get("active", True)],
        key=lambda doctor: doctor.get("full_name", "").lower(),
    )


def all_doctors():
    return sorted(
        db().table("doctors").all(),
        key=lambda doctor: doctor.get("full_name", "").lower(),
    )


def doctor_day_doc_id(doctor_id, work_date):
    DoctorDay = Query()
    item = db().table("doctor_days").get(
        (DoctorDay.doctor_id == doctor_id) & (DoctorDay.date == work_date)
    )
    return item.doc_id if item else None


def set_doctor_day_status(doctor_id, work_date, is_working):
    DoctorDay = Query()
    doctor_days = db().table("doctor_days")
    doc_id = doctor_day_doc_id(doctor_id, work_date)
    payload = {
        "doctor_id": doctor_id,
        "date": work_date,
        "is_working": bool(is_working),
        "updated_at": now_iso(),
    }
    if doc_id:
        doctor_days.update(payload, doc_ids=[doc_id])
    else:
        payload["id"] = str(uuid4())
        payload["created_at"] = now_iso()
        doctor_days.insert(payload)
    return doctor_days.get(
        (DoctorDay.doctor_id == doctor_id) & (DoctorDay.date == work_date)
    )


def doctor_day_statuses(work_date):
    return [
        item
        for item in db().table("doctor_days").all()
        if item.get("date") == work_date
    ]


def find_appointment(appointment_id):
    Appointment = Query()
    return db().table("appointments").get(Appointment.id == appointment_id)


def appointment_doc_id(appointment_id):
    Appointment = Query()
    item = db().table("appointments").get(Appointment.id == appointment_id)
    return item.doc_id if item else None


def appointment_datetime_key(appointment):
    return f"{appointment.get('date', '')} {appointment.get('time', '')}"
