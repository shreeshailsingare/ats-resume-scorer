# ATS Resume Scorer

A full-stack ATS optimization platform for reviewing resumes against job descriptions, surfacing actionable improvement signals, and storing analysis history per authenticated user.

This repository contains a FastAPI backend for parsing and scoring resumes, a Streamlit frontend for user interaction, Supabase-based authentication and history storage, and a set of research notebooks for exploratory NLP work.

## Overview

The application allows a user to:

- Upload a resume in PDF, DOC, or DOCX format
- Optionally provide a job description in plain text or a `.txt` file
- Receive a structured ATS score and category breakdown
- Compare resume content against job description keywords and skills
- Validate whether listed skills are supported by project or experience evidence
- Download a PDF report generated from the analysis result
- View and delete prior analysis history tied to their account

## Technology stack

- Frontend: Streamlit
- Backend: FastAPI + Uvicorn
- Data validation: Pydantic
- NLP: spaCy
- Embeddings / similarity: SentenceTransformers + NumPy
- Resume parsing: PyPDF2, pdfplumber, python-docx, python-magic
- ATS matching: RapidFuzz
- LLM parsing: Groq API (`llama-3.3-70b-versatile`)
- Authentication and persistence: Supabase
- JWT verification: PyJWT
- PDF export: Jinja2 + WeasyPrint
- HTTP clients: httpx, requests

## Project structure

```text
ats-resume-scorer/
├── backend/
│   ├── api/
│   │   ├── auth.py
│   │   └── routes.py
│   ├── core/
│   │   └── config.py
│   ├── database/
│   │   └── supabase_db.py
│   ├── models/
│   │   └── schemas.py
│   ├── services/
│   │   ├── ats_scorer.py
│   │   ├── feedback_engine.py
│   │   ├── groq_parser.py
│   │   ├── jd_matcher.py
│   │   ├── pdf_export.py
│   │   ├── recommendation_engine.py
│   │   ├── report_generator.py
│   │   ├── resume_analyzer.py
│   │   ├── resume_parser.py
│   │   └── ...
│   ├── templates/
│   │   ├── action_items.html
│   │   ├── jd_comparison.html
│   │   ├── quick_actions.html
│   │   └── summary.html
│   ├── utils/
│   │   ├── file_utils.py
│   │   └── matching.py
│   └── main.py
├── frontend/
│   ├── assets/
│   │   └── styles.css
│   ├── components/
│   │   ├── action_items.py
│   │   ├── dashboard.py
│   │   ├── detailed_feedback.py
│   │   ├── jd_comparison.py
│   │   ├── recommendations.py
│   │   ├── score_display.py
│   │   ├── skill_validation.py
│   │   └── strengths_issues.py
│   ├── services/
│   │   ├── api_client.py
│   │   └── supabase_client.py
│   ├── views/
│   │   ├── history.py
│   │   ├── landing.py
│   │   ├── resources.py
│   │   └── scorer.py
│   ├── .streamlit/
│   │   └── config.toml
│   └── streamlit_app.py
├── jupyter notebooks/
│   ├── 01_EDA_and_DATA_prep.ipynb
│   ├── 02_BERT_EMBEDDINGS.ipynb
│   └── 03_BERT_FINETUNEipynb.ipynb
├── .gitignore
├── requirements.txt
├── README.md
└── .env (local, not committed)
```

## Features

### Resume parsing and validation

The backend validates uploaded files before reading them:

- Maximum upload size: 5 MB
- Supported MIME types: PDF, DOC, DOCX
- Supported extensions: `.pdf`, `.doc`, `.docx`
- File content is extracted using either `pdfplumber` or `PyPDF2` for PDFs, and `python-docx` for DOCX files
- A legacy `.doc` upload intentionally raises a clear error, directing the user to convert the file to PDF or DOCX

### ATS scoring model

The scoring pipeline is assembled in `backend/services/resume_analyzer.py` and uses the following weighted categories from `backend/core/config.py`:

- Formatting: 20%
- Keywords: 25%
- Content: 25%
- Skill validation: 15%
- ATS compatibility: 15%

The app also computes an overall ATS score and includes an interpretation string for the final gate.

### JD comparison

If a job description is provided, the app:

- Parses the JD with Groq
- Extracts keywords, required skills, and preferred skills
- Compares resume skills and keywords against the JD
- Computes semantic similarity with SentenceTransformer embeddings
- Identifies matched and missing keywords
- Highlights skills gaps

### Skill validation

The score engine validates whether each detected skill is backed by an actual project or experience section. This is done by comparing skill names with project texts and experience descriptions using semantic similarity thresholds.

The response schema includes:

- `validated`: list of skills with the projects or sections that evidence them
- `unvalidated`: skills that lack supporting evidence
- `total`
- `validated_count`
- `validation_pct`

### Issue detection and recommendations

The `feedback_engine.py` module builds structured issue entries such as:

- Missing Projects Section
- Missing Work Experience Section
- Missing Education Section
- Missing or Weak Skills Section
- Privacy or location concerns in contact text
- Weak bullet formatting or low ATS readability

Each issue includes:

- a title
- severity
- ATS impact
- explanation
- location in the resume
- how to fix it
- suggested action items
- an example improvement

### PDF report generation

The app can generate a combined PDF report from the analysis result using:

- Jinja2 HTML templates under `backend/templates/`
- WeasyPrint for final rendering

Templates include summary, action items, quick actions, and JD comparison sections.

### History and data persistence

Authenticated users can retrieve and delete prior analyses from Supabase.

The database helper in `backend/database/supabase_db.py` writes entries into the `analyses` table with fields including:

- `user_id`
- `filename`
- `ats_score`
- `keyword_match`
- `missing_keywords`
- `created_at`
- `analysis_result` (full JSON payload)

The backend fetches history by filtering on `user_id` and ordering by `created_at.desc`.

## API endpoints

The FastAPI app is mounted in `backend/main.py` and includes routes at `/api/v1`.

### Public health

- `GET /api/v1/health`

Returns whether the spaCy NLP model and embedder are loaded.

### Authenticated analysis and exports

- `POST /api/v1/analyze-resume`
  - Body: resume file upload + optional `job_description` form field
  - Requires Bearer JWT auth
  - Returns `AnalysisResponse`

- `GET /api/v1/history`
  - Requires Bearer JWT auth
  - Returns the signed-in user's prior analyses

- `DELETE /api/v1/history/{analysis_id}`
  - Requires Bearer JWT auth
  - Deletes a single stored analysis if it belongs to the user

- `POST /api/v1/generate-pdf`
  - Requires Bearer JWT auth
  - Accepts an `AnalysisResponse` payload and returns a PDF download

- `GET /api/v1/history/{analysis_id}/pdf`
  - Requires Bearer JWT auth
  - Generates a PDF for a previously saved analysis

The root endpoint (`GET /`) returns basic metadata and available endpoints.

## Authentication flow

### Frontend auth (Streamlit)

The Streamlit app (`frontend/streamlit_app.py`) manages authentication with the Supabase client in `frontend/services/supabase_client.py`.

Supported flows:

- Email/password sign-in
- Email/password sign-up
- Google OAuth sign-in
- Local session state for access and refresh tokens

The frontend uses `st.query_params` to handle the OAuth redirect callback and exchanges the authorization code for a Supabase session.

### Backend auth (FastAPI)

The backend verifies JWTs in `backend/api/auth.py`.

Behavior:

- Reads the bearer token from the `Authorization` header
- Verifies it against either:
  - Supabase JWKS (`SUPABASE_URL` + public signing keys), or
  - `SUPABASE_JWT_SECRET` for HS256 tokens
- Extracts the `sub` claim as the authenticated user ID
- Returns 401 for expired or invalid tokens

This allows the frontend to call the backend with tokens issued by Supabase and keep user-specific history isolated.

## Environment variables

The application expects these runtime settings.

### Backend `.env`

```env
SUPABASE_URL="https://<project-ref>.supabase.co"
SUPABASE_KEY="<service-role-or-anon-key-for-db-write-access>"
SUPABASE_ANON_KEY="<public-anon-key>"
SUPABASE_JWT_SECRET="<supabase-jwt-secret>"
GROQ_API_KEY="<groq-api-key>"
SENTENCE_TRANSFORMER_MODEL="all-MiniLM-L6-v2"
```

Notes:

- `SUPABASE_URL` and `SUPABASE_JWT_SECRET` are used for backend JWT verification
- `SUPABASE_KEY` is used by the backend database helper to make Supabase REST calls with service-role access
- `SUPABASE_ANON_KEY` is used by the frontend auth client
- `GROQ_API_KEY` is required for the resume/JD parsing pipeline
- `SENTENCE_TRANSFORMER_MODEL` is optional and defaults to `all-MiniLM-L6-v2`

### Frontend Streamlit secrets

The frontend can also read configuration from `frontend/.streamlit/secrets.toml` or environment variables, as implemented in `frontend/services/supabase_client.py`.

Example:

```toml
[supabase]
SUPABASE_URL = "https://<project-ref>.supabase.co"
SUPABASE_ANON_KEY = "<public-anon-key>"

[google_oauth]
redirect_uri = "http://localhost:8501"

[backend]
url = "http://localhost:8000"
```

## Required dependencies

The project dependencies are consolidated in `requirements.txt`:

- fastapi
- uvicorn
- pydantic
- python-multipart
- python-dotenv
- spacy
- sentence-transformers
- numpy
- rapidfuzz
- pdfplumber
- PyPDF2
- python-docx
- python-magic
- jinja2
- weasyprint
- httpx
- groq
- PyJWT[crypto]
- streamlit
- requests
- supabase

## Setup and run

### 1. Create a virtual environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Download the spaCy model used by the app

The runtime config in `backend/core/config.py` loads `en_core_web_sm` first and falls back to the same model if it is missing.

```bash
python -m spacy download en_core_web_sm
```

### 4. Configure project secrets

Create a root-level `.env` file using the variables above and optionally create `frontend/.streamlit/secrets.toml` for the frontend.

### 5. Start the backend

From the project root:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The API is available at:

- http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- Redoc: http://localhost:8000/redoc

### 6. Start the UI

In a second terminal:

```bash
streamlit run frontend/streamlit_app.py
```

The app is served at:

- http://localhost:8501

## App workflow

1. User signs in with Supabase auth from the Streamlit sidebar
2. User uploads a resume file on the ATS Scorer page
3. User optionally pastes or uploads a `.txt` job description
4. The frontend sends the resume and JD to FastAPI with the Bearer token in the header
5. The backend validates the resume, extracts text, and parses the document using Groq and NLP functions
6. The scoring pipeline computes the ATS rating and detailed issue list
7. The result is saved to Supabase for that user if the backend is configured with the Supabase service key
8. The user can view performance history, export the report to PDF, and delete saved records

## Notable implementation details

- `backend/main.py` loads spaCy during app startup and sets up CORS for allowed origins
- `frontend/streamlit_app.py` handles OAuth return flows and page navigation between landing, scorer, history, and resources screens
- `backend/services/report_generator.py` converts the structured analysis result into HTML report fragments
- `backend/services/pdf_export.py` merges those HTML documents into a single PDF
- `backend/services/feedback_engine.py` includes diagnostics for ATS-relevant resume weaknesses and recommendations
- `backend/utils/file_utils.py` provides safe fallback defaults when grammar, location, or skill-validation data is unavailable

## Database notes

The project assumes a Supabase project with a table named `analyses` used to store analysis records. There are no SQL migration files in the repo; the inserts are made through the Supabase REST API.

This app does not create local SQLite or Postgres tables as part of the runtime; persistence is delegated to Supabase.

## Jupyter notebooks

The `jupyter notebooks/` folder contains research artifacts for exploratory data preparation and embeddings work:

- `01_EDA_and_DATA_prep.ipynb`
- `02_BERT_EMBEDDINGS.ipynb`
- `03_BERT_FINETUNEipynb.ipynb`

These notebooks are not required to run the application and serve as experimentation artifacts rather than a production pipeline.

## Security and privacy notes

- Supabase auth is used for user identity and per-user persistence
- JWT verification is performed server-side before analysis and history access
- The backend checks for privacy risks such as street addresses and ZIP codes in resume text and warns users to remove them
- Environment files and secrets are intentionally excluded from version control via `.gitignore`

## Production caveats

- The app is configured for local development and local debugging by default
- `ALLOWED_ORIGINS` in `backend/core/config.py` is currently a single hardcoded Streamlit domain value and may need adjustment for other deployments
- `python-magic` depends on the underlying system library being installed correctly
- `WeasyPrint` requires OS-level libraries such as Cairo and Pango on Linux
- A valid Groq API key is required for the resume/JD parsing features to work end-to-end

## License

This project does not declare a repository license file in the workspace. Please check with the repository owner before production reuse or redistribution.
