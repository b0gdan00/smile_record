const modalMap = new Map(
  [...document.querySelectorAll(".modal")].map((modal) => [modal.id, modal])
);

function minutesFromTime(value) {
  const [hours, minutes] = value.split(":").map(Number);
  return hours * 60 + minutes;
}

function padTimePart(value) {
  return String(value).padStart(2, "0");
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

  badge.textContent = `Поточний час: ${currentTime}`;
  badge.classList.toggle("hidden", !isSelectedToday);

  document.querySelectorAll(".schedule-time-row").forEach((row) => {
    row.classList.remove("bg-slate-200");
  });

  if (!isSelectedToday) return;

  const currentMinutes = now.getHours() * 60 + now.getMinutes();
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
  "bg-orange-100",
  "text-slate-50",
  "text-slate-900",
  "text-green-800",
  "text-red-800",
  "text-orange-800",
  "border-green-200",
  "border-red-200",
  "border-orange-200",
  "border-2",
  "border-orange-500",
];

const badgeColorClasses = [
  "bg-slate-900",
  "bg-green-600",
  "bg-red-600",
  "bg-orange-500",
  "text-slate-50",
  "text-slate-900",
];

function statusCardClass(appointment) {
  if (appointment.status_card_class) return appointment.status_card_class;
  if (appointment.needs_status) return "border-2 border-orange-500 bg-slate-200 text-slate-900";
  if (appointment.is_past) return "bg-slate-200 text-slate-900";
  return "bg-slate-900 text-slate-50";
}

function fillAppointmentCard(card, appointment) {
  const paragraphs = card.querySelectorAll("p");
  paragraphs[0].textContent = `${appointment.date} · ${appointment.time}`;
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
    card.textContent = `${appointment.time} · ${appointment.patient_name}`;
  });
}

function addPatientCard(patient) {
  const tableBody = document.querySelector("#patientsTableBody");
  if (!tableBody) return;
  const row = document.createElement("tr");
  row.innerHTML = `
    <td class="px-3 py-3 font-medium"></td>
    <td class="px-3 py-3"></td>
    <td class="px-3 py-3">Немає</td>
    <td class="px-3 py-3">Немає</td>
    <td class="px-3 py-3"></td>
  `;
  row.children[0].textContent = patient.full_name;
  row.children[1].textContent = patient.phone || "Телефон не вказано";
  row.children[4].textContent = patient.notes || "";
  tableBody.prepend(row);
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
      <div>
        <h2 class="text-lg font-semibold"></h2>
        <p class="mt-1 text-sm"></p>
      </div>
      <span class="rounded-md border border-slate-200 px-2 py-1 text-xs"></span>
    </div>
    ${doctor.notes ? '<p class="mt-2 text-sm"></p>' : ""}
  `;
  article.querySelector("h2").textContent = doctor.full_name;
  article.querySelector("p").textContent = doctor.phone || "Телефон не вказано";
  article.querySelector("span").textContent = doctor.active ? "Активний" : "Вимкнений";
  const notes = article.querySelectorAll("p")[1];
  if (notes) notes.textContent = doctor.notes;
  list.prepend(article);
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
    openModal(openButton.dataset.openModal);
  }

  const closeButton = event.target.closest("[data-close-modal]");
  if (closeButton) {
    closeModal(closeButton.closest(".modal"));
  }
});

document.querySelectorAll(".modal").forEach((modal) => {
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal(modal);
  });
});

document.addEventListener("click", (event) => {
  const emptySlot = event.target.closest(".schedule-empty");
  if (!emptySlot) return;
  const form = document.querySelector("#appointmentForm");
  if (!form) return;
  form.reset();
  form.elements.date.value = emptySlot.dataset.date;
  form.elements.time.value = emptySlot.dataset.time;
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
  try {
    const patient = await requestJson("/api/patients", {
      method: "POST",
      body: JSON.stringify(formData(form)),
    });
    addPatientCard(patient);
    showMessage(form, "Пацієнта збережено.");
    form.reset();
  } catch (error) {
    showMessage(form, error.message);
  }
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
  form.elements.status.value = appointment.status || "planned";
  form.elements.service_name.value = appointment.service_name || "";
  form.elements.reason.value = appointment.reason || "";
  form.elements.comments.value = appointment.comments || "";

  document.querySelector("#detailTitle").textContent = patient.full_name || "Пацієнт";
  document.querySelector("#detailMeta").textContent =
    `${appointment.date} · ${appointment.time} · ${appointment.doctor_name}`;
  document.querySelector("#detailPatientInfo").textContent =
    `Телефон: ${patient.phone || "не вказано"}. Нотатки: ${patient.notes || "немає"}.`;
  document.querySelector("#detailLastVisit").textContent = lastVisit
    ? `Був раніше: так, востаннє ${lastVisit.date} о ${lastVisit.time}.`
    : "Був раніше: немає відмічених попередніх прийомів.";

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
    `${appointment.date} · ${appointment.time} · ${appointment.doctor_name}`;
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

updateCurrentTimeMarker();
window.setInterval(updateCurrentTimeMarker, 60000);
