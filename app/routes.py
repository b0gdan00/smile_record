import re
from datetime import date, datetime, time, timedelta
from uuid import uuid4

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from .storage import (
    add_service_if_missing,
    active_doctors,
    all_doctors,
    all_services,
    appointment_datetime_key,
    appointment_doc_id,
    db,
    doctor_day_statuses,
    doctor_doc_id,
    find_appointment,
    find_doctor,
    find_patient,
    now_iso,
    patient_doc_id,
    set_doctor_day_status,
)


bp = Blueprint("main", __name__)

STATUS_LABELS = {
    "planned": "Заплановано",
    "attended": "Проведено",
    "missed": "Не прийшли",
    "cancelled": "Відмінили запис",
}

STATUS_CARD_CLASSES = {
    "attended": "bg-green-100 text-green-800 border-green-200",
    "cancelled": "bg-red-100 text-red-800 border-red-200",
    "missed": "bg-slate-300 text-slate-900 border-slate-400",
}

STATUS_BADGE_CLASSES = {
    "attended": "bg-green-600 text-slate-50",
    "cancelled": "bg-red-600 text-slate-50",
    "missed": "bg-slate-700 text-slate-50",
    "planned": "bg-slate-900 text-slate-50",
}

WEEKDAY_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
WORKDAY_START = time(hour=9)
WORKDAY_END = time(hour=18, minute=30)
DEFAULT_DURATION_MINUTES = 30
SHORT_DURATION_MINUTES = 15


def normalize_text(value):
    return (value or "").strip()


def normalize_phone(value):
    phone = re.sub(r"[^\d+]", "", value or "")
    if phone.startswith("00"):
        phone = f"+{phone[2:]}"
    if phone.startswith("380"):
        phone = f"+{phone}"
    if phone.startswith("0") and len(phone) == 10:
        phone = f"+38{phone}"
    return phone


def patient_name_and_phone(value):
    raw_value = normalize_text(value)
    phone_match = re.search(
        r"(\+?\d[\d\s().-]{7,}\d)",
        raw_value,
    )
    phone = normalize_phone(phone_match.group(1)) if phone_match else ""
    name = raw_value
    if phone_match:
        name = f"{raw_value[:phone_match.start()]} {raw_value[phone_match.end():]}"
    name = re.sub(r"\s*[·,;|]\s*", " ", name).strip()
    name = re.sub(r"\s+", " ", name)
    if not name and phone:
        name = f"Пацієнт {phone}"
    return name, phone


def parse_date(value, fallback=None):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return fallback or date.today()


def plural_uk(value, one, few, many):
    value = abs(value)
    if value % 10 == 1 and value % 100 != 11:
        return one
    if 2 <= value % 10 <= 4 and not 12 <= value % 100 <= 14:
        return few
    return many


def relative_date_label(value):
    target_date = parse_date(value, None)
    if not target_date:
        return ""

    days = (target_date - date.today()).days
    abs_days = abs(days)
    is_future = days > 0

    if days == 0:
        return "сьогодні"
    if days == 1:
        return "завтра"
    if days == -1:
        return "вчора"
    if abs_days <= 6:
        day_word = plural_uk(abs_days, "день", "дні", "днів")
        return f"через {abs_days} {day_word}" if is_future else f"{abs_days} {day_word} тому"
    if abs_days <= 13:
        return "на наступному тижні" if is_future else "минулого тижня"
    if abs_days <= 31:
        weeks = max(2, round(abs_days / 7))
        week_word = plural_uk(weeks, "тиждень", "тижні", "тижнів")
        return f"через {weeks} {week_word}" if is_future else f"{weeks} {week_word} тому"
    if abs_days <= 45:
        return "через місяць" if is_future else "минулого місяця"
    if abs_days < 365:
        months = max(2, round(abs_days / 30))
        month_word = plural_uk(months, "місяць", "місяці", "місяців")
        return f"через {months} {month_word}" if is_future else f"{months} {month_word} тому"

    years = max(1, round(abs_days / 365))
    if years == 1:
        return "через рік" if is_future else "рік тому"
    year_word = plural_uk(years, "рік", "роки", "років")
    return f"через {years} {year_word}" if is_future else f"{years} {year_word} тому"


def minutes_from_time(value):
    try:
        parsed = datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError):
        return None
    return parsed.hour * 60 + parsed.minute


def time_from_minutes(value):
    hours, minutes = divmod(value, 60)
    return f"{hours:02}:{minutes:02}"


def normalize_duration(value):
    try:
        duration = int(value)
    except (TypeError, ValueError):
        return DEFAULT_DURATION_MINUTES
    if duration == SHORT_DURATION_MINUTES:
        return SHORT_DURATION_MINUTES
    return DEFAULT_DURATION_MINUTES


def time_slots():
    slots = []
    current = datetime.combine(date.today(), WORKDAY_START)
    end = datetime.combine(date.today(), WORKDAY_END)
    while current <= end:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=30)
    return slots


def schedule_slots(appointments):
    slot_minutes = {minutes_from_time(slot) for slot in time_slots()}
    workday_start = WORKDAY_START.hour * 60 + WORKDAY_START.minute
    workday_end = WORKDAY_END.hour * 60 + WORKDAY_END.minute

    for appointment in appointments:
        if normalize_duration(appointment.get("duration_minutes")) != SHORT_DURATION_MINUTES:
            continue

        start_minutes = minutes_from_time(appointment.get("time"))
        if start_minutes is None:
            continue

        end_minutes = start_minutes + SHORT_DURATION_MINUTES
        if workday_start <= start_minutes <= workday_end:
            slot_minutes.add(start_minutes)
        if workday_start <= end_minutes <= workday_end:
            slot_minutes.add(end_minutes)

    return [time_from_minutes(value) for value in sorted(slot_minutes)]


def appointment_interval(appointment):
    start_minutes = minutes_from_time(appointment.get("time"))
    if start_minutes is None:
        return None
    return (
        start_minutes,
        start_minutes + normalize_duration(appointment.get("duration_minutes")),
    )


def slot_blocking_appointment(appointments, doctor_id, slot, ignored_appointment_id=None):
    slot_minutes = minutes_from_time(slot)
    if slot_minutes is None:
        return None

    for appointment in appointments:
        if appointment.get("doctor_id") != doctor_id:
            continue
        if ignored_appointment_id and appointment.get("id") == ignored_appointment_id:
            continue

        interval = appointment_interval(appointment)
        if not interval:
            continue
        start_minutes, end_minutes = interval
        if start_minutes < slot_minutes < end_minutes:
            return appointment
    return None


def has_appointment_overlap(appointments, candidate, ignored_appointment_id=None):
    interval = appointment_interval(candidate)
    if not interval:
        return False
    candidate_start, candidate_end = interval

    for appointment in appointments:
        if appointment.get("doctor_id") != candidate.get("doctor_id"):
            continue
        if appointment.get("date") != candidate.get("date"):
            continue
        if ignored_appointment_id and appointment.get("id") == ignored_appointment_id:
            continue

        existing_interval = appointment_interval(appointment)
        if not existing_interval:
            continue
        existing_start, existing_end = existing_interval
        if candidate_start < existing_end and candidate_end > existing_start:
            return True
    return False


def patients_sorted():
    return sorted(
        db().table("patients").all(),
        key=lambda patient: patient.get("full_name", "").lower(),
    )


def is_appointment_past(appointment):
    try:
        appointment_at = datetime.strptime(
            f"{appointment.get('date')} {appointment.get('time')}",
            "%Y-%m-%d %H:%M",
        )
    except (TypeError, ValueError):
        return False
    return appointment_at < datetime.now()


def is_slot_past(date_value, slot):
    try:
        slot_at = datetime.strptime(f"{date_value} {slot}", "%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return False
    return slot_at < datetime.now()


def is_slot_current(date_value, slot, duration_minutes):
    try:
        slot_at = datetime.strptime(f"{date_value} {slot}", "%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return False
    now = datetime.now()
    return slot_at <= now < slot_at + timedelta(minutes=duration_minutes)


def mobile_row_visible(row):
    if row["is_current"]:
        return True
    if not row["is_past"]:
        return True
    return any(cell["appointment"] for cell in row["cells"])


def appointment_payload(appointment):
    patient = find_patient(appointment.get("patient_id")) or {}
    doctor = find_doctor(appointment.get("doctor_id")) or {}
    doctor_name = doctor.get("full_name") or appointment.get("doctor") or "Лікар не знайдений"
    return {
        **appointment,
        "patient_name": patient.get("full_name", "Пацієнт не знайдений"),
        "patient_phone": patient.get("phone", ""),
        "doctor_name": doctor_name,
        "doctor": doctor_name,
        "service_name": appointment.get("service_name") or appointment.get("reason", ""),
        "duration_minutes": normalize_duration(appointment.get("duration_minutes")),
        "is_past": is_appointment_past(appointment),
        "is_closed": appointment.get("status") != "planned",
        "needs_status": appointment.get("status") == "planned"
        and is_appointment_past(appointment),
        "status_label": STATUS_LABELS.get(appointment.get("status"), "Заплановано"),
        "status_card_class": STATUS_CARD_CLASSES.get(appointment.get("status"), ""),
        "status_badge_class": STATUS_BADGE_CLASSES.get(
            appointment.get("status"),
            STATUS_BADGE_CLASSES["planned"],
        ),
    }


def previous_visit(patient_id, current_appointment_id=None):
    appointments = db().table("appointments").all()
    past = [
        item
        for item in appointments
        if item.get("patient_id") == patient_id
        and item.get("status") == "attended"
        and item.get("id") != current_appointment_id
    ]
    if not past:
        return None
    return appointment_payload(sorted(past, key=appointment_datetime_key, reverse=True)[0])


def patient_summary(patient):
    appointments = [
        appointment
        for appointment in db().table("appointments").all()
        if appointment.get("patient_id") == patient["id"]
    ]
    today_value = date.today().isoformat()
    past = [
        item
        for item in appointments
        if item.get("status") == "attended" and item.get("date", "") <= today_value
    ]
    future = [
        item
        for item in appointments
        if item.get("status") == "planned" and item.get("date", "") >= today_value
    ]
    last_visit = sorted(past, key=appointment_datetime_key, reverse=True)[0] if past else None
    next_visit = sorted(future, key=appointment_datetime_key)[0] if future else None
    last_visit_payload = appointment_payload(last_visit) if last_visit else None
    next_visit_payload = appointment_payload(next_visit) if next_visit else None
    if last_visit_payload:
        last_visit_payload["relative_label"] = relative_date_label(
            last_visit_payload.get("date")
        )
    if next_visit_payload:
        next_visit_payload["relative_label"] = relative_date_label(
            next_visit_payload.get("date")
        )
    return {
        **patient,
        "last_visit": last_visit_payload,
        "next_visit": next_visit_payload,
    }


def schedule_days(selected_date):
    start = date.today()
    appointments = db().table("appointments").all()
    today_value = date.today()
    days = []
    for index in range(31):
        current = start + timedelta(days=index)
        current_value = current.isoformat()
        days.append(
            {
                "date": current_value,
                "day": current.day,
                "label": WEEKDAY_LABELS[current.weekday()],
                "is_today": current == today_value,
                "is_selected": current == selected_date,
                "count": len(
                    [
                        item
                        for item in appointments
                        if item.get("date") == current_value
                    ]
                ),
            }
        )
    return days


def schedule_grid(selected_date, selected_doctor_id=None):
    selected_date_value = selected_date.isoformat()
    unavailable_ids = {
        item.get("doctor_id")
        for item in doctor_day_statuses(selected_date_value)
        if item.get("is_working") is False
    }
    all_active_doctors = active_doctors()
    unavailable_doctors = [
        doctor for doctor in all_active_doctors if doctor.get("id") in unavailable_ids
    ]
    doctors = [
        doctor for doctor in all_active_doctors if doctor.get("id") not in unavailable_ids
    ]
    if selected_doctor_id:
        unavailable_doctors = [
            doctor for doctor in unavailable_doctors if doctor["id"] == selected_doctor_id
        ]
        doctors = [doctor for doctor in doctors if doctor["id"] == selected_doctor_id]

    day_appointments = [
        appointment_payload(item)
        for item in db().table("appointments").all()
        if item.get("date") == selected_date_value
        and (not selected_doctor_id or item.get("doctor_id") == selected_doctor_id)
    ]
    by_slot = {
        (item.get("time"), item.get("doctor_id")): item for item in day_appointments
    }

    slots = schedule_slots(day_appointments)
    rows = []
    for index, slot in enumerate(slots):
        cells = []
        slot_is_past = is_slot_past(selected_date_value, slot)
        slot_minutes = minutes_from_time(slot)
        next_slot_minutes = (
            minutes_from_time(slots[index + 1])
            if index + 1 < len(slots)
            else None
        )
        slot_duration = (
            next_slot_minutes - slot_minutes
            if slot_minutes is not None and next_slot_minutes is not None
            else DEFAULT_DURATION_MINUTES
        )
        slot_is_current = is_slot_current(
            selected_date_value, slot, slot_duration
        )
        for doctor in doctors:
            appointment = by_slot.get((slot, doctor["id"]))
            blocked_by = None
            if not appointment:
                blocked_by = slot_blocking_appointment(
                    day_appointments, doctor["id"], slot
                )
            blocked_until = None
            if blocked_by:
                _, blocked_until_minutes = appointment_interval(blocked_by)
                blocked_until = time_from_minutes(blocked_until_minutes)
            cells.append(
                {
                    "time": slot,
                    "doctor": doctor,
                    "appointment": appointment,
                    "blocked_by": blocked_by,
                    "blocked_until": blocked_until,
                    "is_past": slot_is_past,
                    "duration_minutes": slot_duration,
                }
            )
        rows.append(
            {
                "time": slot,
                "is_past": slot_is_past,
                "is_current": slot_is_current,
                "duration_minutes": slot_duration,
                "has_appointment": any(cell["appointment"] for cell in cells),
                "cells": cells,
            }
        )
        rows[-1]["mobile_visible"] = mobile_row_visible(rows[-1])
    return (
        rows,
        doctors,
        sorted(day_appointments, key=appointment_datetime_key),
        unavailable_doctors,
    )


def default_appointment_values(selected_doctor_id=None):
    today_value = date.today()
    rows, doctors, _, _ = schedule_grid(today_value, selected_doctor_id or None)
    allowed_doctor_ids = {doctor["id"] for doctor in doctors}
    if selected_doctor_id and selected_doctor_id not in allowed_doctor_ids:
        selected_doctor_id = ""

    for row in rows:
        if row["is_past"]:
            continue
        for cell in row["cells"]:
            if selected_doctor_id and cell["doctor"]["id"] != selected_doctor_id:
                continue
            if cell["appointment"] or cell["blocked_by"]:
                continue
            return {
                "date": today_value.isoformat(),
                "time": row["time"],
                "duration_minutes": cell["duration_minutes"],
                "doctor_id": selected_doctor_id or cell["doctor"]["id"],
            }

    return {
        "date": today_value.isoformat(),
        "time": "",
        "duration_minutes": DEFAULT_DURATION_MINUTES,
        "doctor_id": selected_doctor_id or "",
    }


def base_context(active_page):
    return {
        "active_page": active_page,
        "today": date.today().isoformat(),
        "doctors": active_doctors(),
        "all_doctors": all_doctors(),
        "patients": patients_sorted(),
        "services": all_services(),
        "status_labels": STATUS_LABELS,
    }


@bp.get("/")
def index():
    return redirect(url_for("main.schedule_page"))


@bp.get("/schedule")
def schedule_page():
    selected_date = parse_date(request.args.get("date"))
    selected_doctor_id = normalize_text(request.args.get("doctor_id"))
    rows, schedule_doctors, day_appointments, unavailable_doctors = schedule_grid(
        selected_date,
        selected_doctor_id or None,
    )
    return render_template(
        "schedule.html",
        **base_context("schedule"),
        selected_date=selected_date.isoformat(),
        selected_doctor_id=selected_doctor_id,
        default_appointment=default_appointment_values(selected_doctor_id),
        days=schedule_days(selected_date),
        schedule_rows=rows,
        schedule_doctors=schedule_doctors,
        day_appointments=day_appointments,
        unavailable_doctors=unavailable_doctors,
    )


@bp.get("/patients")
def patients_page():
    enriched_patients = [patient_summary(patient) for patient in patients_sorted()]
    return render_template(
        "patients.html",
        **base_context("patients"),
        patient_summaries=enriched_patients,
    )


@bp.get("/doctors")
def doctors_page():
    return render_template(
        "doctors.html",
        **base_context("doctors"),
    )


@bp.get("/api/patients")
def patients_search():
    query = normalize_text(request.args.get("q")).lower()
    patients = patients_sorted()
    if query:
        patients = [
            patient
            for patient in patients
            if query in patient.get("full_name", "").lower()
            or query in patient.get("phone", "").lower()
        ]
    return jsonify(patients[:10])


@bp.post("/api/patients")
def create_patient():
    payload = request.get_json(force=True)
    full_name, parsed_phone = patient_name_and_phone(payload.get("full_name"))
    phone = normalize_text(payload.get("phone"))
    if not phone:
        phone = parsed_phone

    if not full_name:
        return jsonify({"error": "Вкажіть ім'я пацієнта."}), 400

    patient = {
        "id": str(uuid4()),
        "full_name": full_name,
        "phone": phone,
        "birth_date": normalize_text(payload.get("birth_date")),
        "notes": normalize_text(payload.get("notes")),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    db().table("patients").insert(patient)
    return jsonify(patient), 201


@bp.patch("/api/patients/<patient_id>")
def update_patient(patient_id):
    patient = find_patient(patient_id)
    doc_id = patient_doc_id(patient_id)
    if not patient or not doc_id:
        return jsonify({"error": "Пацієнта не знайдено."}), 404

    payload = request.get_json(force=True)
    full_name, parsed_phone = patient_name_and_phone(
        payload.get("full_name", patient.get("full_name"))
    )
    if not full_name:
        return jsonify({"error": "Вкажіть ім'я пацієнта."}), 400
    phone = normalize_text(payload.get("phone", patient.get("phone")))
    if not phone:
        phone = parsed_phone

    updates = {
        "full_name": full_name,
        "phone": phone,
        "birth_date": normalize_text(
            payload.get("birth_date", patient.get("birth_date"))
        ),
        "notes": normalize_text(payload.get("notes", patient.get("notes"))),
        "updated_at": now_iso(),
    }
    db().table("patients").update(updates, doc_ids=[doc_id])
    return jsonify({**patient, **updates})


def create_patient_from_appointment_text(value):
    full_name, phone = patient_name_and_phone(value)
    if not full_name:
        return None

    timestamp = now_iso()
    patient = {
        "id": str(uuid4()),
        "full_name": full_name,
        "phone": phone,
        "birth_date": "",
        "notes": "",
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    db().table("patients").insert(patient)
    return patient


@bp.get("/api/doctors")
def doctors_list():
    return jsonify(all_doctors())


@bp.get("/api/services")
def services_list():
    return jsonify(all_services())


@bp.post("/api/doctors")
def create_doctor():
    payload = request.get_json(force=True)
    full_name = normalize_text(payload.get("full_name"))
    if not full_name:
        return jsonify({"error": "Вкажіть ім'я лікаря."}), 400

    doctor = {
        "id": str(uuid4()),
        "full_name": full_name,
        "phone": normalize_text(payload.get("phone")),
        "notes": normalize_text(payload.get("notes")),
        "active": bool(payload.get("active", True)),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    db().table("doctors").insert(doctor)
    return jsonify(doctor), 201


@bp.patch("/api/doctors/<doctor_id>")
def update_doctor(doctor_id):
    doctor = find_doctor(doctor_id)
    doc_id = doctor_doc_id(doctor_id)
    if not doctor or not doc_id:
        return jsonify({"error": "Лікаря не знайдено."}), 404

    payload = request.get_json(force=True)
    updates = {
        "full_name": normalize_text(payload.get("full_name", doctor.get("full_name"))),
        "phone": normalize_text(payload.get("phone", doctor.get("phone"))),
        "notes": normalize_text(payload.get("notes", doctor.get("notes"))),
        "active": bool(payload.get("active")),
        "updated_at": now_iso(),
    }
    if not updates["full_name"]:
        return jsonify({"error": "Вкажіть ім'я лікаря."}), 400

    db().table("doctors").update(updates, doc_ids=[doc_id])
    return jsonify({**doctor, **updates})


@bp.post("/api/doctor-days")
def set_doctor_day():
    payload = request.get_json(force=True)
    doctor_id = normalize_text(payload.get("doctor_id"))
    work_date = normalize_text(payload.get("date"))

    if not find_doctor(doctor_id):
        return jsonify({"error": "Лікаря не знайдено."}), 404
    if not work_date:
        return jsonify({"error": "Вкажіть дату."}), 400

    status = set_doctor_day_status(
        doctor_id=doctor_id,
        work_date=work_date,
        is_working=bool(payload.get("is_working")),
    )
    return jsonify(status)


@bp.post("/api/appointments")
def create_appointment():
    payload = request.get_json(force=True)
    patient_id = normalize_text(payload.get("patient_id"))
    patient_query = normalize_text(payload.get("patient_query"))
    doctor_id = normalize_text(payload.get("doctor_id"))
    appointment_date = normalize_text(payload.get("date"))
    appointment_time = normalize_text(payload.get("time"))
    duration_minutes = normalize_duration(payload.get("duration_minutes"))

    patient = find_patient(patient_id)
    if not patient:
        patient = create_patient_from_appointment_text(patient_query)
        if not patient:
            return jsonify({"error": "Вкажіть пацієнта."}), 400
        patient_id = patient["id"]
    if not find_doctor(doctor_id):
        return jsonify({"error": "Оберіть лікаря."}), 400
    if not appointment_date or not appointment_time:
        return jsonify({"error": "Дата і час є обов'язковими."}), 400

    if is_slot_past(appointment_date, appointment_time):
        return jsonify({"error": "Не можна створити запис на минулий час."}), 400

    status = normalize_text(payload.get("status")) or "planned"
    service_name = normalize_text(payload.get("service_name"))
    appointment = {
        "id": str(uuid4()),
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "date": appointment_date,
        "time": appointment_time,
        "duration_minutes": duration_minutes,
        "service_name": service_name,
        "reason": normalize_text(payload.get("reason")),
        "comments": normalize_text(payload.get("comments")),
        "status": status,
        "visited": status == "attended",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    if has_appointment_overlap(db().table("appointments").all(), appointment):
        return jsonify({"error": "На цей час у лікаря вже є запис."}), 400
    add_service_if_missing(service_name)
    db().table("appointments").insert(appointment)
    return jsonify(appointment_payload(appointment)), 201


@bp.get("/api/appointments/<appointment_id>")
def appointment_detail(appointment_id):
    appointment = find_appointment(appointment_id)
    if not appointment:
        return jsonify({"error": "Запис не знайдено."}), 404

    patient = find_patient(appointment["patient_id"]) or {}
    doctor = find_doctor(appointment.get("doctor_id")) or {}
    last_visit = previous_visit(appointment["patient_id"], appointment_id)
    return jsonify(
        {
            "appointment": appointment_payload(appointment),
            "patient": patient,
            "doctor": doctor,
            "last_visit": last_visit,
        }
    )


@bp.patch("/api/appointments/<appointment_id>")
def update_appointment(appointment_id):
    appointment = find_appointment(appointment_id)
    doc_id = appointment_doc_id(appointment_id)
    if not appointment or not doc_id:
        return jsonify({"error": "Запис не знайдено."}), 404

    payload = request.get_json(force=True)
    doctor_id = normalize_text(payload.get("doctor_id", appointment.get("doctor_id")))
    if not find_doctor(doctor_id):
        return jsonify({"error": "Оберіть лікаря."}), 400

    status = normalize_text(payload.get("status", appointment.get("status"))) or "planned"
    service_name = normalize_text(
        payload.get("service_name", appointment.get("service_name"))
    )
    updates = {
        "doctor_id": doctor_id,
        "date": normalize_text(payload.get("date", appointment.get("date"))),
        "time": normalize_text(payload.get("time", appointment.get("time"))),
        "duration_minutes": normalize_duration(
            payload.get("duration_minutes", appointment.get("duration_minutes"))
        ),
        "service_name": service_name,
        "reason": normalize_text(payload.get("reason", appointment.get("reason"))),
        "comments": normalize_text(payload.get("comments", appointment.get("comments"))),
        "status": status,
        "visited": status == "attended",
        "updated_at": now_iso(),
    }
    if has_appointment_overlap(
        db().table("appointments").all(), {**appointment, **updates}, appointment_id
    ):
        return jsonify({"error": "На цей час у лікаря вже є запис."}), 400
    add_service_if_missing(service_name)
    db().table("appointments").update(updates, doc_ids=[doc_id])
    return jsonify(appointment_payload({**appointment, **updates}))
