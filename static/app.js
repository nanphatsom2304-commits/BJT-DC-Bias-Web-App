const form = document.getElementById("bias-form");
const submitBtn = document.getElementById("submit-btn");
const formErrors = document.getElementById("form-errors");
const results = document.getElementById("results");
const placeholder = document.getElementById("results-placeholder");
const badge = document.getElementById("region-badge");
const warnings = document.getElementById("warnings");
const tables = document.getElementById("result-tables");

const REGION_LABELS = {
  forward_active: "Forward-Active",
  cutoff: "Cutoff",
  saturation: "Saturation",
};

const number = (value, digits) =>
  Number(value).toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

const volts = (value) => `${number(value, 3)} V`;
const ohms = (value) =>
  Math.abs(value) >= 1000
    ? `${number(value / 1000, 2)} kΩ`
    : `${number(value, 2)} Ω`;
const amps = (value) =>
  Math.abs(value) < 1e-3
    ? `${number(value * 1e6, 2)} µA`
    : `${number(value * 1e3, 3)} mA`;

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  resetMessages();
  setBusy(true);

  try {
    const response = await fetch("/calculate", {
      method: "POST",
      body: new FormData(form),
    });
    const body = await response.json();

    if (!response.ok || !body.ok) {
      showErrors(body.errors || {}, body.message);
      return;
    }

    render(body.data);
  } catch (error) {
    showSummary("เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ กรุณาตรวจสอบว่า Flask ยังทำงานอยู่");
  } finally {
    setBusy(false);
  }
});

function setBusy(isBusy) {
  submitBtn.disabled = isBusy;
  submitBtn.textContent = isBusy ? "กำลังคำนวณ…" : "Calculate DC Bias";
}

function resetMessages() {
  formErrors.hidden = true;
  formErrors.textContent = "";
  document.querySelectorAll(".field-error").forEach((node) => node.remove());
  document.querySelectorAll(".field input").forEach((input) => {
    input.removeAttribute("aria-invalid");
  });
  results.hidden = true;
  placeholder.hidden = false;
}

function showSummary(message) {
  if (!message) {
    formErrors.hidden = true;
    return;
  }
  formErrors.textContent = message;
  formErrors.hidden = false;
}

function showErrors(errors, message) {
  showSummary(message || "กรุณาตรวจสอบค่าที่ป้อน");

  Object.entries(errors).forEach(([key, text]) => {
    const input = document.getElementById(key);
    if (!input) {
      return;
    }
    const field = input.closest(".field");
    if (!field) {
      return;
    }
    input.setAttribute("aria-invalid", "true");
    const node = document.createElement("p");
    node.className = "field-error";
    node.textContent = text;
    field.appendChild(node);
  });
}

function render(data) {
  const point = data.operating_point;
  const inputs = data.inputs_si;

  badge.textContent = REGION_LABELS[data.region] || data.region;
  badge.className = `badge badge-${data.region}`;

  warnings.innerHTML = "";
  data.warnings.forEach((text) => {
    const item = document.createElement("p");
    item.textContent = text;
    warnings.appendChild(item);
  });
  warnings.hidden = data.warnings.length === 0;

  tables.innerHTML = "";
  tables.appendChild(buildTable("Inputs (normalized)", [
    ["VCC", volts(inputs.vcc_v)],
    ["R1", ohms(inputs.r1_ohm)],
    ["R2", ohms(inputs.r2_ohm)],
    ["RC", ohms(inputs.rc_ohm)],
    ["RE", ohms(inputs.re_ohm)],
    ["β", number(inputs.beta, 0)],
    ["VBE", `${number(inputs.vbe_v, 2)} V`],
  ]));
  tables.appendChild(buildTable("Intermediate", [
    ["VTH", volts(data.intermediate.vth_v)],
    ["RTH", ohms(data.intermediate.rth_ohm)],
  ]));
  tables.appendChild(buildTable("Operating point", [
    ["IB", amps(point.ib_a)],
    ["IC", amps(point.ic_a)],
    ["IE", amps(point.ie_a)],
    ["VB", volts(point.vb_v)],
    ["VE", volts(point.ve_v)],
    ["VC", volts(point.vc_v)],
    ["VCE", volts(point.vce_v)],
    ["VBC", volts(point.vbc_v)],
  ]));

  placeholder.hidden = true;
  results.hidden = false;
}

function buildTable(title, rows) {
  const section = document.createElement("section");
  section.className = "result-block";

  const heading = document.createElement("h3");
  heading.textContent = title;
  section.appendChild(heading);

  const table = document.createElement("table");
  const body = document.createElement("tbody");
  rows.forEach(([label, value]) => {
    const row = document.createElement("tr");
    const th = document.createElement("th");
    th.scope = "row";
    th.textContent = label;
    const td = document.createElement("td");
    td.textContent = value;
    row.append(th, td);
    body.appendChild(row);
  });
  table.appendChild(body);
  section.appendChild(table);
  return section;
}
