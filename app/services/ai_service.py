import os

from dotenv import load_dotenv
from google import genai


# --------------------------------------------------
# Load environment variables
# --------------------------------------------------

load_dotenv(
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        ".env"
    )
)


# --------------------------------------------------
# Gemini API configuration
# --------------------------------------------------

api_key = os.getenv("GEMINI_API_KEY")

print("Checking Gemini API key...")

if api_key:
    print("GEMINI_API_KEY found")
else:
    print("GEMINI_API_KEY NOT found")
    raise RuntimeError("GEMINI_API_KEY is missing from .env")


client = genai.Client(api_key=api_key)


# --------------------------------------------------
# Analyze medical report
# --------------------------------------------------

def analyze_report(report_text: str) -> str:

    prompt = f"""
You are an AI assistant for MediVeria,
a medical record management platform.

Analyze the following medical report.

Tasks:

1. Provide a short summary.
2. Explain the findings in simple language.
3. Identify potentially abnormal findings.
4. Mention possible risk indicators.
5. Do NOT provide a definitive diagnosis.
6. Do NOT replace a qualified healthcare professional.
7. Clearly state that the result should be reviewed
   by a qualified healthcare professional.

Medical Report:

{report_text}
"""

    response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents=prompt
)

    return response.text