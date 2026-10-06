from google.adk.agents import Agent, LoopAgent, SequentialAgent
from ...config import MODEL, MAX_REPAIR_ITERATIONS
from ..shared import save_spec
from ..frontend_agent.agent import frontend_agent
from ..integration_agent.agent import integration_agent
from ..testing_agent.agent import testing_agent
from ..runner_agent.agent import runner_agent


manager_analysis_agent = Agent(
    name="manager_analysis",
    model=MODEL,
    output_key="manager_analysis",
    instruction="""You are the sole scope authority. Convert the user's request into a precise, closed-world project specification. The generated applications are static client-side HTML, CSS, vanilla JavaScript, optional seed JSON, and browser localStorage only. Never plan a backend, API, server-side app, SQL database, or framework. Include only explicitly requested functionality and strictly necessary internal technical dependencies. Exclude inferred, customary, convenience, future, or best-practice features. For material ambiguity, record clarification_required and do not authorize dependent implementation.

Return one valid JSON object with a nonempty project name and purpose, plus top-level sections PROJECT_SCOPE, APPROVED_FEATURES, OUT_OF_SCOPE_FUNCTIONALITY, FRONTEND_SPECIFICATION, DATA_SPECIFICATION, DATA_FLOW_SPECIFICATION, CLIENT_LOGIC_SPECIFICATION, FILE_SPECIFICATION, TRACEABILITY_MATRIX, SCOPE_AUDIT, FRONTEND_AGENT_PROMPT, and a compatibility frontend object with pages/features. Each approved feature uses FEATURE_001-style ID and fields id, name, purpose, user_actions, expected_behavior, required, frontend_scope, client_logic_scope, data_scope, validation, error_handling, dependencies, data_flow, clarification_status. Each DOM element/component, JS function, event handler, data field/operation, validation, storage operation, page, and file must cite feature_ids. No untraceable requirement is permitted.

FRONTEND_SPECIFICATION defines each page/component/function: name, feature_ids, purpose, trigger, inputs, outputs, state, UI behavior, validation, loading/error/success states, navigation, and data consumed. CLIENT_LOGIC_SPECIFICATION defines only required handlers and functions with feature_ids, triggers, inputs/outputs and effects. DATA_SPECIFICATION must use this exact shape: {"files":[{"path":"data/data.json","purpose":"Initial seed data"}],"root_structure":{"notes":[]},"collections":[{"name":"notes","fields":[{"name":"title","type":"string","required":true,"reason":"..."}]}],"initial_data":{"notes":[]},"operations":[{"operation":"create","feature_ids":["FEATURE_001"]}],"persistence":{"strategy":"JSON_SEED_LOCAL_STORAGE","storage_key":"notes"}}. Include only needed fields and operations. Persistence is exactly READ_ONLY_JSON or JSON_SEED_LOCAL_STORAGE. For mutable data, localStorage is checked first; if absent load data.json as seed and store it locally; subsequent changes go only to localStorage. Read-only data may be read from data.json. Never claim localStorage writes data.json. FILE_SPECIFICATION must have a files array with each entry exactly {"path":"index.html","purpose":"..."}; list only required project files (typically root index.html, style.css, script.js, optional data/data.json, and README.md only if necessary). Every path is project-relative and must match DATA_SPECIFICATION.files paths. Do not specify backend/, database/, deployment/, Dockerfile, requirements.txt, package.json, or server-side code.

DATA_FLOW_SPECIFICATION maps feature ID -> user action -> UI/event handler -> client logic -> optional JSON seed -> localStorage/read-only data -> rendered UI. Check field names, data operations, keys and files agree across sections. OUT_OF_SCOPE_FUNCTIONALITY must list plausible inferred additions, including backend/API, frameworks, authentication, extra CRUD, extra pages, and unrequested storage/data fields. SCOPE_AUDIT explicitly checks traceability, inferred-feature exclusion, no extra CRUD/pages/fields/files, persistence correctness, no API/backend/SQL/framework dependency, and connected/used data operations. Resolve every violation before saving.

FRONTEND_AGENT_PROMPT is dedicated and actionable, contains only the approved frontend/client/data/files and relevant contracts, and cites feature IDs. Append: 'SCOPE ENFORCEMENT: The Orchestrator specification is authoritative. Implement exactly and only the listed functionality. Do not invent, infer, add convenience/standard/future features, unrequested CRUD, extra fields, pages, navigation, UI, validation, or data operations. Every element, function, event handler, operation, field, page, and file must trace to an approved feature ID. Use only HTML, CSS, vanilla JavaScript, JSON seed data when specified, and localStorage when specified. Never implement a backend, API call, SQL/database, framework, or server-side code. Never pretend JavaScript can write data.json. If a dependency appears necessary but is unspecified, do not implement it: report UNAUTHORIZED_DEPENDENCY with what is needed, why, which approved feature requires it, and affected files. Implement the minimum complete system.'

For legacy compatibility only, backend and database may be included as empty objects; do not emit BACKEND_SPECIFICATION, API_CONTRACT, or DATABASE_SPECIFICATION. Call save_spec exactly once with the full JSON encoded as spec_json. Do not guess ambiguous behavior.""",
    tools=[save_spec],
)

integration_testing_loop = LoopAgent(
    name="development_integration_test_loop",
    max_iterations=MAX_REPAIR_ITERATIONS,
    sub_agents=[frontend_agent, integration_agent, testing_agent],
)

manager_agent = SequentialAgent(
    name="manager_agent",
    description="Define closed client-side scope, generate and validate the frontend, then provide the static runner command only after PASS.",
    sub_agents=[manager_analysis_agent, integration_testing_loop, runner_agent],
)

root_agent = manager_agent
