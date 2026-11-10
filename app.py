from flask import Flask, jsonify, render_template, request

from dc_bias import DcBiasResult, calculate_dc_bias, parse_inputs

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/calculate")
def calculate():
    inputs, errors = parse_inputs(request.form)
    if errors:
        return jsonify({
            "ok": False,
            "errors": errors,
            "message": "กรุณาตรวจสอบค่าที่ป้อน",
        }), 400

    return jsonify({"ok": True, "data": _serialize(calculate_dc_bias(inputs))})


def _serialize(result: DcBiasResult) -> dict:
    inputs = result.inputs_si
    return {
        "inputs_si": {
            "vcc_v": inputs.vcc_v,
            "r1_ohm": inputs.r1_ohm,
            "r2_ohm": inputs.r2_ohm,
            "rc_ohm": inputs.rc_ohm,
            "re_ohm": inputs.re_ohm,
            "beta": inputs.beta,
            "vbe_v": inputs.vbe_v,
        },
        "intermediate": {
            "vth_v": result.vth_v,
            "rth_ohm": result.rth_ohm,
        },
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
