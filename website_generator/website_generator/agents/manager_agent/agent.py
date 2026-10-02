from google.adk.agents import Agent, LoopAgent, ParallelAgent, SequentialAgent
from ...config import MODEL
from ..shared import save_spec
from ..frontend_agent.agent import frontend_agent
from ..backend_agent.agent import backend_agent
from ..database_agent.agent import database_agent
from ..integration_agent.agent import integration_agent
from ..testing_agent.agent import testing_agent
from ..deployment_agent.agent import deployment_agent

manager_analysis_agent = Agent(
    name="manager_analysis", model=MODEL, output_key="manager_analysis",
    instruction="""Analyze the user's natural-language website request. Create one valid JSON object with these exact top-level keys: project (a nonempty website/project name), purpose, frontend (object with pages and features arrays), backend (object with apis array of objects, each with method, path, request, response), and database (object with tables array of objects, each with name and columns). Include relationships and integration assumptions where useful. Ensure frontend, backend, and database tasks can proceed independently. Call save_spec exactly once, passing the full JSON object encoded as a JSON string in spec_json. Do not write application code.""",
    tools=[save_spec],
)

parallel_development = ParallelAgent(
    name="parallel_development",
    sub_agents=[frontend_agent, backend_agent, database_agent],
)

integration_testing_loop = LoopAgent(
    name="development_integration_test_loop",
    max_iterations=3,
    # Each pass starts with the three workers in parallel and waits for the
    # ParallelAgent join before integration/testing. A failed report is visible
    # to the next parallel repair pass; PASS escalates from Testing and exits.
    sub_agents=[parallel_development, integration_agent, testing_agent],
)

manager_agent = SequentialAgent(
    name="manager_agent",
    description="Analyze a website request, fan out independent development work in parallel, then integrate, test, and prepare deployment only on PASS.",
    sub_agents=[manager_analysis_agent, integration_testing_loop, deployment_agent],
)

root_agent = manager_agent
