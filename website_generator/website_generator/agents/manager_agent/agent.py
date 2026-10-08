import asyncio
import json
import re
import subprocess
import sys
import threading
from pathlib import Path

from google.adk.agents import Agent, LoopAgent, SequentialAgent
from google.adk.events import Event
from google.genai import types
from ...config import MODEL, MAX_REPAIR_ITERATIONS
from ..shared import save_spec
from ..frontend_agent.agent import frontend_agent
from ..integration_agent.agent import integration_agent
from ..testing_agent.agent import testing_agent
from ..runner_agent.agent import runner_agent
from ...runner import resolve_project


_active_runner_processes = []


def _start_existing_runner(project_slug):
    project = resolve_project(project_slug)
    project_root = Path(__file__).resolve().parents[3]
    process = subprocess.Popen(
        [sys.executable, "-m", "website_generator.runner", project_slug],
        cwd=str(project_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    startup = {"url": None, "error": None}
    ready = threading.Event()

    def capture_runner_output():
        try:
            for line in process.stdout:
                match = re.search(r"https?://[^\s]+", line)
                if match and startup["url"] is None:
                    startup["url"] = match.group(0).rstrip(".,)")
                    ready.set()
        except Exception as exc:
            startup["error"] = str(exc)
        finally:
            ready.set()

    reader = threading.Thread(target=capture_runner_output, daemon=True)
    reader.start()
    if not ready.wait(timeout=20):
        process.terminate()
        raise RuntimeError("The existing runner did not print a URL during startup")
    if not startup["url"]:
        detail = startup["error"] or "The runner exited without printing a URL"
        raise RuntimeError(detail)
    if process.poll() is not None:
        raise RuntimeError("The runner printed a URL but exited before serving the application")

    _active_runner_processes.append((process, reader))
    return startup["url"]


def _final_response(manager_name, invocation_id, message):
    return Event(
        author=manager_name,
        invocation_id=invocation_id,
        content=types.Content(
            role="model",
            parts=[types.Part(text=message)],
        ),
        turn_complete=True,
    )


intent_classifier_agent = Agent(
    name="manager_intent_classifier",
    model=MODEL,
    output_key="manager_intent",
    instruction="""Classify the user's latest message before any application-generation work begins. Return exactly one label and nothing else: CASUAL_CONVERSATION, PRODUCTION_REQUEST, or CLARIFICATION_REQUIRED.

Use PRODUCTION_REQUEST only when the user explicitly asks to create, build, make, or otherwise implement a software application or website. A greeting does not cancel an explicit build request, so 'Hi, create a todo app' is PRODUCTION_REQUEST. Greetings alone, thanks, questions, explanations, and discussion about APIs, LLMs, agents, ADK, programming, or this project are CASUAL_CONVERSATION. Never infer a build request from context or from the assumption that every message asks for an app. If the user expresses a possible creation intent but does not specify a clear application request (for example, 'make something cool'), choose CLARIFICATION_REQUIRED. When uncertain whether an application was explicitly requested, choose CLARIFICATION_REQUIRED.""",
)

manager_conversation_agent = Agent(
    name="manager_conversation",
    model=MODEL,
    instruction="""Respond normally to the user's conversational message. Answer questions helpfully, explain the project or general concepts when asked, and acknowledge greetings or thanks. Do not create or describe a project specification, invoke application-generation work, or claim that files were created.""",
)

manager_clarification_agent = Agent(
    name="manager_clarification",
    model=MODEL,
    instruction="""The user's possible application request is ambiguous. Ask a concise clarifying question about what application they want. Do not create a project specification or begin application-generation work.""",
)


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

class IntentGatedManagerAgent(SequentialAgent):
    async def _run_async_impl(self, ctx):
        async for event in intent_classifier_agent.run_async(ctx):
            yield event

        intent = ctx.session.state.get("manager_intent", "")
        if intent == "CASUAL_CONVERSATION":
            response_agent = manager_conversation_agent
        elif intent == "PRODUCTION_REQUEST":
            response_agent = None
        else:
            response_agent = manager_clarification_agent

        if response_agent is not None:
            async for event in response_agent.run_async(ctx):
                yield event
            return

        # Keep the existing runner agent registered for compatibility, but do
        # not invoke its LLM handoff. Start the existing static runner below.
        for production_stage in self.sub_agents[:2]:
            async for event in production_stage.run_async(ctx):
                yield event

        report = ctx.session.state.get("test_report")
        try:
            report = json.loads(report) if isinstance(report, str) else report
        except (TypeError, ValueError):
            report = None

        try:
            tests_passed = (
                isinstance(report, dict)
                and report.get("status") == "PASS"
                and int(report.get("failed", 0)) == 0
            )
        except (TypeError, ValueError):
            tests_passed = False

        if not tests_passed:
            yield _final_response(
                self.name,
                ctx.invocation_id,
                "The generated application was not started because its test report is not PASS.",
            )
            return

        project_slug = str(ctx.session.state.get("project_slug", "")).strip()
        if not project_slug:
            yield _final_response(
                self.name,
                ctx.invocation_id,
                "The application passed testing, but the runner could not start it because the project slug is missing.",
            )
            return

        try:
            url = await asyncio.to_thread(_start_existing_runner, project_slug)
        except Exception as exc:
            yield _final_response(
                self.name,
                ctx.invocation_id,
                f"The application passed testing, but the existing runner did not start successfully: {exc}",
            )
            return

        yield _final_response(
            self.name,
            ctx.invocation_id,
            f"Your generated application is running at {url}",
        )


manager_agent = IntentGatedManagerAgent(
    name="manager_agent",
    description="Classify intent, generate and validate explicit application requests, then start the tested static application and return its actual local URL.",
    sub_agents=[manager_analysis_agent, integration_testing_loop, runner_agent],
)

root_agent = manager_agent
