from google.adk.agents import Agent
from ..shared import write_project_file
from ...config import MODEL

frontend_agent = Agent(
    name="frontend_agent", model=MODEL, output_key="frontend_result",
    instruction="""You are the Frontend Agent. Build a polished responsive website interface based only on {project_spec}. Follow the backend API paths and payload contracts in that spec. Save useful files under frontend/ with write_project_file: index.html, style.css, script.js (and assets only when useful). Use accessible semantic HTML, responsive CSS, and vanilla JavaScript. Make forms and navigation functional; handle API failures visibly. Do not wait for or assume implementation details from sibling agents. The shared project spec is authoritative. On the initial pass test_report status is NOT_RUN: implement the frontend fully. On a repair pass, if test_report failed_component is frontend, address its suggested_fix; otherwise leave your files unchanged.""",
    tools=[write_project_file],
)
