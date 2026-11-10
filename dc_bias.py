"""DC bias calculations for a BJT voltage-divider biased common-emitter stage.

Pure engineering logic: no Flask, no HTML, no HTTP. All values are in SI
base units (volts, amps, ohms). Model assumption: forward-active
approximation with constant beta and constant VBE.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

_UNIT_FACTORS = {"ohm": 1.0, "kohm": 1_000.0}
_RESISTOR_FIELDS = (("r1", "R1"), ("r2", "R2"), ("rc", "RC"), ("re", "RE"))
VCE_SATURATION_THRESHOLD_V = 0.3


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
class DcBiasResult:
    inputs_si: DcBiasInputs
    vth_v: float
    rth_ohm: float
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


def parse_inputs(raw: Mapping[str, str]) -> tuple[DcBiasInputs | None, dict[str, str]]:
    """Convert raw form strings to SI units and validate them.

    Returns (inputs, {}) when everything is valid, otherwise (None, errors)
    where errors is keyed by the base field name (r1, rc, beta, ...).
    """
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
    for key, label in _RESISTOR_FIELDS:
        value = _parse_number(raw, key, label, errors)
        unit = (raw.get(f"{key}_unit") or "").strip().lower()
        if unit not in _UNIT_FACTORS:
            errors[key] = f"หน่วยของ {label} ต้องเป็น ohm หรือ kohm"
            ohms[key] = None
            continue
        if value is not None and value <= 0:
            errors[key] = f"{label} ต้องมากกว่า 0 Ω"
        ohms[key] = None if value is None else value * _UNIT_FACTORS[unit]

    if errors:
        return None, errors

    inputs = DcBiasInputs(
        vcc_v=vcc,
        r1_ohm=ohms["r1"],
        r2_ohm=ohms["r2"],
        rc_ohm=ohms["rc"],
        re_ohm=ohms["re"],
        beta=beta,
        vbe_v=vbe,
    )
    return inputs, {}


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
    vth = inputs.vcc_v * inputs.r2_ohm / (inputs.r1_ohm + inputs.r2_ohm)
    rth = inputs.r1_ohm * inputs.r2_ohm / (inputs.r1_ohm + inputs.r2_ohm)
    ib = (vth - inputs.vbe_v) / (rth + (inputs.beta + 1.0) * inputs.re_ohm)
    ic = inputs.beta * ib
    ie = (inputs.beta + 1.0) * ib
    ve = ie * inputs.re_ohm
    vb = ve + inputs.vbe_v
    vc = inputs.vcc_v - ic * inputs.rc_ohm
    vce = vc - ve
    vbc = vb - vc

    region, warnings = _classify_region(vth, inputs.vbe_v, vce)

    return DcBiasResult(
        inputs_si=inputs,
        vth_v=vth,
        rth_ohm=rth,
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
    )


def _classify_region(vth_v: float, vbe_v: float, vce_v: float) -> tuple[str, list[str]]:
    """Decide the operating region and explain any model limitation."""
    if vth_v <= vbe_v:
        return "cutoff", [
            f"VTH ({vth_v:.3f} V) ≤ VBE ({vbe_v:.2f} V) — ทรานซิสเตอร์"
            " ไม่อยู่ใน Forward-Active; ค่าที่คำนวณจากสมการนี้ใช้ไม่ได้"
        ]
    if vce_v < VCE_SATURATION_THRESHOLD_V:
        return "saturation", [
            f"VCE ({vce_v:.3f} V) < {VCE_SATURATION_THRESHOLD_V:.1f} V — "
            "อยู่ในหรือใกล้ Saturation; forward-active approximation ไม่แม่นยำ"
        ]
    return "forward_active", []
