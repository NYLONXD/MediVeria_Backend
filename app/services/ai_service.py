"""Deterministic analysis used by the prototype.

This intentionally does not call an external model. It provides a stable,
safe presentation response for demos and must not be treated as a diagnosis.
"""

from collections.abc import Iterable


SAFETY_DISCLAIMER = (
    "Prototype-generated information only. It is not a diagnosis and must be "
    "reviewed by a qualified healthcare professional."
)


def build_demo_analysis(report_title: str, measurements: Iterable[object]) -> dict:
    """Create a predictable, patient-safe result from parsed measurements."""
    flagged = []
    for measurement in measurements:
        flag = (getattr(measurement, "abnormal_flag", None) or "").lower()
        if flag and flag not in {"normal", "none"}:
            value = getattr(measurement, "value_numeric", None)
            flagged.append({
                "test": getattr(measurement, "test_name", "Reported measurement"),
                "flag": flag,
                "value": str(value if value is not None else getattr(measurement, "value_text", "")),
            })

    if flagged:
        summary = f"The prototype found {len(flagged)} result(s) marked for attention in {report_title}."
        explanation = "Some recorded values are outside their listed reference range. A clinician should interpret them with symptoms and medical history."
        recommendations = ["Review the flagged values with the treating clinician.", "Seek prompt medical advice if symptoms are severe or worsening."]
    else:
        summary = f"{report_title} has been processed and is ready for clinical review."
        explanation = "No automatically flagged measurement is available in this uploaded report. This does not confirm that all findings are normal."
        recommendations = ["Review the report with a qualified healthcare professional.", "Keep this report with the patient's clinical record."]

    return {
        "summary": summary,
        "simplified_explanation": explanation,
        "risk_indicators": flagged,
        "recommendations": recommendations,
        "confidence_score": 1.0,
        "model_name": "MediVeria demo analysis",
        "model_version": "static-v1",
        "prompt_version": "prototype",
        "safety_disclaimer": SAFETY_DISCLAIMER,
    }


def analyze_report(report_text: str) -> str:
    """Compatibility helper for the existing local smoke-test script."""
    return build_demo_analysis("Medical report", [])['summary']
