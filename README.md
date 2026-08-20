# MedVault / MediVeria Backend

Secure FastAPI backend for a medical record platform that lets hospitals, doctors, and patients manage lifelong medical reports with authenticated Cloudinary storage.

## Current capabilities

- JWT/cookie authentication for patients, doctors, admins, and hospital admins.
- Doctor and patient profile rows are created during registration.
- Cloudinary-backed report upload with authenticated assets instead of public URLs.
- Registered-patient and pending-patient report ownership routes.
- Report file metadata, checksums, audit logging, and PostgreSQL models aligned with the MedVault schema.
- Processing pipeline records that identify PDF/image, DICOM, and structured inputs and enqueue the correct next jobs.
- Protected report listing and detail endpoints scoped by user role.

## Setup

1. Use Python 3.11 and install dependencies:

   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Configure `.env`:

   ```env
   DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/medvault
   SECRET_KEY=change-me
   FRONTEND_ORIGIN=http://localhost:5173
   CLOUDINARY_CLOUD_NAME=your-cloud-name
   CLOUDINARY_API_KEY=your-api-key
   CLOUDINARY_API_SECRET=your-api-secret
   CLOUDINARY_MEDICAL_FOLDER=medvault/reports
   ```

3. Run the server:

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

4. Open API docs at `http://localhost:8000/docs`.

## Key endpoints

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | Create a patient, doctor, admin, or hospital admin account. |
| POST | `/api/v1/auth/login` | Login and set the access-token cookie. |
| GET | `/api/v1/auth/me` | Get the current authenticated user. |
| POST | `/api/v1/auth/logout` | Clear the access-token cookie. |
| POST | `/api/v1/reports` | Doctor uploads one or more files for a registered or pending patient. |
| GET | `/api/v1/reports` | List reports visible to the current user. |
| GET | `/api/v1/reports/{report_id}` | Fetch one protected report with file metadata. |


## Processing pipeline status

The backend now **models and queues** the architecture below, but it does **not yet run real OCR, DICOM parsing, table extraction, waveform processing, medical NLP, or AI explanations**. Those require worker services such as Celery/RQ/Arq plus OCR/DICOM/AI libraries or external APIs.

Current upload behavior:

1. Store the original file in authenticated Cloudinary storage.
2. Detect the source format from MIME type or filename: PDF, image, DICOM, or structured.
3. Create queued `processing_jobs` rows for the required pipeline:
   - PDF/image blood and lab reports: virus scan, table extraction, OCR, normalization, AI analysis.
   - PDF/image MRI, X-ray, prescriptions, notes, summaries: virus scan, OCR/text extraction path, normalization, AI analysis.
   - DICOM MRI/CT/ECG scans: virus scan, DICOM parsing, thumbnail generation, optional ECG waveform processing, normalization, AI analysis.
   - Structured JSON/CSV-like uploads: virus scan, structured extraction, normalization, AI analysis.
4. Return report metadata plus queued jobs to the API client.

Next implementation step: add a background worker that consumes `processing_jobs`, writes OCR/parser output to `report_extractions`, stores lab values in `report_measurements`, and writes patient-safe explanations to `ai_analysis`.

## Report upload payload

`POST /api/v1/reports` expects multipart form data:

- `payload`: JSON string matching `ReportCreate`.
- `files`: one or more medical report files.

Example `payload` for an unregistered patient:

```json
{
  "pending_patient": {
    "full_name": "Amina Patel",
    "phone": "+15555550123",
    "dob": "1995-04-16"
  },
  "report_type": "blood_test",
  "title": "CBC Report",
  "description": "Complete blood count",
  "report_date": "2026-08-20"
}
```

Cloudinary uploads use `type="authenticated"`, so application code should generate short-lived signed access URLs rather than exposing raw public objects.
