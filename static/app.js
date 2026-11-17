const form = document.getElementById("bias-form");
const submitBtn = document.getElementById("submit-btn");
const formErrors = document.getElementById("form-errors");
const results = document.getElementById("results");
const placeholder = document.getElementById("results-placeholder");
const badge = document.getElementById("region-badge");
const warnings = document.getElementById("warnings");
const tables = document.getElementById("result-tables");
const modeSelect = document.getElementById("mode");
const resultMode = document.getElementById("result-mode");

const REGION_LABELS = {
  forward_active: "Forward-Active",
  cutoff: "Cutoff",
  saturation: "Saturation",
};

const MODE_LABELS = {
  divider: "Voltage Divider Bias",
  fixed: "Fixed Bias",
  emitter: "Emitter Bias",
};

const MODE_HINTS = {
  divider: "กรอก VCC, R1, R2, RC, RE, β, VBE แล้วกด Calculate DC Bias",
  fixed: "กรอก VCC, RC, RB, β, VBE แล้วกด Calculate DC Bias",
  emitter: "กรอก VCC, RC, RE, RB, β, VBE แล้วกด Calculate DC Bias",
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

modeSelect.addEventListener("change", () => {
  applyMode();
  resetMessages();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  resetMessages();
  // Build the payload before setBusy() disables controls: disabled fields are
  // omitted from FormData, and `mode` must always reach the server.
  const payload = new FormData(form);
  const submittedMode = modeSelect.value;
  setBusy(true);

  try {
    const response = await fetch("/calculate", {
      method: "POST",
      body: payload,
    });
    const body = await response.json();

    if (!response.ok || !body.ok) {
      showErrors(body.errors || {}, body.message, body.mode);
      return;
    }

    if (body.data.mode !== submittedMode) {
      return;
    }

    render(body.data);
  } catch (error) {
    showSummary("เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ กรุณาตรวจสอบว่า Flask ยังทำงานอยู่");
  } finally {
    setBusy(false);
  }
});

function applyMode() {
  const mode = modeSelect.value;
  document.querySelectorAll(".field[data-modes]").forEach((field) => {
    const active = field.dataset.modes.split(" ").includes(mode);
    field.hidden = !active;
    field.querySelectorAll("input, select").forEach((control) => {
      control.disabled = !active;
    });
  });
  placeholder.textContent = MODE_HINTS[mode] || MODE_HINTS.divider;
}

function setBusy(isBusy) {
  submitBtn.disabled = isBusy;
  modeSelect.disabled = isBusy;
  submitBtn.textContent = isBusy ? "กำลังคำนวณ…" : "Calculate DC Bias";
}

function resetMessages() {
  formErrors.hidden = true;
  formErrors.textContent = "";
  document.querySelectorAll(".field-error").forEach((node) => node.remove());
  document.querySelectorAll(".field input, .field select").forEach((control) => {
    control.removeAttribute("aria-invalid");
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

function showErrors(errors, message, mode) {
  const label = MODE_LABELS[mode] || mode || "";
  const summary = message || "กรุณาตรวจสอบค่าที่ป้อน";
  showSummary(label ? `โหมด: ${label} — ${summary}` : summary);

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

  resultMode.textContent = `โหมด: ${MODE_LABELS[data.mode] || data.mode}`;

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
  tables.appendChild(buildTable("Inputs (normalized)", inputRows(inputs)));
  if (data.intermediate.vth_v != null) {
    tables.appendChild(buildTable("Intermediate", [
      ["VTH", volts(data.intermediate.vth_v)],
      ["RTH", ohms(data.intermediate.rth_ohm)],
    ]));
  }
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

function inputRows(inputs) {
  const rows = [["VCC", volts(inputs.vcc_v)]];
  if (inputs.r1_ohm !== undefined) {
    rows.push(["R1", ohms(inputs.r1_ohm)], ["R2", ohms(inputs.r2_ohm)]);
  }
  rows.push(["RC", ohms(inputs.rc_ohm)]);
  if (inputs.re_ohm !== undefined) {
    rows.push(["RE", ohms(inputs.re_ohm)]);
  }
  if (inputs.rb_ohm !== undefined) {
    rows.push(["RB", ohms(inputs.rb_ohm)]);
  }
  rows.push(["β", number(inputs.beta, 0)], ["VBE", `${number(inputs.vbe_v, 2)} V`]);
  return rows;
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

applyMode();
