import json
import ast
import re
import sqlite3
from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext
from ..shared import inspect_generated_files, project_dir_from_context
from ...config import MODEL


def run_project_checks(tool_context: ToolContext) -> dict:
    """Run deterministic syntax, file, API contract, and SQLite checks."""
    root = project_dir_from_context(tool_context)
    spec = json.loads(tool_context.state.get("project_spec", "{}"))
    checks: list[dict] = []

    def check(name: str, passed: bool, component: str, detail: str = ""):
        checks.append({"name": name, "passed": bool(passed), "component": component, "detail": detail})

    required = ["frontend/index.html", "frontend/style.css", "frontend/script.js",
                "backend/main.py", "backend/requirements.txt", "database/schema.sql", "database/database.py"]
    for name in required:
        check(f"artifact:{name}", (root / name).is_file(),
              "frontend" if name.startswith("frontend/") else "backend" if name.startswith("backend/") else "database")

    for name in ["backend/main.py", "database/database.py"]:
        path = root / name
        ok, detail = False, "file missing"
        if path.is_file():
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=name)
                ok, detail = True, "Python syntax valid"
            except SyntaxError as exc:
                detail = f"line {exc.lineno}: {exc.msg}"
        check(f"python-syntax:{name}", ok, "backend" if name.startswith("backend/") else "database", detail)

    schema = root / "database/schema.sql"
    if schema.is_file():
        try:
            connection = sqlite3.connect(":memory:")
            connection.executescript(schema.read_text(encoding="utf-8"))
            table_names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            connection.close()
            expected_tables = [table.get("name", "") if isinstance(table, dict) else str(table)
                               for table in spec.get("database", {}).get("tables", [])]
            expected_tables = [name for name in expected_tables if name]
            missing_tables = [table for table in expected_tables if table not in table_names]
            check("sqlite-schema-executes", not missing_tables, "database",
                  "missing tables: " + ", ".join(missing_tables) if missing_tables else "schema executes in memory")
        except sqlite3.Error as exc:
            check("sqlite-schema-executes", False, "database", str(exc))
    else:
        check("sqlite-schema-executes", False, "database", "schema.sql missing")

    backend = (root / "backend/main.py").read_text(encoding="utf-8") if (root / "backend/main.py").is_file() else ""
    frontend = (root / "frontend/script.js").read_text(encoding="utf-8") if (root / "frontend/script.js").is_file() else ""
    html = (root / "frontend/index.html").read_text(encoding="utf-8") if (root / "frontend/index.html").is_file() else ""
    check("frontend-assets-linked", "style.css" in html and "script.js" in html, "frontend",
          "HTML references stylesheet and script" if "style.css" in html and "script.js" in html
          else "index.html must link style.css and script.js")
    for api in spec.get("backend", {}).get("apis", []):
        method = str(api.get("method", "GET")).upper()
        path = str(api.get("path", ""))
        route_pattern = rf"@(?:app|router)\.{re.escape(method.lower())}\s*\(\s*['\"]{re.escape(path)}['\"]"
        route_present = bool(path and re.search(route_pattern, backend))
        frontend_path = path in frontend
        component = "backend" if not route_present else "frontend"
        check(f"api-contract:{method} {path}", bool(route_present and frontend_path), component,
              "route and frontend reference found" if route_present and frontend_path else
              "backend route missing" if not route_present else "frontend API reference missing")

    failed = [item for item in checks if not item["passed"]]
    report = {
        "status": "FAIL" if failed else "PASS",
        "tests": len(checks), "passed": len(checks) - len(failed), "failed": len(failed),
        "errors": [f"{item['name']}: {item['detail']}" for item in failed],
    }
    if failed:
        report["failed_component"] = failed[0]["component"]
        report["error"] = report["errors"][0]
        report["suggested_fix"] = f"Repair {failed[0]['component']} artifact: {failed[0]['name']}"
    tool_context.state["test_report"] = json.dumps(report)
    (root / "test_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if report["status"] == "PASS":
        # ADK LoopAgent ends its repair loop when a child escalates.
        tool_context.actions.escalate = True
    return report


testing_agent = Agent(
    name="testing_agent", model=MODEL, output_key="testing_result",
    instruction="""You are the Testing Agent. Run run_project_checks and report its returned structured report accurately. The checks cover required artifacts, Python parsing, executing the SQLite schema in memory, and API route references. Do not claim broader live-browser or HTTP workflow tests were run. A PASS ends the ADK repair loop. A FAIL proceeds to the next iteration, where the reported failed component and suggested fix are addressed.""",
    tools=[inspect_generated_files, run_project_checks],
)
