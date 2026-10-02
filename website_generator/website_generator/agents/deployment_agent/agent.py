import json
from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext
from ..shared import project_dir_from_context, write_project_file
from ...config import MODEL


def prepare_deployment(tool_context: ToolContext) -> dict:
    """Create Docker deployment files only after a persisted passing report."""
    raw = tool_context.state.get("test_report")
    if not raw:
        raise ValueError("Deployment blocked: no saved test report")
    report = json.loads(raw)
    if report.get("status") != "PASS" or int(report.get("failed", 0)) != 0:
        raise ValueError("Deployment blocked: tests have not passed")
    root = project_dir_from_context(tool_context)
    dockerfile = """FROM python:3.12-slim\nWORKDIR /app\nCOPY backend/requirements.txt ./requirements.txt\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\nENV PORT=8080\nEXPOSE 8080\nCMD [\"sh\", \"-c\", \"uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}\"]\n"""
    (root / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    (root / "deployment").mkdir(exist_ok=True)
    (root / "deployment" / "cloudrun.md").write_text(
        "# Cloud Run deployment\n\nBuild and deploy this container after reviewing generated code. Set secrets with Secret Manager or environment configuration; never commit credentials. Example:\n\n```sh\ngcloud run deploy SITE_NAME --source . --region REGION --allow-unauthenticated\n```\n\nThis generator prepares files only. Run the command in an authenticated Google Cloud project to deploy and obtain a live URL.\n",
        encoding="utf-8",
    )
    return {"prepared": True, "project_dir": str(root), "live_url": None,
            "note": "Deployment bundle prepared; Cloud Run was not invoked."}


deployment_agent = Agent(
    name="deployment_agent", model=MODEL, output_key="deployment_result",
    instruction="""You are the Deployment Agent. First call prepare_deployment; it enforces the Testing Agent PASS gate and writes a Dockerfile plus Cloud Run instructions. Summarize the output path. Do not deploy to Google Cloud or invent a live URL. Deployment requires explicit cloud configuration outside this workflow.""",
    tools=[prepare_deployment],
)
