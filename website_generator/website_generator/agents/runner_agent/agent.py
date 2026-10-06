import json

from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext

from ...config import MODEL
from ...runner import resolve_project


def prepare_static_runner(tool_context: ToolContext) -> dict:
    """Return the fixed local runner command only after the generated app passes checks."""
    raw = tool_context.state.get("test_report")
    if not raw:
        raise ValueError("Runner blocked: no saved test report")
    report = json.loads(raw)
    if report.get("status") != "PASS" or int(report.get("failed", 0)) != 0:
        raise ValueError("Runner blocked: generated application has not passed testing")
    slug = str(tool_context.state.get("project_slug", ""))
    project = resolve_project(slug)
    return {
        "ready": True,
        "project_dir": str(project),
        "command": f"python -m website_generator.runner {slug}",
        "stop": "Press Ctrl+C in the runner terminal to stop the server cleanly.",
    }


runner_agent = Agent(
    name="runner_agent",
    model=MODEL,
    output_key="runner_result",
    instruction="""You are the post-PASS static runner handoff. Call prepare_static_runner and report its exact project path, command, and stop instructions. Do not invent shell commands, install packages, use a backend server, or claim the application is live before the user runs the command. The Python static runner selects and prints an available port.""",
    tools=[prepare_static_runner],
)
