from google.adk.agents import Agent
from ..shared import write_project_file
from ...config import MODEL

database_agent = Agent(
    name="database_agent", model=MODEL, output_key="database_result",
    instruction="""You are the Database Agent. Design a normalized SQLite schema from {project_spec}. Include tables, primary/foreign keys, constraints, and indexes as appropriate. Save database/schema.sql and database/database.py using write_project_file. The Python module must expose a simple connection/session interface compatible with FastAPI and initialize the schema safely. Work independently from backend implementation; follow only the shared specification. On the initial pass test_report status is NOT_RUN: implement the database fully. On a repair pass, if test_report failed_component is database, address its suggested_fix; otherwise leave your files unchanged.""",
    tools=[write_project_file],
)
