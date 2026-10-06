# AI Software Factory

This factory generates self-contained client-side web applications using HTML, CSS, vanilla JavaScript, optional JSON seed data, and browser `localStorage`. Generated applications do not use a backend, API, server-side code, database, or frontend framework.

## Setup

Use Python 3.10+ and install the factory dependency:

```powershell
cd website_generator
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `GOOGLE_API_KEY` in `.env`, then start the ADK interface from the parent directory with `adk web`. Generated projects are written under `generated_sites/<project-slug>/`.

## Workflow

The Manager first saves a closed-world project specification. Its approved feature registry, frontend/data/file specifications, traceability matrix, and scope audit are the source of truth. Only then does the Frontend Agent generate the listed files. The Integration Agent checks file/DOM/data wiring and rejects backend, API, SQL, database, framework, or unapproved files. The Testing Agent runs integration checks, JavaScript syntax validation, and an isolated DOM/localStorage runtime smoke check. A failed check enters a frontend-only repair loop, capped by `MAX_REPAIR_ITERATIONS` (default 3). After PASS, the Runner Agent returns the fixed static-server command for the tested project.

Mutable data uses `data/data.json` only as initial seed data and `localStorage` for runtime persistence. Read-only applications may load JSON directly. Browser code never writes back to `data.json`.

## Run a generated project

After the test report is PASS, the Runner Agent returns the command. Run the deterministic static server from the factory directory:

```powershell
python -m website_generator.runner <project-slug>
```

The runner locates the generated project, requires `index.html`, selects an available port dynamically, prints the actual local URL, serves only that project, and stops with Ctrl+C. It does not start or create an application backend.

## Layout

- `website_generator/agents/`: Manager, Frontend, Integration, and Testing agent definitions.
- `website_generator/runner.py`: deterministic static-file runner.
- `website_generator/agents/shared.py`: scope-aware project file and specification tools.
- `tests/`: workflow and factory validation tests.

Generated output is untrusted code. Review it before use.
