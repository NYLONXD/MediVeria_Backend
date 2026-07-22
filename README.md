# Doctor-Patient Reports API (Auth Module)

## Setup

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate   # on Windows: .\venv\Scripts\Activate
   pip install -r requirements.txt
   ```#this website runs only on python 3.11 versions.

2. Create your PostgreSQL database:
   ```sql
   CREATE DATABASE reports_db;
   ```

3. Copy `.env.example` to `.env` and fill in your real DB credentials and a secret key:
   ```bash
   cp .env.example .env
   ```

4. Run the server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

5. Open the interactive docs at `http://localhost:8000/docs`.

## Endpoints so far

| Method | Path                | Description                          |
|--------|---------------------|---------------------------------------|
| POST   | /api/v1/auth/register | Create a doctor or patient account   |
| POST   | /api/v1/auth/login    | Get a JWT access token               |
| GET    | /api/v1/auth/me       | Get the currently logged-in user     |

`role` in register accepts: `doctor`, `patient`, `admin`.

## Folder structure (MVC-style)

- `models/` – SQLAlchemy tables (the "M")
- `controllers/` – route handlers, thin, call into services (the "C")
- `services/` – actual business logic (register, authenticate, later: fetch reports, generate download links)
- `schemas/` – Pydantic request/response validation (kept separate from models on purpose)
- `core/` – config and security (JWT, password hashing)
- `db/` – database engine/session setup

## Next steps once auth is solid

- Add a `Report` model (patient_id, doctor_id, file_path, uploaded_at, title)
- Add a `report_controller.py` with:
  - `POST /api/v1/reports` (doctor uploads a report for a patient)
  - `GET /api/v1/reports` (patient/doctor lists reports they have access to)
  - `GET /api/v1/reports/{id}/download` (streams the file, protected by `get_current_user` + ownership check)
- Store files either on disk (`/uploads`) or in S3/GCS, keep only the path/key in Postgres
- Add Alembic for proper migrations instead of `create_all()`


pip install --upgrade pip
python.exe -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

