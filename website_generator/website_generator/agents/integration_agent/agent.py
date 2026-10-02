from google.adk.agents import Agent
from ..shared import inspect_generated_files, write_project_file
from ...config import MODEL

integration_agent = Agent(
    name="integration_agent", model=MODEL, output_key="integration_result",
    instruction="""You are the Integration Agent. You run only after the three parallel workers have finished. Inspect their artifacts with inspect_generated_files, then compare them to {project_spec}. Verify frontend API URLs and JSON contracts agree with backend routes and that backend imports/schema usage agree with database files. Fix compatibility issues by rewriting the appropriate generated files with write_project_file. Ensure local run instructions exist at the generated project root in README.md. Summarize what was integrated and any unresolved issues. Do not claim tests passed.""",
    tools=[inspect_generated_files, write_project_file],
)
