# AI Website Generator

A small multi-agent website generator built with Google ADK. The manager analyzes a request into a shared project specification, then ADK's `ParallelAgent` starts the frontend, backend, and database agents concurrently. Integration and testing run after the parallel fan-out completes; deployment preparation is gated on a passing test report.

## Setup

Use Python 3.10+ and install dependencies:

```powershell
cd website_generator
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `GOOGLE_API_KEY` in `.env`. Never commit credentials. Run the ADK developer UI from the parent directory:

```powershell
adk web
```

Select `website_generator` and describe the site you want. Generated projects are written under `generated_sites/<project-slug>/`.

## Workflow

`Manager Agent` first writes `project_spec.json`. `Parallel Development` is an ADK `ParallelAgent` with exactly three children (Frontend, Backend, Database); each reads the same spec and writes to its own directory. ADK waits for all parallel children before `Integration Agent` runs. `Testing Agent` records a structured PASS/FAIL report. `Deployment Agent` only prepares a Docker/Cloud Run deployment bundle when the report is PASS; it does not deploy or claim a live URL without explicit cloud credentials and an actual deployment.

Each worker's output is stored under a unique session state key. The integration and testing stages check generated artifacts and cross-component contracts. The project includes deployment preparation, but actual Cloud Run deployment requires a configured Google Cloud project and authenticated `gcloud` environment.

## Layout

- `agents/`: seven agent definitions and the ADK workflow.
- `frontend/`, `backend/`, `database/`: generated output destinations within each generated site.
- `tests/`: local workflow and generated-project checks.
- `deployment/`: container and Cloud Run preparation guidance.

The generator intentionally starts with a small, reviewable scope. Generated code is untrusted output; inspect it before running or deploying.
