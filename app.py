import math
from dataclasses import fields

from flask import Flask, Response, jsonify, render_template, request

from dc_bias import (
    DcBiasInputs,
    DcBiasResult,
    EmitterBiasInputs,
    FixedBiasInputs,
    calculate_dc_bias,
    calculate_emitter_bias,
    calculate_fixed_bias,
    parse_inputs,
)

app = Flask(__name__)

_RESULT_FLOATS = (
    "vth_v",
    "rth_ohm",
    "ib_a",
    "ic_a",
    "ie_a",
    "vb_v",
    "ve_v",
    "vc_v",
    "vce_v",
    "vbc_v",
)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/calculate")
def calculate():
    # An absent field means "legacy client" -> divider; a present but blank
    # value is a client error and must not silently become divider.
    raw_mode = request.form.get("mode")
    mode = "divider" if raw_mode is None else raw_mode.strip().lower()

    inputs, errors = parse_inputs(request.form, mode)
    if errors:
        return _error_response(mode, errors)

    result = _calculate_for_mode(mode, inputs)
    if result is None:  # defensive: parse_inputs already rejects unknown modes
        return _error_response(mode, {"mode": f"โหมดไม่รู้จัก: {mode}"})

    if not _all_finite(result):
        return _error_response(
            mode,
            {"result": "ค่าที่คำนวณได้เกินขอบเขตตัวเลข"},
            "ค่าอุปกรณ์ทำให้ผลลัพธ์เกินขอบเขตตัวเลข กรุณาลดค่าลง",
        )

    return jsonify({"ok": True, "data": _serialize(result)})


def _calculate_for_mode(
    mode: str,
    inputs: DcBiasInputs | FixedBiasInputs | EmitterBiasInputs,
) -> DcBiasResult | None:
    if mode == "divider" and isinstance(inputs, DcBiasInputs):
        return calculate_dc_bias(inputs)
    if mode == "fixed" and isinstance(inputs, FixedBiasInputs):
        return calculate_fixed_bias(inputs)
    if mode == "emitter" and isinstance(inputs, EmitterBiasInputs):
        return calculate_emitter_bias(inputs)
    return None


def _all_finite(result: DcBiasResult) -> bool:
    """Guard the JSON contract: Infinity/NaN cannot be serialized as JSON."""
    for name in _RESULT_FLOATS:
        value = getattr(result, name)
        if value is not None and not math.isfinite(value):
            return False
    for field in fields(result.inputs_si):
        if not math.isfinite(getattr(result.inputs_si, field.name)):
            return False
    return True


def _error_response(
    mode: str,
    errors: dict[str, str],
    message: str = "กรุณาตรวจสอบค่าที่ป้อน",
) -> tuple[Response, int]:
    return jsonify({
        "ok": False,
        "mode": mode,
        "errors": errors,
        "message": message,
    }), 400


def _serialize(result: DcBiasResult) -> dict:
    return {
        "mode": result.mode,
        "inputs_si": _serialize_inputs(result.inputs_si),
        "intermediate": _serialize_intermediate(result),
        "operating_point": {
            "ib_a": result.ib_a,
            "ic_a": result.ic_a,
            "ie_a": result.ie_a,
            "vb_v": result.vb_v,
            "ve_v": result.ve_v,
            "vc_v": result.vc_v,
            "vce_v": result.vce_v,
            "vbc_v": result.vbc_v,
        },
        "region": result.region,
        "warnings": list(result.warnings),
    }


def _serialize_inputs(
    inputs: DcBiasInputs | FixedBiasInputs | EmitterBiasInputs,
) -> dict:
    data = {
        "vcc_v": inputs.vcc_v,
        "rc_ohm": inputs.rc_ohm,
        "beta": inputs.beta,
        "vbe_v": inputs.vbe_v,
    }
    if isinstance(inputs, DcBiasInputs):
        data["r1_ohm"] = inputs.r1_ohm
        data["r2_ohm"] = inputs.r2_ohm
        data["re_ohm"] = inputs.re_ohm
    else:
        data["rb_ohm"] = inputs.rb_ohm
        if isinstance(inputs, EmitterBiasInputs):
            data["re_ohm"] = inputs.re_ohm
    return data


def _serialize_intermediate(result: DcBiasResult) -> dict:
    if result.vth_v is None or result.rth_ohm is None:
        return {}
    return {"vth_v": result.vth_v, "rth_ohm": result.rth_ohm}
