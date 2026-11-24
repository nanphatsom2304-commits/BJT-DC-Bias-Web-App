import math
from dataclasses import fields

from flask import Flask, Response, jsonify, render_template, request

import spice_engine
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

# Lab 3 analytical reference for the same circuit: constant beta and VBE.
REFERENCE_BETA = 100.0
REFERENCE_VBE_V = 0.70

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


@app.get("/api/engine")
def engine_status():
    """Report whether ngspice is usable, so the UI can show a truthful badge."""
    try:
        data = spice_engine.engine_info()
    except spice_engine.NgspiceNotFound as exc:
        return jsonify({
            "ok": True,
            "data": {"available": False, "message": str(exc)},
        })
    return jsonify({"ok": True, "data": data})


@app.post("/api/simulate")
def simulate():
    """Run a real ngspice analysis for the reference CE stage."""
    # The simulator form prefixes its fields with ``sim_`` so the page can host
    # both the Lab 3 form and this form without duplicate ids or names.
    raw = {key.removeprefix("sim_"): value for key, value in request.form.items()}
    analysis = (raw.get("analysis") or "dc").strip().lower()

    inputs, errors = spice_engine.parse_inputs(raw, analysis)
    if errors:
        return jsonify({
            "ok": False,
            "analysis": analysis,
            "errors": errors,
            "message": "กรุณาตรวจสอบค่าที่ป้อน",
        }), 400

    try:
        data = spice_engine.run_analysis(inputs, analysis)
    except spice_engine.NgspiceNotFound as exc:
        return jsonify({
            "ok": False,
            "analysis": analysis,
            "engine_unavailable": True,
            "message": str(exc),
        }), 503
    except spice_engine.SpiceError as exc:
        return jsonify({
            "ok": False,
            "analysis": analysis,
            "message": str(exc),
        }), 502

    data["reference"] = _analytical_reference(inputs)
    return jsonify({"ok": True, "data": data})


def _analytical_reference(inputs: spice_engine.AmplifierInputs) -> dict:
    """Lab 3 closed-form DC bias for the same resistor values (beta=100, VBE=0.70 V)."""
    reference_inputs = DcBiasInputs(
        vcc_v=inputs.vcc_v,
        r1_ohm=inputs.r1_ohm,
        r2_ohm=inputs.r2_ohm,
        rc_ohm=inputs.rc_ohm,
        re_ohm=inputs.re_ohm,
        beta=REFERENCE_BETA,
        vbe_v=REFERENCE_VBE_V,
    )
    result = calculate_dc_bias(reference_inputs)
    return {
        "assumptions": {
            "beta": REFERENCE_BETA,
            "vbe_v": REFERENCE_VBE_V,
            "note": "สมการ Lab 3 (β คงที่, VBE คงที่) ใช้เป็นค่าอ้างอิงเทียบกับ ngspice",
        },
        "operating_point": {
            "vb_v": result.vb_v,
            "ve_v": result.ve_v,
            "vc_v": result.vc_v,
            "vce_v": result.vce_v,
            "ic_a": result.ic_a,
            "ib_a": result.ib_a,
            "ie_a": result.ie_a,
        },
        "vth_v": result.vth_v,
        "rth_ohm": result.rth_ohm,
        "region": result.region,
    }


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
