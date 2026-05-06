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
    "missed": "bg-orange-100 text-orange-800 border-orange-200",
}

STATUS_BADGE_CLASSES = {
    "attended": "bg-green-600 text-slate-50",
    "cancelled": "bg-red-600 text-slate-50",
    "missed": "bg-orange-500 text-slate-900",
    "planned": "bg-slate-900 text-slate-50",
}

WEEKDAY_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]


def normalize_text(value):
    return (value or "").strip()


def parse_date(value, fallback=None):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return fallback or date.today()


def time_slots():
    slots = []
    current = datetime.combine(date.today(), time(hour=9))
    end = datetime.combine(date.today(), time(hour=18, minute=30))
    while current <= end:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=30)
    return slots


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
    return {
        **patient,
        "last_visit": appointment_payload(last_visit) if last_visit else None,
        "next_visit": appointment_payload(next_visit) if next_visit else None,
    }


def schedule_days(selected_date):
    start = selected_date - timedelta(days=selected_date.weekday())
    appointments = db().table("appointments").all()
    today_value = date.today()
    days = []
    for index in range(7):
        current = start + timedelta(days=index)
        current_value = current.isoformat()
        days.append(
            {
                "date": current_value,
                "day": current.day,
                "label": WEEKDAY_LABELS[index],
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

    rows = []
    for slot in time_slots():
        cells = []
        for doctor in doctors:
            cells.append(
                {
                    "time": slot,
                    "doctor": doctor,
                    "appointment": by_slot.get((slot, doctor["id"])),
                }
            )
        rows.append({"time": slot, "cells": cells})
    return (
        rows,
        doctors,
        sorted(day_appointments, key=appointment_datetime_key),
        unavailable_doctors,
    )


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
    full_name = normalize_text(payload.get("full_name"))
    phone = normalize_text(payload.get("phone"))

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
    doctor_id = normalize_text(payload.get("doctor_id"))
    appointment_date = normalize_text(payload.get("date"))
    appointment_time = normalize_text(payload.get("time"))

    if not find_patient(patient_id):
        return jsonify({"error": "Оберіть пацієнта зі списку або додайте нового."}), 400
    if not find_doctor(doctor_id):
        return jsonify({"error": "Оберіть лікаря."}), 400
    if not appointment_date or not appointment_time:
        return jsonify({"error": "Дата і час є обов'язковими."}), 400

    status = normalize_text(payload.get("status")) or "planned"
    service_name = normalize_text(payload.get("service_name"))
    add_service_if_missing(service_name)
    appointment = {
        "id": str(uuid4()),
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "date": appointment_date,
        "time": appointment_time,
        "service_name": service_name,
        "reason": normalize_text(payload.get("reason")),
        "comments": normalize_text(payload.get("comments")),
        "status": status,
        "visited": status == "attended",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
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
    add_service_if_missing(service_name)
    updates = {
        "doctor_id": doctor_id,
        "date": normalize_text(payload.get("date", appointment.get("date"))),
        "time": normalize_text(payload.get("time", appointment.get("time"))),
        "service_name": service_name,
        "reason": normalize_text(payload.get("reason", appointment.get("reason"))),
        "comments": normalize_text(payload.get("comments", appointment.get("comments"))),
        "status": status,
        "visited": status == "attended",
        "updated_at": now_iso(),
    }
    db().table("appointments").update(updates, doc_ids=[doc_id])
    return jsonify(appointment_payload({**appointment, **updates}))
