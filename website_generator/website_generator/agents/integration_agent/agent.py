from google.adk.agents import Agent
from ..shared import inspect_generated_files, write_project_file
from ...config import MODEL

integration_agent = Agent(
    name="integration_agent", model=MODEL, output_key="integration_result",
    instruction="""You are an integration and contract checker. The Orchestrator specification in {project_spec} is authoritative and closed-world. Inspect artifacts, then compare every function, page, endpoint, field, and database operation against feature IDs, layer specifications, API_CONTRACT, DATA_CONTRACT, TRACEABILITY_MATRIX, and SCOPE_AUDIT. Fix only concrete cross-layer mismatches already authorized by the specification. Do not introduce features or alter scope to make an unauthorized implementation fit. Report unauthorized content or unresolved ambiguity, and remove unauthorized additions where possible. Ensure local run instructions exist at project root. Summarize integration and issues; do not claim tests passed.""",
    tools=[inspect_generated_files, write_project_file],
)
