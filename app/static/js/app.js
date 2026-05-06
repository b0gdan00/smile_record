const modalMap = new Map(
  [...document.querySelectorAll(".modal")].map((modal) => [modal.id, modal])
);
const scheduleDoctorStorageKey = "smile:selectedDoctorId";

function isMobileViewport() {
  return window.matchMedia("(max-width: 767px)").matches;
}

function rememberScheduleDoctor() {
  const schedule = document.querySelector("[data-schedule-date]");
  const doctorSelect = document.querySelector("#scheduleDoctorFilter");
  if (!isMobileViewport()) return;
  if (!schedule || !doctorSelect) return;

  if (doctorSelect.value) {
    localStorage.setItem(scheduleDoctorStorageKey, doctorSelect.value);
  }
}

function restoreScheduleDoctor() {
  const schedule = document.querySelector("[data-schedule-date]");
  const doctorSelect = document.querySelector("#scheduleDoctorFilter");
  if (!isMobileViewport()) {
    const url = new URL(window.location.href);
    if (url.searchParams.has("doctor_id")) {
      url.searchParams.delete("doctor_id");
      window.location.replace(url.toString());
    }
    return;
  }
  if (!schedule || !doctorSelect) return;
  if (doctorSelect.value) {
    localStorage.setItem(scheduleDoctorStorageKey, doctorSelect.value);
    return;
  }

  const savedDoctorId = localStorage.getItem(scheduleDoctorStorageKey);
  if (!savedDoctorId) return;
  const optionExists = [...doctorSelect.options].some(
    (option) => option.value === savedDoctorId
  );
  if (!optionExists) {
    localStorage.removeItem(scheduleDoctorStorageKey);
    return;
  }

  const url = new URL(window.location.href);
  url.searchParams.set("doctor_id", savedDoctorId);
  window.location.replace(url.toString());
}

function minutesFromTime(value) {
  const [hours, minutes] = value.split(":").map(Number);
  return hours * 60 + minutes;
}

function padTimePart(value) {
  return String(value).padStart(2, "0");
}

function updatePastEmptySlots(currentDate, currentMinutes) {
  document.querySelectorAll(".schedule-empty").forEach((slot) => {
    const slotDate = slot.dataset.date;
    const slotMinutes = minutesFromTime(slot.dataset.time);
    const isPast =
      slotDate < currentDate ||
      (slotDate === currentDate && slotMinutes <= currentMinutes);

    slot.disabled = isPast;
    slot.setAttribute("aria-disabled", isPast ? "true" : "false");
    slot.classList.toggle("cursor-not-allowed", isPast);
    slot.classList.toggle("bg-slate-100", isPast);
    slot.classList.toggle("text-slate-400", isPast);
  });
}

function updateMobileScheduleRows(scheduleDate, currentDate, currentMinutes) {
  document.querySelectorAll("[data-mobile-schedule] .schedule-time-row").forEach((row) => {
    const rowMinutes = minutesFromTime(row.dataset.time);
    const duration = Number(row.dataset.duration || 30);
    const hasAppointment = row.dataset.hasAppointment === "true";
    const isCurrent =
      scheduleDate === currentDate &&
      currentMinutes >= rowMinutes &&
      currentMinutes < rowMinutes + duration;
    const isPast =
      scheduleDate < currentDate ||
      (scheduleDate === currentDate && rowMinutes < currentMinutes);
    const isVisible = isCurrent || !isPast || hasAppointment;

    row.classList.toggle("hidden", !isVisible);
    const rowCard = row.querySelector("[data-mobile-row-card]");
    rowCard?.classList.toggle("ring-2", isCurrent);
    rowCard?.classList.toggle("ring-slate-900", isCurrent);
    row.querySelectorAll("[data-mobile-past-empty]").forEach((cell) => {
      cell.classList.toggle("hidden", isPast && !isCurrent);
    });
    row.dataset.mobileVisible = isVisible ? "true" : "false";
  });
}

function updateCurrentTimeMarker() {
  const schedule = document.querySelector("[data-schedule-date]");
  const badge = document.querySelector("#currentTimeBadge");
  if (!schedule || !badge) return;

  const now = new Date();
  const currentDate = [
    now.getFullYear(),
    padTimePart(now.getMonth() + 1),
    padTimePart(now.getDate()),
  ].join("-");
  const currentTime = `${padTimePart(now.getHours())}:${padTimePart(now.getMinutes())}`;
  const isSelectedToday = schedule.dataset.scheduleDate === currentDate;
  const currentMinutes = now.getHours() * 60 + now.getMinutes();

  updatePastEmptySlots(currentDate, currentMinutes);
  updateMobileScheduleRows(schedule.dataset.scheduleDate, currentDate, currentMinutes);

  badge.textContent = `Поточний час: ${currentTime}`;
  badge.classList.toggle("hidden", !isSelectedToday);

  document.querySelectorAll(".schedule-time-row").forEach((row) => {
    row.classList.remove("bg-slate-200");
  });

  if (!isSelectedToday) return;

  let activeRow = null;
  document.querySelectorAll(".schedule-time-row").forEach((row) => {
    const rowMinutes = minutesFromTime(row.dataset.time);
    if (currentMinutes >= rowMinutes && currentMinutes < rowMinutes + 30) {
      activeRow = row;
    }
  });

  activeRow?.classList.add("bg-slate-200");
}

function openModal(id) {
  const modal = modalMap.get(id);
  if (!modal) return;
  modal.classList.remove("hidden");
  modal.classList.add("flex");
}

function closeModal(modal) {
  if (!modal) return;
  modal.classList.add("hidden");
  modal.classList.remove("flex");
}

function formData(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  for (const checkbox of form.querySelectorAll('input[type="checkbox"]')) {
    data[checkbox.name] = checkbox.checked;
  }
  return data;
}

function showMessage(form, message) {
  const node = form?.querySelector("[data-form-message]");
  if (!node) return;
  node.textContent = message;
  node.classList.remove("hidden");
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Помилка збереження.");
  }
  return payload;
}

function appointmentCardHtml(appointment) {
  return `
    <div class="flex items-start justify-between gap-3">
      <div>
        <p class="text-sm font-semibold"></p>
        <h2 class="mt-1 text-lg font-semibold"></h2>
      </div>
      <span class="rounded-md bg-slate-900 px-2 py-1 text-xs font-medium text-slate-50"></span>
    </div>
    <p class="mt-2 text-sm"></p>
    <p class="mt-1 text-sm"></p>
  `;
}

const appointmentColorClasses = [
  "bg-slate-900",
  "bg-slate-200",
  "bg-green-100",
  "bg-red-100",
  "bg-slate-300",
  "text-slate-50",
  "text-slate-900",
  "text-green-800",
  "text-red-800",
  "text-slate-900",
  "border-green-200",
  "border-red-200",
  "border-slate-400",
  "border-2",
  "border-slate-700",
];

const badgeColorClasses = [
  "bg-slate-900",
  "bg-green-600",
  "bg-red-600",
  "bg-slate-700",
  "text-slate-50",
  "text-slate-900",
];

function statusCardClass(appointment) {
  if (appointment.status_card_class) return appointment.status_card_class;
  if (appointment.needs_status) return "border-2 border-slate-700 bg-slate-200 text-slate-900";
  if (appointment.is_past) return "bg-slate-200 text-slate-900";
  return "bg-slate-900 text-slate-50";
}

function appointmentDurationLabel(appointment) {
  return `${appointment.duration_minutes || 30} хв`;
}

function appointmentMetaText(appointment) {
  return `${appointment.date} · ${appointment.time} · ${appointmentDurationLabel(appointment)}`;
}

function fillAppointmentCard(card, appointment) {
  const paragraphs = card.querySelectorAll("p");
  paragraphs[0].textContent = appointmentMetaText(appointment);
  card.querySelector("h2").textContent = appointment.patient_name;
  card.classList.remove(...appointmentColorClasses);
  card.classList.add(...statusCardClass(appointment).split(" "));
  const badge = card.querySelector("span");
  badge.textContent = appointment.status_label || "Заплановано";
  badge.classList.remove(...badgeColorClasses);
  badge.classList.add(...(appointment.status_badge_class || "bg-slate-900 text-slate-50").split(" "));
  paragraphs[1].textContent = appointment.doctor_name || appointment.doctor || "";
  paragraphs[2].textContent =
    appointment.service_name || appointment.reason || "Без причини візиту";
}

function addServiceOption(serviceName) {
  const cleanName = (serviceName || "").trim();
  const datalist = document.querySelector("#servicesDatalist");
  if (!cleanName || !datalist) return;
  const exists = [...datalist.options].some((option) => option.value === cleanName);
  if (exists) return;
  const option = document.createElement("option");
  option.value = cleanName;
  datalist.append(option);
}

function addAppointmentCard(appointment) {
  const list = document.querySelector("#appointmentList");
  if (!list) return;
  const button = document.createElement("button");
  button.className = "appointment-card w-full rounded-lg border border-slate-200 p-4 text-left";
  button.dataset.appointmentId = appointment.id;
  button.innerHTML = appointmentCardHtml(appointment);
  fillAppointmentCard(button, appointment);
  list.prepend(button);
}

function updateAppointmentCard(appointment) {
  const cards = document.querySelectorAll(
    `[data-appointment-id="${appointment.id}"]`
  );
  cards.forEach((card) => {
    if (!card.classList.contains("appointment-card")) return;
    if (card.querySelector("h2")) {
      fillAppointmentCard(card, appointment);
      return;
    }
    card.textContent = `${appointment.time} · ${appointmentDurationLabel(appointment)} · ${appointment.patient_name}`;
  });
}

function addPatientCard(patient) {
  const list = document.querySelector("#patientsList");
  if (!list) return;
  const details = document.createElement("details");
  details.className = "patient-list-item rounded-lg border border-slate-200";
  details.dataset.search = `${patient.full_name || ""} ${patient.phone || ""} ${patient.notes || ""}`.toLowerCase();
  details.innerHTML = `
    <summary class="cursor-pointer list-none px-4 py-3">
      <div class="flex items-center justify-between gap-3">
        <div class="min-w-0">
          <h2 class="font-semibold"></h2>
          <p class="mt-1 text-sm text-slate-600"></p>
        </div>
        <span class="shrink-0 rounded-md border border-slate-200 px-2 py-1 text-xs">Без запису</span>
      </div>
    </summary>
    <div class="space-y-3 border-t border-slate-200 p-4 text-sm">
      <div class="grid gap-2 sm:grid-cols-3">
        <div class="rounded-md border border-slate-200 p-3">
          <p class="text-xs font-medium uppercase text-slate-500">Наступний запис</p>
          <p class="mt-1">Немає</p>
        </div>
        <div class="rounded-md border border-slate-200 p-3">
          <p class="text-xs font-medium uppercase text-slate-500">Останній прийом</p>
          <p class="mt-1">Немає</p>
        </div>
        <div class="rounded-md border border-slate-200 p-3">
          <p class="text-xs font-medium uppercase text-slate-500">Дата народження</p>
          <p class="mt-1" data-patient-birth></p>
        </div>
      </div>
      <div class="rounded-md border border-slate-200 p-3">
        <p class="text-xs font-medium uppercase text-slate-500">Нотатки</p>
        <p class="mt-1" data-patient-notes></p>
      </div>
      <button class="edit-patient w-full rounded-md border border-slate-200 px-3 py-2 text-sm font-medium sm:w-auto">Редагувати</button>
    </div>
  `;
  details.querySelector("h2").textContent = patient.full_name;
  details.querySelector("summary p").textContent = patient.phone || "Телефон не вказано";
  details.querySelector("[data-patient-birth]").textContent =
    patient.birth_date || "Не вказано";
  details.querySelector("[data-patient-notes]").textContent = patient.notes || "Немає";
  const editButton = details.querySelector(".edit-patient");
  editButton.dataset.patientId = patient.id;
  editButton.dataset.fullName = patient.full_name || "";
  editButton.dataset.phone = patient.phone || "";
  editButton.dataset.birthDate = patient.birth_date || "";
  editButton.dataset.notes = patient.notes || "";
  list.prepend(details);
}

function addDoctorOption(doctor) {
  document.querySelectorAll('select[name="doctor_id"]').forEach((select) => {
    const option = document.createElement("option");
    option.value = doctor.id;
    option.textContent = doctor.full_name;
    select.append(option);
  });
}

function addDoctorCard(doctor) {
  const list = document.querySelector("#doctorsList");
  if (!list) return;
  const article = document.createElement("article");
  article.className = "doctor-card rounded-lg border border-slate-200 p-4";
  article.dataset.doctorId = doctor.id;
  article.innerHTML = `
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 class="text-lg font-semibold"></h2>
        <p class="mt-1 text-sm"></p>
      </div>
      <span class="shrink-0 rounded-md border border-slate-200 px-2 py-1 text-xs"></span>
    </div>
    <div class="mt-3 rounded-md border border-slate-200 p-3 text-sm">
      <p class="text-xs font-medium uppercase text-slate-500">Нотатки</p>
      <p class="mt-1"></p>
    </div>
    <button class="edit-doctor mt-4 w-full rounded-md border border-slate-200 px-3 py-2 text-sm font-medium">Редагувати</button>
  `;
  article.querySelector("h2").textContent = doctor.full_name;
  article.querySelector("p").textContent = doctor.phone || "Телефон не вказано";
  article.querySelector("span").textContent = doctor.active ? "Активний" : "Вимкнений";
  article.querySelectorAll("p")[2].textContent = doctor.notes || "Немає";
  const editButton = article.querySelector(".edit-doctor");
  editButton.dataset.doctorId = doctor.id;
  editButton.dataset.fullName = doctor.full_name;
  editButton.dataset.phone = doctor.phone || "";
  editButton.dataset.notes = doctor.notes || "";
  editButton.dataset.active = doctor.active ? "true" : "false";
  list.prepend(article);
}

function prepareAppointmentFormDefaults() {
  const form = document.querySelector("#appointmentForm");
  if (!form) return;

  const schedule = document.querySelector("[data-schedule-date]");
  const autocomplete = document.querySelector("#patientAutocomplete");
  form.reset();
  if (autocomplete) autocomplete.value = "";

  if (!schedule) return;

  form.elements.date.value = schedule.dataset.defaultDate || schedule.dataset.today || "";
  form.elements.time.value = schedule.dataset.defaultTime || "";
  form.elements.duration_minutes.value = schedule.dataset.defaultDuration || "30";
  if (schedule.dataset.defaultDoctorId) {
    form.elements.doctor_id.value = schedule.dataset.defaultDoctorId;
  }
}

function requiresMobileDoctorSelection() {
  const schedule = document.querySelector("[data-mobile-requires-doctor]");
  return Boolean(schedule && isMobileViewport());
}

function openMobileDoctorRequiredModal() {
  if (!requiresMobileDoctorSelection()) return false;
  openModal("mobileDoctorRequiredModal");
  return true;
}

document.addEventListener("click", (event) => {
  const openButton = event.target.closest("[data-open-modal]");
  if (openButton) {
    if (openButton.dataset.closeParent !== undefined) {
      closeModal(openButton.closest(".modal"));
    }
    if (openButton.dataset.openModal === "doctorModal") {
      const form = document.querySelector("#doctorForm");
      document.querySelector("#doctorModalTitle").textContent = "Новий лікар";
      form?.reset();
      if (form?.elements.active) form.elements.active.checked = true;
    }
    if (openButton.dataset.openModal === "patientModal") {
      const form = document.querySelector("#patientForm");
      document.querySelector("#patientModalTitle").textContent = "Новий пацієнт";
      form?.reset();
      if (form?.elements.patient_id) form.elements.patient_id.value = "";
    }
    if (openButton.dataset.openModal === "appointmentModal") {
      if (openMobileDoctorRequiredModal()) return;
      prepareAppointmentFormDefaults();
    }
    openModal(openButton.dataset.openModal);
  }

  const closeButton = event.target.closest("[data-close-modal]");
  if (closeButton) {
    closeModal(closeButton.closest(".modal"));
  }
});

document.querySelectorAll(".modal").forEach((modal) => {
  modal.addEventListener("click", (event) => {
    if (modal.dataset.requiredModal !== undefined) return;
    if (event.target === modal) closeModal(modal);
  });
});

document.addEventListener("click", (event) => {
  const emptySlot = event.target.closest(".schedule-empty");
  if (!emptySlot) return;
  if (emptySlot.disabled || emptySlot.getAttribute("aria-disabled") === "true") return;
  const form = document.querySelector("#appointmentForm");
  if (!form) return;
  form.reset();
  form.elements.date.value = emptySlot.dataset.date;
  form.elements.time.value = emptySlot.dataset.time;
  form.elements.duration_minutes.value = emptySlot.dataset.duration || "30";
  form.elements.doctor_id.value = emptySlot.dataset.doctorId;
  document.querySelector("#patientAutocomplete").value = "";
  openModal("appointmentModal");
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest(".doctor-work-toggle");
  if (!button) return;

  const isWorking = button.dataset.isWorking === "true";
  const doctorName = button.dataset.doctorName || "лікар";
  const message = isWorking
    ? `Повернути ${doctorName} до графіка на цей день?`
    : `${doctorName} не працює у цей день? Колонку буде приховано.`;

  if (!window.confirm(message)) return;

  await requestJson("/api/doctor-days", {
    method: "POST",
    body: JSON.stringify({
      doctor_id: button.dataset.doctorId,
      date: button.dataset.date,
      is_working: isWorking,
    }),
  });

  window.location.reload();
});

const patientForm = document.querySelector("#patientForm");
patientForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  const patientId = data.patient_id;
  delete data.patient_id;

  try {
    const patient = await requestJson(
      patientId ? `/api/patients/${patientId}` : "/api/patients",
      {
        method: patientId ? "PATCH" : "POST",
        body: JSON.stringify(data),
      }
    );
    if (!patientId) addPatientCard(patient);
    showMessage(form, "Пацієнта збережено.");
    if (patientId || window.location.pathname === "/patients") {
      window.setTimeout(() => window.location.reload(), 350);
    } else {
      form.reset();
    }
  } catch (error) {
    showMessage(form, error.message);
  }
});

document.querySelector("#patientPageSearch")?.addEventListener("input", (event) => {
  const query = event.currentTarget.value.trim().toLowerCase();
  document.querySelectorAll(".patient-list-item").forEach((item) => {
    item.classList.toggle("hidden", !item.dataset.search.includes(query));
  });
});

document.addEventListener("click", (event) => {
  const button = event.target.closest(".edit-patient");
  if (!button) return;

  const form = document.querySelector("#patientForm");
  if (!form) return;
  document.querySelector("#patientModalTitle").textContent = "Редагувати пацієнта";
  form.reset();
  form.elements.patient_id.value = button.dataset.patientId;
  form.elements.full_name.value = button.dataset.fullName || "";
  form.elements.phone.value = button.dataset.phone || "";
  form.elements.birth_date.value = button.dataset.birthDate || "";
  form.elements.notes.value = button.dataset.notes || "";
  openModal("patientModal");
});

const doctorForm = document.querySelector("#doctorForm");
doctorForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  const doctorId = data.doctor_id;
  delete data.doctor_id;

  try {
    const doctor = await requestJson(
      doctorId ? `/api/doctors/${doctorId}` : "/api/doctors",
      {
        method: doctorId ? "PATCH" : "POST",
        body: JSON.stringify(data),
      }
    );
    if (!doctorId) {
      addDoctorOption(doctor);
      addDoctorCard(doctor);
    }
    showMessage(form, "Лікаря збережено.");
    if (doctorId || window.location.pathname === "/doctors") {
      window.setTimeout(() => window.location.reload(), 350);
    } else {
      form.reset();
      form.elements.active.checked = true;
    }
  } catch (error) {
    showMessage(form, error.message);
  }
});

document.addEventListener("click", (event) => {
  const button = event.target.closest(".edit-doctor");
  if (!button) return;
  const form = document.querySelector("#doctorForm");
  form.reset();
  document.querySelector("#doctorModalTitle").textContent = "Редагувати лікаря";
  form.elements.doctor_id.value = button.dataset.doctorId;
  form.elements.full_name.value = button.dataset.fullName || "";
  form.elements.phone.value = button.dataset.phone || "";
  form.elements.notes.value = button.dataset.notes || "";
  form.elements.active.checked = button.dataset.active === "true";
  openModal("doctorModal");
});

const autocomplete = document.querySelector("#patientAutocomplete");
const suggestions = document.querySelector("#patientSuggestions");
const appointmentForm = document.querySelector("#appointmentForm");

autocomplete?.addEventListener("input", async () => {
  appointmentForm.elements.patient_id.value = "";
  const query = autocomplete.value.trim();
  if (query.length < 2) {
    suggestions.classList.add("hidden");
    return;
  }

  const patients = await requestJson(`/api/patients?q=${encodeURIComponent(query)}`);
  suggestions.innerHTML = "";
  patients.forEach((patient) => {
    const option = document.createElement("button");
    option.type = "button";
    option.className = "block w-full px-3 py-3 text-left text-sm hover:bg-slate-200";
    option.textContent = `${patient.full_name}${patient.phone ? ` · ${patient.phone}` : ""}`;
    option.addEventListener("click", () => {
      autocomplete.value = option.textContent;
      appointmentForm.elements.patient_id.value = patient.id;
      suggestions.classList.add("hidden");
    });
    suggestions.append(option);
  });
  suggestions.classList.toggle("hidden", patients.length === 0);
});

appointmentForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  try {
    const appointment = await requestJson("/api/appointments", {
      method: "POST",
      body: JSON.stringify(formData(form)),
    });
    addServiceOption(appointment.service_name);
    addAppointmentCard(appointment);
    showMessage(form, "Запис створено.");
    if (window.location.pathname === "/schedule") {
      window.setTimeout(() => window.location.reload(), 350);
    } else {
      form.reset();
      autocomplete.value = "";
    }
  } catch (error) {
    showMessage(form, error.message);
  }
});

document.addEventListener("click", async (event) => {
  const card = event.target.closest(".appointment-card");
  if (!card) return;

  const payload = await requestJson(`/api/appointments/${card.dataset.appointmentId}`);
  const { appointment, patient, last_visit: lastVisit } = payload;
  const form = document.querySelector("#detailForm");

  form.elements.appointment_id.value = appointment.id;
  form.elements.date.value = appointment.date;
  form.elements.time.value = appointment.time;
  form.elements.doctor_id.value = appointment.doctor_id;
  form.elements.duration_minutes.value = appointment.duration_minutes || "30";
  form.elements.status.value = appointment.status || "planned";
  form.elements.service_name.value = appointment.service_name || "";
  form.elements.reason.value = appointment.reason || "";

  document.querySelector("#detailTitle").textContent = patient.full_name || "Пацієнт";
  document.querySelector("#detailMeta").textContent =
    `${appointmentMetaText(appointment)} · ${appointment.doctor_name}`;
  document.querySelector("#detailPatientPhone").textContent =
    patient.phone || "Не вказано";
  document.querySelector("#detailPatientNotes").textContent =
    patient.notes || "Немає нотаток";
  document.querySelector("#detailLastVisit").textContent = lastVisit
    ? `${lastVisit.date} о ${lastVisit.time}`
    : "Немає відмічених прийомів";

  openModal("detailModal");
});

const detailForm = document.querySelector("#detailForm");
async function saveDetailForm(form) {
  const appointmentId = form.elements.appointment_id.value;
  const appointment = await requestJson(`/api/appointments/${appointmentId}`, {
    method: "PATCH",
    body: JSON.stringify(formData(form)),
  });
  addServiceOption(appointment.service_name);
  updateAppointmentCard(appointment);
  document.querySelector("#detailMeta").textContent =
    `${appointmentMetaText(appointment)} · ${appointment.doctor_name}`;
  showMessage(form, "Деталі збережено.");
  if (window.location.pathname === "/schedule") {
    window.setTimeout(() => window.location.reload(), 350);
  }
}

detailForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  try {
    await saveDetailForm(form);
  } catch (error) {
    showMessage(form, error.message);
  }
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest(".close-status");
  if (!button) return;
  const form = document.querySelector("#detailForm");
  if (!form) return;
  form.elements.status.value = button.dataset.status;
  try {
    await saveDetailForm(form);
  } catch (error) {
    showMessage(form, error.message);
  }
});

restoreScheduleDoctor();
updateCurrentTimeMarker();
openMobileDoctorRequiredModal();
window.setInterval(updateCurrentTimeMarker, 60000);
