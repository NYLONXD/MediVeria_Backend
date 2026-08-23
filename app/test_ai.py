print("STEP 1: Starting test")

from app.services.ai_service import analyze_report

print("STEP 2: Imported AI service")


report = """
Patient Name: Demo Patient

Blood Test Report:

Hemoglobin: 10.2 g/dL
Reference Range: 13.0 - 17.0 g/dL

WBC: 7,500 /µL
Reference Range: 4,000 - 11,000 /µL

Platelets: 250,000 /µL
Reference Range: 150,000 - 450,000 /µL

The patient reports fatigue.
"""


print("STEP 3: Sending report to Gemini")

result = analyze_report(report)

print("STEP 4: Got response")

print("\n========== AI RESPONSE ==========\n")
print(result)
print("\n=================================")