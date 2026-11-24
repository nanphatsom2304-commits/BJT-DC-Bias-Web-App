/* ============================================================
   Lab 04 — BJT CE Amplifier Simulator (ngspice)
   ============================================================ */

const simForm = document.getElementById("sim-form");
const simSubmit = document.getElementById("sim-submit");
const simErrors = document.getElementById("sim-errors");
const simResults = document.getElementById("sim-results");
const simPlaceholder = document.getElementById("sim-placeholder");
const simAnalysisLabel = document.getElementById("sim-analysis-label");
const simEngineMeta = document.getElementById("sim-engine-meta");
const simRunMeta = document.getElementById("sim-run-meta");
const simSummary = document.getElementById("sim-summary");
const simCharts = document.getElementById("sim-charts");
const simTables = document.getElementById("sim-tables");
const simWarnings = document.getElementById("sim-warnings");
const simNetlist = document.getElementById("sim-netlist");
const simModel = document.getElementById("sim-model");
const engineBadge = document.getElementById("engine-badge");
const engineText = document.getElementById("engine-text");

const ANALYSIS_LABELS = {
  dc: "DC operating point (.op)",
  ac: "AC frequency response (.ac)",
  tran: "Transient response (.tran)",
};

const CHART_COLORS = {
  magnitude: "#1d638b",
  phase: "#b85c2c",
  vin: "#546d83",
  vout: "#0c8078",
};

/* ---------- formatting ---------- */

const number = (value, digits) =>
  Number(value).toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

const SI_STEPS = [
  [1e9, "G"],
  [1e6, "M"],
  [1e3, "k"],
  [1, ""],
  [1e-3, "m"],
  [1e-6, "µ"],
  [1e-9, "n"],
  [1e-12, "p"],
];

function si(value, unit, digits = 3) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return "—";
  }
  const magnitude = Math.abs(value);
  let step = [1, ""];
  if (magnitude > 0) {
    step = SI_STEPS.find(([factor]) => magnitude >= factor) || SI_STEPS[SI_STEPS.length - 1];
  }
  return `${number(value / step[0], digits)} ${step[1]}${unit}`;
}

const volts = (value) => si(value, "V");
const amps = (value) => si(value, "A");
const hertz = (value) => si(value, "Hz", 3);
const seconds = (value) => si(value, "s", 3);

const decibels = (value) =>
  value === null || value === undefined || !Number.isFinite(Number(value))
    ? "—"
    : `${value >= 0 ? "+" : ""}${number(value, 2)} dB`;

const signedPercent = (delta, base) => {
  if (!Number.isFinite(delta) || !Number.isFinite(base) || base === 0) return "";
  const percent = (delta / base) * 100;
  return `${percent >= 0 ? "+" : ""}${number(percent, 1)}%`;
};

function tickLabel(value) {
  if (value === 0) return "0";
  const magnitude = Math.abs(value);
  if (magnitude >= 1e3) {
    const step = SI_STEPS.find(([factor]) => magnitude >= factor) || SI_STEPS[0];
    const scaled = value / step[0];
    return `${Number(scaled.toFixed(2))}${step[1]}`;
  }
  if (magnitude >= 100) return number(value, 0);
  if (magnitude >= 1) return number(value, 1).replace(/\.0$/, "");
  return number(value, 2);
}

/* ---------- engine status ---------- */

async function loadEngineStatus() {
  try {
    const response = await fetch("/api/engine");
    const body = await response.json();
    const data = body.data || {};
    if (body.ok && data.available) {
      engineBadge.dataset.state = "ok";
      engineText.textContent = `${data.version} · ${data.model.name}`;
      return;
    }
    engineBadge.dataset.state = "error";
    engineText.textContent = "ไม่พบ ngspice";
    engineBadge.title = data.message || "";
  } catch (error) {
    engineBadge.dataset.state = "error";
    engineText.textContent = "ตรวจสอบ engine ไม่ได้";
  }
}

/* ---------- simulator form ---------- */

simForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearSimMessages();

  const payload = new FormData(simForm);
  const analysis = payload.get("sim_analysis") || "dc";

  setSimBusy(true, analysis);

  try {
    const response = await fetch("/api/simulate", {
      method: "POST",
      body: payload,
    });
    const body = await response.json();

    if (!response.ok || !body.ok) {
      showSimErrors(body.errors || {}, body.message, body.engine_unavailable);
      return;
    }

    renderSimulation(body.data);
  } catch (error) {
    simPlaceholder.hidden = false;
    simPlaceholder.textContent =
      "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ กรุณาตรวจสอบว่า Flask ยังทำงานอยู่";
    simResults.hidden = true;
    simErrors.textContent = "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ (network error)";
    simErrors.hidden = false;
  } finally {
    setSimBusy(false);
  }
});

document.querySelectorAll('input[name="sim_analysis"]').forEach((input) => {
  input.addEventListener("change", () => {
    updateSourceHints();
    clearSimMessages();
  });
});

function updateSourceHints() {
  const analysis = document.querySelector('input[name="sim_analysis"]:checked').value;
  const amplitude = document.getElementById("sim_amp_mv");
  const frequency = document.getElementById("sim_freq_hz");
  const hint = document.getElementById("sim-hint");

  amplitude.required = analysis === "tran";
  frequency.required = analysis !== "dc";

  if (analysis === "dc") {
    hint.textContent =
      "DC (.op) ใช้เฉพาะค่าอุปกรณ์ — แอมพลิจูดและความถี่ไม่ถูกใช้ใน operating point";
  } else if (analysis === "ac") {
    hint.textContent =
      "AC (.ac) กวาดความถี่ 1 Hz – 100 MHz ด้วยแหล่ง 1 V (normalized) และรายงานค่าใกล้ความถี่ที่กรอก";
  } else {
    hint.textContent =
      "Transient (.tran) ใช้แอมพลิจูดและความถี่ที่กรอก รัน 5 คาบและรายงานช่วง steady state";
  }
}

function setSimBusy(isBusy, analysis) {
  simSubmit.disabled = isBusy;
  simForm.querySelectorAll("input, select").forEach((control) => {
    control.disabled = isBusy;
  });
  simSubmit.textContent = isBusy
    ? `กำลังรัน ngspice (${analysis || "dc"})…`
    : "Run ngspice";
  simForm.setAttribute("aria-busy", String(isBusy));
  if (isBusy) {
    simResults.hidden = true;
    simPlaceholder.hidden = false;
    simPlaceholder.textContent = "กำลังรัน ngspice — ผลเดิมถูกล้างเพื่อไม่ให้เข้าใจผิดว่าเป็นผลใหม่";
  }
}

function clearSimMessages() {
  simErrors.hidden = true;
  simErrors.textContent = "";
  simForm.querySelectorAll(".field-error").forEach((node) => node.remove());
  simForm.querySelectorAll("input, select").forEach((control) => {
    control.removeAttribute("aria-invalid");
  });
  simResults.hidden = true;
  simPlaceholder.hidden = false;
  simPlaceholder.textContent =
    "ตั้งค่าอุปกรณ์แล้วกด Run ngspice — ผลทุกค่าอ่านจาก output จริงของ ngspice";
}

function showSimErrors(errors, message, engineUnavailable) {
  simResults.hidden = true;
  simPlaceholder.hidden = false;
  simPlaceholder.textContent = "ยังไม่มีผลลัพธ์ที่ใช้ได้ — แก้ไขแล้วลองรันใหม่";

  const summary = message || "กรุณาตรวจสอบค่าที่ป้อน";
  simErrors.textContent = engineUnavailable
    ? `${summary}\nติดตั้ง ngspice หรือตั้งค่า NGSPICE_BIN แล้วลองใหม่ (ดู README)`
    : summary;
  simErrors.hidden = false;

  Object.entries(errors).forEach(([key, text]) => {
    const input = document.getElementById(`sim_${key}`);
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

/* ---------- simulator results ---------- */

function renderSimulation(data) {
  simAnalysisLabel.textContent = ANALYSIS_LABELS[data.analysis] || data.analysis;
  simEngineMeta.textContent = `${data.engine.version} · ${data.engine.model.name} · batch`;
  const runTime = new Date().toLocaleTimeString("th-TH", { hour12: false });
  simRunMeta.textContent = `รันเมื่อ ${runTime}`;

  simSummary.replaceChildren();
  simCharts.replaceChildren();
  simTables.replaceChildren();

  if (data.analysis === "dc") {
    renderDc(data);
  } else if (data.analysis === "ac") {
    renderAc(data);
  } else {
    renderTran(data);
  }

  simWarnings.replaceChildren();
  const warnings = data.warnings || [];
  warnings.forEach((text) => {
    const item = document.createElement("p");
    item.textContent = text;
    simWarnings.appendChild(item);
  });
  simWarnings.hidden = warnings.length === 0;

  simModel.textContent = `${data.engine.model.note} — แหล่งที่มา: ${data.engine.model.source}`;
  simNetlist.textContent = data.netlist;

  simPlaceholder.hidden = true;
  simResults.hidden = false;
}

function stat(label, value, unit) {
  const wrapper = document.createElement("dl");
  wrapper.className = "stat";
  const term = document.createElement("dt");
  term.textContent = label;
  const description = document.createElement("dd");
  description.textContent = value;
  if (unit) {
    const small = document.createElement("small");
    small.textContent = ` ${unit}`;
    description.appendChild(small);
  }
  wrapper.append(term, description);
  return wrapper;
}

/* ---------- DC ---------- */

function renderDc(data) {
  const spice = data.operating_point;
  const reference = data.reference;

  simSummary.append(
    stat("IC (ngspice)", amps(spice.ic_a)),
    stat("VCE (ngspice)", volts(spice.vce_v)),
    stat("IB (ngspice)", amps(spice.ib_a)),
    stat("VBE (ngspice)", volts(spice.vbe_v))
  );

  const rows = [
    ["VB", volts(spice.vb_v), volts(reference.operating_point.vb_v)],
    ["VE", volts(spice.ve_v), volts(reference.operating_point.ve_v)],
    ["VC", volts(spice.vc_v), volts(reference.operating_point.vc_v)],
    ["VCE", volts(spice.vce_v), volts(reference.operating_point.vce_v)],
    ["IC", amps(spice.ic_a), amps(reference.operating_point.ic_a)],
    ["IB", amps(spice.ib_a), amps(reference.operating_point.ib_a)],
    ["IE", amps(spice.ie_a), amps(reference.operating_point.ie_a)],
  ];
  const numeric = [
    [spice.vb_v, reference.operating_point.vb_v, "V"],
    [spice.ve_v, reference.operating_point.ve_v, "V"],
    [spice.vc_v, reference.operating_point.vc_v, "V"],
    [spice.vce_v, reference.operating_point.vce_v, "V"],
    [spice.ic_a, reference.operating_point.ic_a, "A"],
    [spice.ib_a, reference.operating_point.ib_a, "A"],
    [spice.ie_a, reference.operating_point.ie_a, "A"],
  ];

  const table = document.createElement("table");
  table.className = "compare";
  const colgroup = document.createElement("colgroup");
  [24, 25, 25, 26].forEach((width) => {
    const col = document.createElement("col");
    col.style.width = `${width}%`;
    colgroup.appendChild(col);
  });
  table.appendChild(colgroup);
  const head = document.createElement("thead");
  head.innerHTML =
    "<tr><th>ปริมาณ</th><th class=\"num\">ngspice (.op)</th>" +
    "<th class=\"num\">Analytical (Lab 3)</th><th class=\"num\">Δ</th></tr>";
  table.appendChild(head);

  const body = document.createElement("tbody");
  rows.forEach(([label, spiceText, referenceText], index) => {
    const [spiceValue, referenceValue, unit] = numeric[index];
    const delta = spiceValue - referenceValue;
    const row = document.createElement("tr");
    const th = document.createElement("th");
    th.scope = "row";
    th.textContent = label;
    const spiceCell = document.createElement("td");
    spiceCell.className = "num";
    spiceCell.textContent = spiceText;
    const referenceCell = document.createElement("td");
    referenceCell.className = "num";
    referenceCell.textContent = referenceText;
    const deltaCell = document.createElement("td");
    deltaCell.className = `num ${Math.abs(delta) < 1e-12 ? "delta-zero" : "delta"}`;
    const deltaText = unit === "A" ? si(delta, "A") : si(delta, "V");
    deltaCell.textContent = `${delta >= 0 ? "+" : ""}${deltaText}`;
    const percent = signedPercent(delta, referenceValue);
    if (percent) {
      const percentNode = document.createElement("span");
      percentNode.className = "delta-percent";
      percentNode.textContent = percent;
      deltaCell.appendChild(percentNode);
    }
    row.append(th, spiceCell, referenceCell, deltaCell);
    body.appendChild(row);
  });
  table.appendChild(body);

  const section = document.createElement("section");
  section.className = "result-block";
  const heading = document.createElement("h3");
  heading.textContent = "Operating point — ngspice เทียบกับสมการ Lab 3";
  const note = document.createElement("p");
  note.className = "chart-note";
  note.textContent =
    `Analytical ใช้ β=${reference.assumptions.beta} คงที่ และ VBE=${reference.assumptions.vbe_v} V; ` +
    `ngspice ใช้โมเดล ${data.engine.model.name} ซึ่งมี β และ VBE ไม่คงที่ ค่าจึงต่างกันได้`;
  section.append(heading, note, table);

  const inputs = data.inputs_si;
  const circuitRows = [
    ["VCC", volts(inputs.vcc_v)],
    ["R1 / R2", `${si(inputs.r1_ohm, "Ω", 3)} / ${si(inputs.r2_ohm, "Ω", 3)}`],
    ["RC / RE / RL", `${si(inputs.rc_ohm, "Ω", 3)} / ${si(inputs.re_ohm, "Ω", 3)} / ${si(inputs.rl_ohm, "Ω", 3)}`],
    ["CIN / COUT", `${si(inputs.cin_f, "F", 3)} / ${si(inputs.cout_f, "F", 3)}`],
    ["แหล่งสัญญาณ", `${si(inputs.source_amplitude_v, "V", 3)} peak · ${hertz(inputs.source_frequency_hz)}`],
    ["VTH / RTH (อ้างอิง)", `${volts(reference.vth_v)} / ${si(reference.rth_ohm, "Ω", 3)}`],
  ];
  simTables.append(section, buildTable("ค่าอุปกรณ์ที่ส่งเข้า ngspice", circuitRows));
}

/* ---------- AC ---------- */

function renderAc(data) {
  const midband = data.midband;
  const cutoff = data.cutoff;
  const atFrequency = hertz(midband.frequency_hz);

  simSummary.append(
    stat(`Gain @ ${atFrequency}`, decibels(midband.gain_db)),
    stat("Gain (V/V)", number(midband.gain_vv, 3)),
    stat(`Phase @ ${atFrequency}`, `${number(midband.phase_deg, 1)}°`),
    stat("Lower −3 dB", cutoff.low_hz ? hertz(cutoff.low_hz) : "ไม่พบในช่วง"),
    stat("Upper −3 dB", cutoff.high_hz ? hertz(cutoff.high_hz) : "ไม่พบในช่วง"),
    stat(
      "Bandwidth",
      cutoff.low_hz && cutoff.high_hz ? hertz(cutoff.high_hz - cutoff.low_hz) : "—"
    )
  );

  const frequencies = data.frequency_hz;

  simCharts.append(
    makeChart({
      title: "Magnitude response",
      note: `แกน X: ความถี่ (Hz, log) · แกน Y: |Vout/Vin| (dB) · ${frequencies.length} จุดจาก ngspice`,
      series: [
        {
          name: "Gain",
          color: CHART_COLORS.magnitude,
          points: frequencies.map((f, i) => [f, data.gain_db[i]]),
        },
      ],
      xScale: "log",
      yUnit: "dB",
    }),
    makeChart({
      title: "Phase response",
      note: "แกน X: ความถี่ (Hz, log) · แกน Y: เฟส (องศา) —  unwrapped",
      series: [
        {
          name: "Phase",
          color: CHART_COLORS.phase,
          points: frequencies.map((f, i) => [f, data.phase_deg[i]]),
        },
      ],
      xScale: "log",
      yUnit: "°",
      yZero: true,
    })
  );

  simTables.append(
    buildTable("สรุปจาก ngspice (.ac)", [
      [`Gain @ ${atFrequency}`, `${decibels(midband.gain_db)} (${number(midband.gain_vv, 4)} V/V)`],
      [`Phase @ ${atFrequency}`, `${number(midband.phase_deg, 2)}°`],
      ["Lower −3 dB", cutoff.low_hz ? hertz(cutoff.low_hz) : cutoff.note],
      ["Upper −3 dB", cutoff.high_hz ? hertz(cutoff.high_hz) : cutoff.note],
      ["ช่วงกวาดความถี่", `${hertz(frequencies[0])} → ${hertz(frequencies[frequencies.length - 1])}`],
      ["ความถี่ที่ร้องขอ", hertz(midband.target_hz)],
      ["หมายเหตุ", "AC ใช้แหล่ง 1 V (normalized) เพื่ออ่าน Gain; แอมพลิจูดในฟอร์มมีผลกับ Transient"],
    ])
  );
}

/* ---------- transient ---------- */

function renderTran(data) {
  const summary = data.summary;

  simSummary.append(
    stat("Vin (pp)", volts(summary.vin_pp_v)),
    stat("Vout (pp)", volts(summary.vout_pp_v)),
    stat("Gain (V/V)", summary.gain_vv === null ? "—" : number(summary.gain_vv, 3)),
    stat("เฟส", summary.phase_note),
    stat("ช่วงเวลา", `${number(summary.time_stop_s * 1e3, 2)} ms`),
    stat("จำนวนจุด", number(data.raw_point_count, 0))
  );

  simCharts.append(
    makeChart({
      title: "Transient waveform",
      note: "แกน X: เวลา (ms) · แกน Y: แรงดัน (mV) — Vin คือแหล่งก่อน CIN, Vout คือโหลดหลัง COUT",
      series: [
        {
          name: "Vin",
          color: CHART_COLORS.vin,
          points: data.time_s.map((t, i) => [t * 1e3, data.vin_v[i] * 1e3]),
        },
        {
          name: "Vout",
          color: CHART_COLORS.vout,
          points: data.time_s.map((t, i) => [t * 1e3, data.vout_v[i] * 1e3]),
        },
      ],
      xUnit: "ms",
      yUnit: "mV",
      yZero: true,
    })
  );

  simTables.append(
    buildTable("สรุปจาก ngspice (.tran)", [
      ["Vin peak", volts(summary.vin_peak_v)],
      ["Vout peak", volts(summary.vout_peak_v)],
      ["Vin (peak-to-peak)", volts(summary.vin_pp_v)],
      ["Vout (peak-to-peak)", volts(summary.vout_pp_v)],
      ["Gain (pp ratio)", summary.gain_vv === null ? "—" : number(summary.gain_vv, 4)],
      ["สหสัมพันธ์ Vin/Vout", summary.correlation === null ? "—" : number(summary.correlation, 4)],
      ["เฟส", summary.phase_note],
      ["จุดที่ดึงมาแสดง", `${number(data.time_s.length, 0)} จาก ${number(data.raw_point_count, 0)} จุด`],
    ])
  );
}

/* ---------- shared table builder ---------- */

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

function niceStep(span, targetCount) {
  const rough = span / Math.max(1, targetCount);
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const normalized = rough / magnitude;
  const factor = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 2.5 ? 2.5 : normalized <= 5 ? 5 : 10;
  return factor * magnitude;
}

function linearTicks(min, max, targetCount = 5) {
  const step = niceStep(max - min, targetCount);
  const ticks = [];
  const start = Math.ceil(min / step) * step;
  for (let value = start; value <= max + step * 1e-9; value += step) {
    ticks.push(Math.abs(value) < step * 1e-9 ? 0 : value);
  }
  return ticks;
}

function logTicks(min, max) {
  const first = Math.ceil(Math.log10(min));
  const last = Math.floor(Math.log10(max));
  const count = last - first + 1;
  const step = count > 9 ? Math.ceil(count / 8) : 1;
  const ticks = [];
  for (let exponent = first; exponent <= last; exponent += step) {
    ticks.push(10 ** exponent);
  }
  return ticks;
}

/* ---------- SVG chart ---------- */

function makeChart({ title, note, series, xScale = "linear", xUnit = "Hz", yUnit = "", yZero = false }) {
  const narrow = window.matchMedia("(max-width: 700px)").matches;
  const width = narrow ? 420 : 720;
  const height = narrow ? 240 : 270;
  const margin = {
    top: 12,
    right: narrow ? 10 : 16,
    bottom: 34,
    left: narrow ? 44 : 54,
  };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;

  const allPoints = series.flatMap((item) => item.points);
  const xs = allPoints.map(([x]) => x).filter(Number.isFinite);
  const ys = allPoints.map(([, y]) => y).filter(Number.isFinite);

  const wrapper = document.createElement("figure");
  wrapper.className = "chart";

  const heading = document.createElement("h3");
  heading.textContent = title;
  wrapper.appendChild(heading);

  if (!xs.length || !ys.length) {
    const empty = document.createElement("p");
    empty.className = "chart-note";
    empty.textContent = "ไม่มีข้อมูลเพียงพอสำหรับวาดกราฟ";
    wrapper.appendChild(empty);
    return wrapper;
  }

  const xMinRaw = Math.min(...xs);
  const xMaxRaw = Math.max(...xs);
  const log = xScale === "log" && xMinRaw > 0;
  const xTransform = (value) => (log ? Math.log10(value) : value);
  const xMin = xTransform(xMinRaw);
  const xMax = xTransform(xMaxRaw);
  const xSpan = xMax - xMin || 1;

  let yMin = Math.min(...ys);
  let yMax = Math.max(...ys);
  if (yZero) {
    yMin = Math.min(yMin, 0);
    yMax = Math.max(yMax, 0);
  }
  if (yMin === yMax) {
    yMin -= 1;
    yMax += 1;
  }
  const padding = (yMax - yMin) * 0.08;
  yMin -= padding;
  yMax += padding;
  const ySpan = yMax - yMin;

  const toX = (value) => margin.left + ((xTransform(value) - xMin) / xSpan) * plotWidth;
  const toY = (value) => margin.top + (1 - (value - yMin) / ySpan) * plotHeight;

  const svgNs = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNs, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `${title} — ${series.map((s) => s.name).join(", ")}`);

  const add = (name, attrs, text) => {
    const node = document.createElementNS(svgNs, name);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
    if (text !== undefined) node.textContent = text;
    svg.appendChild(node);
    return node;
  };

  // horizontal grid + y ticks
  linearTicks(yMin, yMax, narrow ? 4 : 5).forEach((value) => {
    const y = toY(value);
    add("line", {
      x1: margin.left, x2: margin.left + plotWidth, y1: y, y2: y,
      stroke: "#e6eef5", "stroke-width": 1,
    });
    add("text", {
      x: margin.left - 8, y: y + 4, "text-anchor": "end", class: "axis-label",
    }, tickLabel(value));
  });

  // vertical grid + x ticks
  const xTicks = log ? logTicks(xMinRaw, xMaxRaw) : linearTicks(xMinRaw, xMaxRaw, narrow ? 5 : 6);
  xTicks.forEach((value) => {
    const x = toX(value);
    add("line", {
      x1: x, x2: x, y1: margin.top, y2: margin.top + plotHeight,
      stroke: "#eef4f9", "stroke-width": 1,
    });
    add("text", {
      x, y: margin.top + plotHeight + 16, "text-anchor": "middle", class: "axis-label",
    }, tickLabel(value));
  });

  // axes
  add("line", {
    x1: margin.left, x2: margin.left + plotWidth,
    y1: margin.top + plotHeight, y2: margin.top + plotHeight,
    stroke: "#9fb4c6", "stroke-width": 1.2,
  });
  add("line", {
    x1: margin.left, x2: margin.left,
    y1: margin.top, y2: margin.top + plotHeight,
    stroke: "#9fb4c6", "stroke-width": 1.2,
  });

  if (yMin < 0 && yMax > 0) {
    const yZeroLine = toY(0);
    add("line", {
      x1: margin.left, x2: margin.left + plotWidth, y1: yZeroLine, y2: yZeroLine,
      stroke: "#c4d3e0", "stroke-width": 1, "stroke-dasharray": "4 3",
    });
  }

  series.forEach((item) => {
    const path = item.points
      .filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y))
      .map(([x, y], index) => `${index === 0 ? "M" : "L"}${toX(x).toFixed(2)},${toY(y).toFixed(2)}`)
      .join(" ");
    if (path) {
      add("path", {
        d: path, fill: "none", stroke: item.color,
        "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round",
      });
    }
  });

  const axisNote = document.createElement("p");
  axisNote.className = "chart-note";
  axisNote.textContent = note;

  const legend = document.createElement("div");
  legend.className = "legend";
  series.forEach((item) => {
    const entry = document.createElement("span");
    const swatch = document.createElement("i");
    swatch.className = "swatch";
    swatch.style.background = item.color;
    entry.append(swatch, document.createTextNode(item.name));
    legend.appendChild(entry);
  });
  const unitTag = document.createElement("span");
  unitTag.textContent = `หน่วย: ${yUnit || "-"}`;
  legend.appendChild(unitTag);

  wrapper.append(heading, axisNote, legend, svg);
  return wrapper;
}

/* ============================================================
   Lab 03 — DC Bias calculator (unchanged behaviour)
   ============================================================ */

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

const ohms = (value) =>
  Math.abs(value) >= 1000
    ? `${number(value / 1000, 2)} kΩ`
    : `${number(value, 2)} Ω`;

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

applyMode();
updateSourceHints();
loadEngineStatus();
