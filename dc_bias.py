"""DC bias calculations for a BJT common-emitter stage (three bias modes).

Voltage-divider, fixed-bias and emitter-bias stages share one forward-active
approximation (constant beta and constant VBE).

Pure engineering logic: no Flask, no HTML, no HTTP. All values are in SI
base units (volts, amps, ohms).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

_UNIT_FACTORS = {"ohm": 1.0, "kohm": 1_000.0}
_RESISTOR_LABELS = {"r1": "R1", "r2": "R2", "rc": "RC", "re": "RE", "rb": "RB"}
_MODE_RESISTORS = {
    "divider": ("r1", "r2", "rc", "re"),
    "fixed": ("rc", "rb"),
    "emitter": ("rc", "re", "rb"),
}
VCE_SATURATION_THRESHOLD_V = 0.2


@dataclass(frozen=True)
class DcBiasInputs:
    vcc_v: float
    r1_ohm: float
    r2_ohm: float
    rc_ohm: float
    re_ohm: float
    beta: float
    vbe_v: float


@dataclass(frozen=True)
class FixedBiasInputs:
    vcc_v: float
    rb_ohm: float
    rc_ohm: float
    beta: float
    vbe_v: float


@dataclass(frozen=True)
class EmitterBiasInputs:
    vcc_v: float
    rb_ohm: float
    rc_ohm: float
    re_ohm: float
    beta: float
    vbe_v: float


@dataclass(frozen=True)
class DcBiasResult:
    inputs_si: DcBiasInputs | FixedBiasInputs | EmitterBiasInputs
    vth_v: float | None
    rth_ohm: float | None
    ib_a: float
    ic_a: float
    ie_a: float
    vb_v: float
    ve_v: float
    vc_v: float
    vce_v: float
    vbc_v: float
    region: str
    warnings: list[str]
    mode: str = "divider"


def parse_inputs(
    raw: Mapping[str, str], mode: str = "divider"
) -> tuple[DcBiasInputs | FixedBiasInputs | EmitterBiasInputs | None, dict[str, str]]:
    """Convert raw form strings to SI units and validate them for one bias mode.

    Only the resistors the chosen mode needs are read; other fields are
    ignored. Returns (inputs, {}) when everything is valid, otherwise
    (None, errors) where errors is keyed by the base field name
    (mode, r1, rb, rc, beta, ...).
    """
    mode = (mode or "").strip().lower()
    if mode not in _MODE_RESISTORS:
        return None, {"mode": f"โหมดไม่รู้จัก: {mode or '(ว่าง)'}"}

    errors: dict[str, str] = {}

    vcc = _parse_number(raw, "vcc", "VCC", errors)
    beta = _parse_number(raw, "beta", "β", errors)
    vbe = _parse_number(raw, "vbe", "VBE", errors)

    if vcc is not None and vcc <= 0:
        errors["vcc"] = "VCC ต้องมากกว่า 0 V"
    if beta is not None and beta <= 0:
        errors["beta"] = "β ต้องมากกว่า 0"
    if vbe is not None and not 0.0 <= vbe <= 2.0:
        errors["vbe"] = "VBE ต้องอยู่ระหว่าง 0 ถึง 2 V"

    ohms: dict[str, float | None] = {}
    for key in _MODE_RESISTORS[mode]:
        label = _RESISTOR_LABELS[key]
        value = _parse_number(raw, key, label, errors)
        if value is None:
            ohms[key] = None
            continue
        unit = (raw.get(f"{key}_unit") or "").strip().lower()
        if unit not in _UNIT_FACTORS:
            errors[key] = f"หน่วยของ {label} ต้องเป็น ohm หรือ kohm"
            ohms[key] = None
            continue
        if value <= 0:
            errors[key] = f"{label} ต้องมากกว่า 0 Ω"
            ohms[key] = None
            continue
        ohms[key] = value * _UNIT_FACTORS[unit]
        if not math.isfinite(ohms[key]):
            errors[key] = f"{label} มีค่ามากเกินกว่าที่คำนวณได้"
            ohms[key] = None

    if errors:
        return None, errors

    common = {"vcc_v": vcc, "rc_ohm": ohms["rc"], "beta": beta, "vbe_v": vbe}
    if mode == "divider":
        return DcBiasInputs(
            **common, r1_ohm=ohms["r1"], r2_ohm=ohms["r2"], re_ohm=ohms["re"]
        ), {}
    if mode == "fixed":
        return FixedBiasInputs(**common, rb_ohm=ohms["rb"]), {}
    if mode == "emitter":
        return EmitterBiasInputs(**common, rb_ohm=ohms["rb"], re_ohm=ohms["re"]), {}
    return None, {"mode": f"โหมดไม่รู้จัก: {mode}"}


def _parse_number(
    raw: Mapping[str, str], key: str, label: str, errors: dict[str, str]
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
    return value


def calculate_dc_bias(inputs: DcBiasInputs) -> DcBiasResult:
    """Voltage-divider bias: R1/R2 set the base voltage through the Thevenin source."""
    vth = inputs.vcc_v * inputs.r2_ohm / (inputs.r1_ohm + inputs.r2_ohm)
    rth = inputs.r1_ohm * inputs.r2_ohm / (inputs.r1_ohm + inputs.r2_ohm)
    ib = (vth - inputs.vbe_v) / (rth + (inputs.beta + 1.0) * inputs.re_ohm)
    return _assemble(inputs, ib, inputs.re_ohm, "divider", vth_v=vth, rth_ohm=rth)


def calculate_fixed_bias(inputs: FixedBiasInputs) -> DcBiasResult:
    """Fixed-bias stage: RB from VCC to base, emitter grounded."""
    ib = (inputs.vcc_v - inputs.vbe_v) / inputs.rb_ohm
    return _assemble(inputs, ib, 0.0, "fixed")


def calculate_emitter_bias(inputs: EmitterBiasInputs) -> DcBiasResult:
    """Emitter-bias stage: RB from VCC to base, RE in the emitter leg."""
    ib = (inputs.vcc_v - inputs.vbe_v) / (
        inputs.rb_ohm + (inputs.beta + 1.0) * inputs.re_ohm
    )
    return _assemble(inputs, ib, inputs.re_ohm, "emitter")


def _assemble(
    inputs: DcBiasInputs | FixedBiasInputs | EmitterBiasInputs,
    ib: float,
    re_ohm: float,
    mode: str,
    vth_v: float | None = None,
    rth_ohm: float | None = None,
) -> DcBiasResult:
    """Shared operating-point arithmetic for every bias mode."""
    ic = inputs.beta * ib
    ie = (inputs.beta + 1.0) * ib
    ve = ie * re_ohm
    vb = ve + inputs.vbe_v
    vc = inputs.vcc_v - ic * inputs.rc_ohm
    vce = vc - ve
    vbc = vb - vc

    region, warnings = _classify_region(ib, vce)

    return DcBiasResult(
        inputs_si=inputs,
        vth_v=vth_v,
        rth_ohm=rth_ohm,
        ib_a=ib,
        ic_a=ic,
        ie_a=ie,
        vb_v=vb,
        ve_v=ve,
        vc_v=vc,
        vce_v=vce,
        vbc_v=vbc,
        region=region,
        warnings=warnings,
        mode=mode,
    )


def _classify_region(ib_a: float, vce_v: float) -> tuple[str, list[str]]:
    """Decide the operating region and explain any model limitation."""
    if ib_a <= 0:
        return "cutoff", [
            f"IB ({ib_a * 1e6:.3f} µA) ≤ 0 — ทรานซิสเตอร์ไม่อยู่ใน Forward-Active;"
            " ค่าที่คำนวณจากสมการนี้ใช้ไม่ได้"
        ]
    if vce_v <= VCE_SATURATION_THRESHOLD_V:
        return "saturation", [
            f"VCE ({vce_v:.3f} V) ≤ {VCE_SATURATION_THRESHOLD_V:.1f} V — "
            "อยู่ในหรือใกล้ Saturation; forward-active approximation ไม่แม่นยำ"
        ]
    return "forward_active", []
