"""ngspice adapter for the Lab 4 BJT common-emitter amplifier simulator.

The module owns the external-process boundary only:

* validate and normalize simulator inputs,
* build a deterministic netlist for the reference CE voltage-divider stage,
* run ngspice in batch mode,
* parse the text output into JSON-friendly values.

It deliberately does not import Flask, Jinja or any HTTP code.  The Flask
layer (``app.py``) validates the request, calls :func:`run_analysis` and
serializes the returned dictionary.

Only the one instructor-style reference circuit is supported in v1:
VCC, R1/R2 divider, RC, RE, CIN, COUT, RL and an NPN transistor.  The
transistor model is the T2N2222 card shipped with ngspice's own example
``examples/noise/bipolar-noise.cir``.  It is a documented generic model, not
a guessed device-specific model.
"""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

Analysis = Literal["dc", "ac", "tran"]

ANALYSES = ("dc", "ac", "tran")
ANALYSIS_LABELS = {
    "dc": "DC operating point (.op)",
    "ac": "AC frequency response (.ac)",
    "tran": "Transient response (.tran)",
}

MODEL_NAME = "T2N2222"
MODEL_CARD = (
    ".model T2N2222 NPN(IS=19f BF=150 VAF=100 IKF=0.18 ISE=50p NE=2.5 "
    "BR=7.5 VAR=6.4 IKR=12m ISC=8.7p NC=1.2 RB=50 RE=0.4 RC=0.3 "
    "CJE=26p TF=0.5n CJC=11p TR=7n XTB=1.5 KF=0.032f AF=1)"
)
MODEL_SOURCE = (
    "ngspice-47 example examples/noise/bipolar-noise.cir "
    "(Tadej Tuma & Arpad Burmen, Circuit Simulation with SPICE OPUS)"
)
MODEL_NOTE = (
    "SPICE ใช้โมเดล T2N2222 (BF=150) จากตัวอย่างที่มากับ ngspice; "
    "ผล Analytical ของ Lab 3 ใช้ β=100 และ VBE=0.70 V "
    "ค่าจึงไม่จำเป็นต้องเท่ากันทุกหลัก"
)

RESISTOR_UNITS = {"ohm": 1.0, "kohm": 1_000.0}
CAPACITOR_UNITS = {"uf": 1e-6, "nf": 1e-9, "f": 1.0}

_RESISTOR_FIELDS = {
    "r1": "R1",
    "r2": "R2",
    "rc": "RC",
    "re": "RE",
    "rl": "RL",
}
_CAPACITOR_FIELDS = {"cin": "CIN", "cout": "COUT"}

_MIN_RESISTOR_OHM = 1.0
_MAX_RESISTOR_OHM = 10_000_000.0
_MIN_CAPACITOR_F = 1e-12
_MAX_CAPACITOR_F = 1e-3
_MIN_VCC_V = 0.1
_MAX_VCC_V = 30.0
_MIN_AMPLITUDE_V = 1e-4
_MAX_AMPLITUDE_V = 1.0
_MIN_FREQUENCY_HZ = 10.0
_MAX_FREQUENCY_HZ = 1_000_000.0

_NAME_RE = re.compile(r"^\s*(vcc|src|base|coll|emit|out)\s+([-+0-9.eE]+)\s*$")
_CURRENT_RE = re.compile(r"^\s*@q1\[(ic|ib|ie)\]\s+([-+0-9.eE]+)\s*$")
_NUMBER_RE = re.compile(r"^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?$")


class SpiceError(RuntimeError):
    """Base class for user-facing simulator errors."""


class NgspiceNotFound(SpiceError):
    """ngspice could not be located."""


class SpiceRunError(SpiceError):
    """ngspice started but the run failed, timed out or produced no data."""


class SpiceParseError(SpiceError):
    """ngspice produced output that the parser could not understand."""


@dataclass(frozen=True)
class AmplifierInputs:
    """Validated SI-unit inputs for the reference CE stage."""

    vcc_v: float
    r1_ohm: float
    r2_ohm: float
    rc_ohm: float
    re_ohm: float
    rl_ohm: float
    cin_f: float
    cout_f: float
    source_amplitude_v: float
    source_frequency_hz: float

    def as_dict(self) -> dict[str, float]:
        return {
            "vcc_v": self.vcc_v,
            "r1_ohm": self.r1_ohm,
            "r2_ohm": self.r2_ohm,
            "rc_ohm": self.rc_ohm,
            "re_ohm": self.re_ohm,
            "rl_ohm": self.rl_ohm,
            "cin_f": self.cin_f,
            "cout_f": self.cout_f,
            "source_amplitude_v": self.source_amplitude_v,
            "source_frequency_hz": self.source_frequency_hz,
        }


def parse_inputs(
    raw: Mapping[str, str], analysis: str = "dc"
) -> tuple[AmplifierInputs | None, dict[str, str]]:
    """Convert simulator form strings to SI units and validate them.

    Returns ``(inputs, {})`` when valid, otherwise ``(None, errors)`` where
    keys match the form field names (``re``, ``cin``, ``freq``, ...).
    """
    mode = _normalize_analysis(analysis)
    errors: dict[str, str] = {}
    if mode is None:
        errors["analysis"] = "โหมดวิเคราะห์ต้องเป็น dc, ac หรือ tran"

    def number(
        key: str,
        label: str,
        *,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> float | None:
        return _read_number(raw, key, label, errors, minimum=minimum, maximum=maximum)

    vcc = number("vcc", "VCC", minimum=_MIN_VCC_V, maximum=_MAX_VCC_V)
    beta = None  # the SPICE model supplies beta; no form beta for this mode
    del beta

    ohms: dict[str, float | None] = {}
    for key, label in _RESISTOR_FIELDS.items():
        value = number(
            key,
            label,
            minimum=_MIN_RESISTOR_OHM,
            maximum=_MAX_RESISTOR_OHM,
        )
        if value is None:
            ohms[key] = None
            continue
        unit = (raw.get(f"{key}_unit") or "").strip().lower()
        factor = RESISTOR_UNITS.get(unit)
        if factor is None:
            errors[key] = f"หน่วยของ {label} ต้องเป็น ohm หรือ kohm"
            ohms[key] = None
            continue
        converted = value * factor
        if not math.isfinite(converted) or converted > _MAX_RESISTOR_OHM:
            errors[key] = f"{label} มีค่ามากเกินกว่าที่จำลองได้"
            ohms[key] = None
            continue
        ohms[key] = converted

    farads: dict[str, float | None] = {}
    for key, label in _CAPACITOR_FIELDS.items():
        value = number(key, label, minimum=_MIN_CAPACITOR_F * 1e9, maximum=1_000.0)
        if value is None:
            farads[key] = None
            continue
        unit = (raw.get(f"{key}_unit") or "").strip().lower()
        factor = CAPACITOR_UNITS.get(unit)
        if factor is None:
            errors[key] = f"หน่วยของ {label} ต้องเป็น uf, nf หรือ f"
            farads[key] = None
            continue
        converted = value * factor
        if not math.isfinite(converted) or not (
            _MIN_CAPACITOR_F <= converted <= _MAX_CAPACITOR_F
        ):
            errors[key] = f"{label} ต้องอยู่ระหว่าง 1 pF ถึง 1 mF"
            farads[key] = None
            continue
        farads[key] = converted

    amplitude = None
    frequency = None
    if mode == "tran":
        amp_mv = number(
            "amp_mv",
            "แอมพลิจูดแหล่งสัญญาณ (mV peak)",
            minimum=_MIN_AMPLITUDE_V * 1e3,
            maximum=_MAX_AMPLITUDE_V * 1e3,
        )
        if amp_mv is not None:
            amplitude = amp_mv / 1_000.0
        frequency = number(
            "freq_hz",
            "ความถี่แหล่งสัญญาณ",
            minimum=_MIN_FREQUENCY_HZ,
            maximum=_MAX_FREQUENCY_HZ,
        )
    else:
        # AC uses the 1 V AC source; DC ignores the time source.  Read the
        # fields only if present so an API client can omit them.
        if (raw.get("amp_mv") or "").strip():
            amp_mv = number(
                "amp_mv",
                "แอมพลิจูดแหล่งสัญญาณ (mV peak)",
                minimum=_MIN_AMPLITUDE_V * 1e3,
                maximum=_MAX_AMPLITUDE_V * 1e3,
            )
            if amp_mv is not None:
                amplitude = amp_mv / 1_000.0
        if (raw.get("freq_hz") or "").strip():
            frequency = number(
                "freq_hz",
                "ความถี่แหล่งสัญญาณ",
                minimum=_MIN_FREQUENCY_HZ,
                maximum=_MAX_FREQUENCY_HZ,
            )

    if errors:
        return None, errors

    # ``mode`` cannot be None here when there are no errors, but keep the
    # contract explicit for readers and type checkers.
    if mode is None:
        return None, {"analysis": "โหมดวิเคราะห์ต้องเป็น dc, ac หรือ tran"}

    return (
        AmplifierInputs(
            vcc_v=_require(vcc),
            r1_ohm=_require(ohms["r1"]),
            r2_ohm=_require(ohms["r2"]),
            rc_ohm=_require(ohms["rc"]),
            re_ohm=_require(ohms["re"]),
            rl_ohm=_require(ohms["rl"]),
            cin_f=_require(farads["cin"]),
            cout_f=_require(farads["cout"]),
            source_amplitude_v=amplitude
            if amplitude is not None
            else 10e-3,
            source_frequency_hz=frequency if frequency is not None else 1_000.0,
        ),
        {},
    )


def _read_number(
    raw: Mapping[str, str],
    key: str,
    label: str,
    errors: dict[str, str],
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    text = (raw.get(key) or "").strip()
    if not text:
        errors[key] = f"กรุณากรอก {label}"
        return None
    try:
        value = float(text)
    except ValueError:
        errors[key] = f"{label} ต้องเป็นตัวเลข"
        return None
    if not math.isfinite(value):
        errors[key] = f"{label} ต้องเป็นจำนวนจริงจำกัด"
        return None
    if minimum is not None and value < minimum:
        errors[key] = f"{label} ต้องไม่น้อยกว่า {minimum:g}"
        return None
    if maximum is not None and value > maximum:
        errors[key] = f"{label} ต้องไม่เกิน {maximum:g}"
        return None
    return value


def _require(value: float | None) -> float:
    if value is None:  # pragma: no cover - parse_inputs validates first
        raise SpiceParseError("ค่าอินพุตหายไปหลังการตรวจสอบ")
    return value


def _normalize_analysis(analysis: str | None) -> Analysis | None:
    value = (analysis or "").strip().lower()
    if not value:
        return "dc"
    if value in ANALYSES:
        return value  # type: ignore[return-value]
    return None


def build_netlist(inputs: AmplifierInputs, analysis: str = "dc") -> str:
    """Build the verified reference netlist for one analysis mode."""
    mode = _normalize_analysis(analysis)
    if mode is None:
        raise SpiceParseError(f"โหมดวิเคราะห์ไม่รู้จัก: {analysis}")

    transistor = (
        f"Q1 coll base emit {MODEL_NAME}\n"
        f"{MODEL_CARD}\n"
    )
    header = (
        "* Lab 04 - BJT CE voltage-divider amplifier (generated by spice_engine.py)\n"
        f"* analysis: {mode}\n"
        "* node reference: src = source before CIN, out = load after COUT\n"
    )
    body = (
        f"VCC vcc 0 {_fmt(inputs.vcc_v)}\n"
        f"VIN src 0 DC 0 AC 1 SIN(0 {_fmt(inputs.source_amplitude_v)} "
        f"{_fmt(inputs.source_frequency_hz)})\n"
        f"R1 vcc base {_fmt(inputs.r1_ohm)}\n"
        f"R2 base 0 {_fmt(inputs.r2_ohm)}\n"
        f"RC vcc coll {_fmt(inputs.rc_ohm)}\n"
        f"RE emit 0 {_fmt(inputs.re_ohm)}\n"
        f"CIN src base {_fmt(inputs.cin_f)}\n"
        f"COUT coll out {_fmt(inputs.cout_f)}\n"
        f"RL out 0 {_fmt(inputs.rl_ohm)}\n"
        f"{transistor}"
    )

    if mode == "dc":
        analysis_block = (
            ".op\n"
            ".print op @q1[ic] @q1[ib] @q1[ie]\n"
        )
    elif mode == "ac":
        analysis_block = (
            ".ac dec 20 1 1g\n"
            ".print ac vm(out) vp(out)\n"
        )
    else:
        stop = max(5.0 / inputs.source_frequency_hz, 1e-3)
        step = stop / 1_000.0
        analysis_block = (
            f".tran {_fmt(step)} {_fmt(stop)}\n"
            ".print tran v(src) v(out)\n"
        )
    return header + body + analysis_block + ".end\n"


def _fmt(value: float) -> str:
    """Format a float without locale-dependent decimals."""
    return f"{value:.12g}"


def run_analysis(
    inputs: AmplifierInputs,
    analysis: str = "dc",
    *,
    timeout_s: float = 25.0,
) -> dict[str, Any]:
    """Run one real ngspice analysis and return parsed, JSON-friendly data."""
    mode = _normalize_analysis(analysis)
    if mode is None:
        raise SpiceParseError(f"โหมดวิเคราะห์ไม่รู้จัก: {analysis}")

    ngspice = find_ngspice()
    netlist = build_netlist(inputs, mode)
    version = engine_version(ngspice)

    with tempfile.TemporaryDirectory(prefix="bjt_lab4_") as tmp:
        workdir = Path(tmp)
        circuit = workdir / "circuit.cir"
        log_path = workdir / "run.log"
        circuit.write_text(netlist, encoding="ascii")

        command = [str(ngspice), "-b", "-o", str(log_path), str(circuit)]
        creationflags = 0
        if os.name == "nt":  # avoid a console window when Flask runs
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            completed = subprocess.run(
                command,
                cwd=workdir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_s,
                check=False,
                creationflags=creationflags,
            )
        except subprocess.TimeoutExpired as exc:
            raise SpiceRunError(
                f"ngspice ใช้เวลานานเกิน {timeout_s:.0f} วินาที "
                "กรุณาลดความถี่หรือค่าองค์ประกอบ"
            ) from exc
        except OSError as exc:
            raise SpiceRunError(f"เรียก ngspice ไม่ได้: {exc}") from exc

        log_text = ""
        if log_path.exists():
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
        if not log_text.strip():
            log_text = "\n".join(
                part for part in (completed.stdout, completed.stderr) if part
            )

        if completed.returncode != 0:
            raise SpiceRunError(
                "ngspice จบการทำงานด้วยรหัส "
                f"{completed.returncode}\n{_short_log(log_text)}"
            )
        if not log_text.strip():
            raise SpiceRunError("ngspice ไม่ได้สร้าง Output (ไฟล์ log ว่าง)")
        if "No. of Data Rows : 0" in log_text:
            raise SpiceRunError(
                "ngspice ไม่ได้ข้อมูลผลลัพธ์ (0 data rows)\n"
                f"{_short_log(log_text)}"
            )
        if re.search(r"^\s*Error", log_text, flags=re.MULTILINE):
            raise SpiceRunError(f"ngspice รายงานข้อผิดพลาด\n{_short_log(log_text)}")

        parsed = parse_log(
            log_text, mode, target_hz=inputs.source_frequency_hz
        )
        parsed["analysis"] = mode
        parsed["analysis_label"] = ANALYSIS_LABELS[mode]
        parsed["inputs_si"] = inputs.as_dict()
        parsed["engine"] = {
            "name": "ngspice",
            "version": version,
            "command": ngspice.name,
            "run_mode": "batch",
            "model": {
                "name": MODEL_NAME,
                "source": MODEL_SOURCE,
                "note": MODEL_NOTE,
            },
        }
        parsed["netlist"] = netlist
        parsed["warnings"] = list(parsed.get("warnings", [])) + [MODEL_NOTE]
        return parsed


def find_ngspice() -> Path:
    """Locate the ngspice console executable or raise :class:`NgspiceNotFound`."""
    candidates: list[Path] = []
    env_value = (os.environ.get("NGSPICE_BIN") or "").strip().strip('"')
    if env_value:
        candidates.append(Path(env_value))

    for name in ("ngspice_con", "ngspice_con.exe", "ngspice", "ngspice.exe"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))

    here = Path(__file__).resolve().parent
    candidates.extend(
        [
            here / "tools" / "ngspice47" / "Spice64" / "bin" / "ngspice_con.exe",
            here / "tools" / "ngspice" / "Spice64" / "bin" / "ngspice_con.exe",
            here / "tools" / "ngspice" / "bin" / "ngspice_con.exe",
        ]
    )

    for base in (Path(r"C:\Program Files"), Path(r"C:\Program Files (x86)")):
        if base.exists():
            for directory in sorted(base.glob("ngspice*")):
                candidates.extend(
                    [
                        directory / "Spice64" / "bin" / "ngspice_con.exe",
                        directory / "bin" / "ngspice_con.exe",
                        directory / "Spice64" / "bin" / "ngspice.exe",
                    ]
                )

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise NgspiceNotFound(
        "ไม่พบ ngspice ในเครื่องนี้ กรุณาติดตั้ง ngspice แล้วเพิ่มใน PATH "
        "หรือตั้งค่า environment variable NGSPICE_BIN ให้ชี้ไปที่ ngspice_con.exe"
    )


_VERSION_CACHE: dict[str, str] = {}


def engine_version(ngspice: Path | None = None) -> str:
    """Return a cached ngspice version string such as ``ngspice-47``."""
    path = ngspice or find_ngspice()
    key = str(path)
    if key in _VERSION_CACHE:
        return _VERSION_CACHE[key]

    try:
        completed = subprocess.run(
            [str(path), "-v"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        _VERSION_CACHE[key] = "ngspice (version unknown)"
        return _VERSION_CACHE[key]

    text = f"{completed.stdout}\n{completed.stderr}"
    match = re.search(r"ngspice-\d+(?:\.\d+)?", text)
    _VERSION_CACHE[key] = match.group(0) if match else "ngspice (version unknown)"
    return _VERSION_CACHE[key]


def engine_info() -> dict[str, Any]:
    """Return availability/version/model metadata for the UI status badge."""
    ngspice = find_ngspice()
    return {
        "available": True,
        "name": "ngspice",
        "version": engine_version(ngspice),
        "command": ngspice.name,
        "model": {
            "name": MODEL_NAME,
            "source": MODEL_SOURCE,
            "note": MODEL_NOTE,
        },
    }


def parse_log(
    text: str, analysis: str, *, target_hz: float = 1_000.0
) -> dict[str, Any]:
    """Parse an ngspice batch log for one analysis mode.

    ``target_hz`` selects the frequency reported as the AC operating point
    (the nearest sweep point to the requested source frequency).
    """
    mode = _normalize_analysis(analysis)
    if mode is None:
        raise SpiceParseError(f"โหมดวิเคราะห์ไม่รู้จัก: {analysis}")

    warnings = [
        line.strip()
        for line in text.splitlines()
        if line.strip().lower().startswith("warning:")
    ]
    if mode == "dc":
        data = _parse_op(text)
    elif mode == "ac":
        data = _parse_ac(text, target_hz=target_hz)
    else:
        data = _parse_tran(text)
    data["warnings"] = warnings
    return data


def _parse_op(text: str) -> dict[str, Any]:
    node_voltages: dict[str, float] = {}
    currents: dict[str, float] = {}

    for line in text.splitlines():
        node_match = _NAME_RE.match(line)
        if node_match:
            name, raw_value = node_match.groups()
            value = _to_float(raw_value)
            if value is not None:
                node_voltages[name] = value
            continue
        current_match = _CURRENT_RE.match(line)
        if current_match:
            name, raw_value = current_match.groups()
            value = _to_float(raw_value)
            if value is not None:
                currents[name] = value

    required_nodes = {"vcc", "src", "base", "coll", "emit", "out"}
    missing = required_nodes - set(node_voltages)
    if missing:
        raise SpiceParseError(
            "อ่าน Operating Point จาก ngspice ไม่ครบ: ขาด "
            + ", ".join(sorted(missing))
        )
    if not {"ic", "ib"}.issubset(currents):
        raise SpiceParseError("อ่านกระแส IC/IB จาก ngspice ไม่ครบ")

    vb = node_voltages["base"]
    ve = node_voltages["emit"]
    vc = node_voltages["coll"]
    ic = currents["ic"]
    ib = currents["ib"]
    ie = ic + ib

    return {
        "node_voltages": node_voltages,
        "currents": {
            "ic_a": ic,
            "ib_a": ib,
            "ie_a": ie,
        },
        "operating_point": {
            "vb_v": vb,
            "ve_v": ve,
            "vc_v": vc,
            "vbe_v": vb - ve,
            "vce_v": vc - ve,
            "vbc_v": vb - vc,
            "ic_a": ic,
            "ib_a": ib,
            "ie_a": ie,
        },
    }


def _parse_ac(text: str, *, target_hz: float = 1_000.0) -> dict[str, Any]:
    rows = _numeric_rows(text, expected_columns=4)
    if not rows:
        raise SpiceParseError("ไม่พบข้อมูล AC ใน Output ของ ngspice")

    frequency_hz: list[float] = []
    gain_vv: list[float] = []
    gain_db: list[float] = []
    phase_deg: list[float] = []

    for row in rows:
        _index, frequency, magnitude, phase_rad = row
        if frequency <= 0:
            continue
        frequency_hz.append(frequency)
        gain_vv.append(magnitude)
        gain_db.append(20.0 * math.log10(magnitude) if magnitude > 0 else -240.0)
        phase_deg.append(math.degrees(phase_rad))

    if not frequency_hz:
        raise SpiceParseError("ข้อมูล AC ว่างหรือความถี่ไม่ถูกต้อง")

    phase_deg = _unwrap_phase(phase_deg)

    midband = _midband_summary(frequency_hz, gain_db, gain_vv, phase_deg, target_hz)
    cutoff = _cutoff_summary(frequency_hz, gain_db, midband["gain_db"])

    return {
        "frequency_hz": frequency_hz,
        "gain_vv": gain_vv,
        "gain_db": gain_db,
        "phase_deg": phase_deg,
        "midband": midband,
        "cutoff": cutoff,
    }


def _unwrap_phase(phase_deg: list[float]) -> list[float]:
    """Remove ±360° jumps so the plotted phase curve stays continuous."""
    if not phase_deg:
        return []
    unwrapped = [phase_deg[0]]
    for value in phase_deg[1:]:
        previous = unwrapped[-1]
        adjusted = value
        while adjusted - previous > 180.0:
            adjusted -= 360.0
        while adjusted - previous < -180.0:
            adjusted += 360.0
        unwrapped.append(adjusted)
    return unwrapped


def _parse_tran(text: str) -> dict[str, Any]:
    rows = _numeric_rows(text, expected_columns=4)
    if not rows:
        raise SpiceParseError("ไม่พบข้อมูล Transient ใน Output ของ ngspice")

    time_s: list[float] = []
    vin_v: list[float] = []
    vout_v: list[float] = []
    for row in rows:
        _index, time_value, vin, vout = row
        time_s.append(time_value)
        vin_v.append(vin)
        vout_v.append(vout)

    if len(time_s) < 10:
        raise SpiceParseError("ข้อมูล Transient น้อยเกินไปสำหรับการสรุปผล")

    summary = _tran_summary(time_s, vin_v, vout_v)

    # Keep the JSON payload responsive; the chart does not need 5,000 points.
    max_points = 1_000
    step = max(1, math.ceil(len(time_s) / max_points))
    return {
        "time_s": time_s[::step],
        "vin_v": vin_v[::step],
        "vout_v": vout_v[::step],
        "summary": summary,
        "raw_point_count": len(time_s),
    }


def _numeric_rows(text: str, *, expected_columns: int) -> list[list[float]]:
    rows: list[list[float]] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != expected_columns or not parts[0].isdigit():
            continue
        try:
            rows.append([float(part) for part in parts])
        except ValueError:
            continue
    return rows


def _midband_summary(
    frequencies: list[float],
    gain_db: list[float],
    gain_vv: list[float],
    phase_deg: list[float],
    target_hz: float = 1_000.0,
) -> dict[str, float]:
    index = min(
        range(len(frequencies)),
        key=lambda i: abs(math.log10(frequencies[i] / target_hz)),
    )
    return {
        "target_hz": target_hz,
        "frequency_hz": frequencies[index],
        "gain_db": gain_db[index],
        "gain_vv": gain_vv[index],
        "phase_deg": phase_deg[index],
    }


def _cutoff_summary(
    frequencies: list[float],
    gain_db: list[float],
    midband_gain_db: float,
) -> dict[str, Any]:
    target = midband_gain_db - 3.0
    peak_index = max(range(len(gain_db)), key=lambda i: gain_db[i])

    low = None
    for i in range(peak_index - 1, -1, -1):
        if gain_db[i] <= target:
            low = _interpolate_log_frequency(
                frequencies[i], gain_db[i], frequencies[i + 1], gain_db[i + 1], target
            )
            break

    high = None
    for i in range(peak_index + 1, len(gain_db)):
        if gain_db[i] <= target:
            high = _interpolate_log_frequency(
                frequencies[i - 1], gain_db[i - 1], frequencies[i], gain_db[i], target
            )
            break

    if low is None and high is None:
        note = "not determined in sweep range"
    elif low is None:
        note = "lower -3 dB point not determined in sweep range"
    elif high is None:
        note = "upper -3 dB point not determined in sweep range"
    else:
        note = "both -3 dB points found"
    return {"low_hz": low, "high_hz": high, "note": note}


def _interpolate_log_frequency(
    f1: float, g1: float, f2: float, g2: float, target: float
) -> float:
    if g2 == g1:
        return math.sqrt(f1 * f2)
    fraction = (target - g1) / (g2 - g1)
    return 10.0 ** (
        math.log10(f1) + fraction * (math.log10(f2) - math.log10(f1))
    )


def _tran_summary(
    time_s: list[float], vin_v: list[float], vout_v: list[float]
) -> dict[str, Any]:
    start = int(len(time_s) * 0.40)
    steady_vin = vin_v[start:]
    steady_vout = vout_v[start:]
    vin_pp = max(steady_vin) - min(steady_vin) if steady_vin else 0.0
    vout_pp = max(steady_vout) - min(steady_vout) if steady_vout else 0.0
    gain = vout_pp / vin_pp if vin_pp > 0 else None

    correlation = _correlation(steady_vin, steady_vout)
    inverted = correlation is not None and correlation < 0
    if correlation is None:
        phase_note = "ตรวจเฟสไม่ได้ (สัญญาณอินพุตแบน)"
    elif inverted:
        phase_note = "กลับเฟส (~180°)"
    else:
        phase_note = "ไม่กลับเฟส (~0°)"

    return {
        "vin_pp_v": vin_pp,
        "vout_pp_v": vout_pp,
        "vin_peak_v": max(abs(value) for value in steady_vin) if steady_vin else 0.0,
        "vout_peak_v": max(abs(value) for value in steady_vout) if steady_vout else 0.0,
        "gain_vv": gain,
        "correlation": correlation,
        "inverted": inverted,
        "phase_note": phase_note,
        "time_start_s": time_s[0],
        "time_stop_s": time_s[-1],
    }


def _correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = math.sqrt(
        sum((x - mean_x) ** 2 for x in xs)
        * sum((y - mean_y) ** 2 for y in ys)
    )
    if denominator == 0:
        return None
    return numerator / denominator


def _to_float(text: str) -> float | None:
    if not _NUMBER_RE.match(text):
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _short_log(text: str, limit: int = 1_200) -> str:
    compact = "\n".join(line.rstrip() for line in text.strip().splitlines() if line.strip())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "\n... (ตัดข้อความ)"
