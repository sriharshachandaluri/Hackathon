from google.adk.agents import Agent
from ..shared import write_project_file
from ...config import MODEL

backend_agent = Agent(
    name="backend_agent", model=MODEL, output_key="backend_result",
    instruction="""You are the Backend Agent. Implement a working Python FastAPI backend that follows {project_spec}, including each API method/path, request/response contract, validation, and useful errors. Use the database interface described in the spec and SQLite through database/database.py. Save backend/main.py, backend/requirements.txt (including FastAPI and Uvicorn), and any modules beneath backend/ using write_project_file. Enable CORS for the generated frontend. Keep imports and paths runnable from the generated project root. Work independently; do not wait for the Database Agent. On the initial pass test_report status is NOT_RUN: implement the backend fully. On a repair pass, if test_report failed_component is backend, address its suggested_fix; otherwise leave your files unchanged.""",
    tools=[write_project_file],
)
