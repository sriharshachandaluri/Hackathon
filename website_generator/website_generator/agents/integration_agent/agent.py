from __future__ import annotations

import json
import re
from pathlib import Path

from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext

from ..shared import inspect_generated_files, project_dir_from_context
from ...config import MODEL


def run_client_integration_checks(tool_context: ToolContext) -> dict:
    """Check generated client files, DOM wiring, seed data, traceability, and forbidden dependencies."""
    root = project_dir_from_context(tool_context)
    spec = json.loads(tool_context.state.get("project_spec", "{}"))
    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    declared_files = spec.get("FILE_SPECIFICATION", {}).get("files", [])
    file_paths = [str(item.get("path", "")) if isinstance(item, dict) else str(item)
                  for item in declared_files]
    for relative in file_paths:
        check(f"required-file:{relative}", bool(relative and (root / relative).is_file()),
              "present" if relative and (root / relative).is_file() else "required file missing")

    html_path, css_path, js_path = root / "index.html", root / "style.css", root / "script.js"
    html = html_path.read_text(encoding="utf-8") if html_path.is_file() else ""
    css = css_path.read_text(encoding="utf-8") if css_path.is_file() else ""
    js = js_path.read_text(encoding="utf-8") if js_path.is_file() else ""
    check("html-entrypoint", html_path.is_file(), "root index.html must exist")
    check("html-script-link", bool(re.search(r'<script\b[^>]*\bsrc=[\"\'](?:\./)?script\.js[\"\']', html, re.I)),
          "index.html must load root script.js")
    check("html-css-link", bool(re.search(r'<link\b[^>]*\bhref=[\"\'](?:\./)?style\.css[\"\']', html, re.I)),
          "index.html must link root style.css")
    script_links = re.findall(r'<script\b[^>]*\bsrc=[\"\']([^\"\']+)', html, re.I)
    style_links = re.findall(r'<link\b[^>]*\bhref=[\"\']([^\"\']+)', html, re.I)
    allowed_assets = {"script.js", "./script.js", "style.css", "./style.css"}
    external_assets = [asset for asset in script_links + style_links if asset not in allowed_assets]
    check("no-external-assets", not external_assets,
          "unapproved script/style dependencies: " + ", ".join(external_assets))

    html_ids = set(re.findall(r'\bid=[\"\']([^\"\']+)', html))
    js_ids = set(re.findall(r'(?:getElementById\s*\(|querySelector(?:All)?\s*\()\s*[\"\']#?([A-Za-z][\w:.-]*)', js))
    missing_ids = sorted(js_ids - html_ids)
    check("dom-references", not missing_ids, "missing HTML id(s): " + ", ".join(missing_ids))

    spec_data = spec.get("DATA_SPECIFICATION", {})
    data_files = [item.get("path") for item in spec_data.get("files", []) if isinstance(item, dict)]
    collections = spec_data.get("collections", [])
    declared_fields = {str(field.get("name")) for collection in collections if isinstance(collection, dict)
                       for field in collection.get("fields", []) if isinstance(field, dict)}
    data_field_refs = set(re.findall(r"\b(?:note|notes|item|record|entry|task|tasks)\.(\w+)", js))
    data_field_refs -= {"push", "pop", "map", "forEach", "filter", "find", "length", "some",
                        "every", "slice", "reduce", "includes", "sort", "join", "splice", "concat"}
    unknown_data_fields = sorted(data_field_refs - declared_fields)
    check("data-field-usage", not unknown_data_fields,
          "JavaScript references fields absent from DATA_SPECIFICATION: " + ", ".join(unknown_data_fields))
    for data_path in data_files:
        target = root / data_path
        check(f"seed-file:{data_path}", target.is_file(), "specified seed file is missing")
        if target.is_file():
            try:
                data = json.loads(target.read_text(encoding="utf-8"))
                check(f"seed-json:{data_path}", isinstance(data, dict), "JSON root must be an object")
                expected_initial = spec_data.get("initial_data")
                if expected_initial is not None:
                    check(f"seed-matches-spec:{data_path}", data == expected_initial,
                          "data.json must match DATA_SPECIFICATION.initial_data exactly")
                for collection in collections:
                    name = collection.get("name")
                    if name in data:
                        entries = data[name]
                        valid = isinstance(entries, list)
                        if valid:
                            required_fields = {field["name"] for field in collection.get("fields", [])
                                               if isinstance(field, dict) and field.get("required")}
                            valid = all(isinstance(row, dict) and required_fields.issubset(row) for row in entries)
                        check(f"seed-collection:{name}", valid,
                              f"expected list with required fields {sorted(required_fields)}")
                    else:
                        check(f"seed-collection:{name}", False, "collection missing from JSON root")
            except (json.JSONDecodeError, OSError) as exc:
                check(f"seed-json:{data_path}", False, str(exc))

    strategy = spec_data.get("persistence", {}).get("strategy")
    storage_key = spec_data.get("persistence", {}).get("storage_key")
    if strategy == "JSON_SEED_LOCAL_STORAGE":
        check("localstorage-required", "localStorage" in js, "mutable data must use browser localStorage")
        if storage_key:
            check("localstorage-key", str(storage_key) in js, f"specified key {storage_key!r} not referenced")
        check("seed-load", bool(data_files) and any(Path(str(p)).name == "data.json" for p in data_files)
              and ("data.json" in js or "fetch(" in js), "mutable data requires static JSON seed loading")

    feature_ids = [feature.get("id") for feature in spec.get("APPROVED_FEATURES", [])]
    source = html + "\n" + css + "\n" + js
    for feature_id in feature_ids:
        check(f"traceability:{feature_id}", str(feature_id) in source,
              "feature ID annotation missing from generated frontend source")

    forbidden_paths = []
    for item in root.rglob("*"):
        if not item.is_file() or item.name in {"project_spec.json", "test_report.json", ".gitignore"}:
            continue
        relative = item.relative_to(root)
        blocked_dirs = {"backend", "database", "deployment", "node_modules"}
        blocked_names = {"dockerfile", "requirements.txt", "package.json", "server.py", "main.py", "routes.py", "schema.sql"}
        if (any(part.lower() in blocked_dirs for part in relative.parts)
                or item.name.lower() in blocked_names or item.suffix.lower() in {".py", ".sql"}):
            forbidden_paths.append(relative.as_posix())
        if relative.as_posix() not in file_paths:
            forbidden_paths.append(relative.as_posix())
    check("file-scope", not forbidden_paths, "undeclared files: " + ", ".join(sorted(forbidden_paths)))

    forbidden_patterns = {
        "backend-url": r"(?:https?://[^\s\"'`]+(?:/api/|:800\d)|https?://(?:localhost|127\.0\.0\.1))",
        "api-route": r"(?:fetch|axios\.(?:get|post|put|delete))\s*\(\s*[\"']/(?:api/)",
        "sql": r"\b(?:SELECT\s+.+\s+FROM|INSERT\s+INTO|CREATE\s+TABLE|UPDATE\s+\w+\s+SET|DELETE\s+FROM)\b",
        "framework": r"\b(?:React|Vue|Angular|Next\.js|Express|FastAPI|Flask|SQLite|MongoDB|PostgreSQL|MySQL)\b",
    }
    app_text = "\n".join((html, css, js))
    for name, pattern in forbidden_patterns.items():
        check(f"forbidden:{name}", not re.search(pattern, app_text, re.I),
              "forbidden backend/API/database/framework dependency detected")
    fetch_targets = re.findall(r"\bfetch\s*\(\s*['\"]([^'\"]+)['\"]", js, re.I)
    fetch_count = len(re.findall(r"\bfetch\s*\(", js, re.I))
    allowed_seed_paths = {str(path) for path in data_files} | {"./" + str(path) for path in data_files}
    bad_fetches = [target for target in fetch_targets if target not in allowed_seed_paths]
    check("fetch-only-local-seed", fetch_count == len(fetch_targets) and not bad_fetches,
          "fetch() may only load the declared local JSON seed; found: " + ", ".join(bad_fetches))
    forbidden_clients = re.findall(r"\b(?:XMLHttpRequest|axios|WebSocket|EventSource)\b", app_text, re.I)
    check("no-network-clients", not forbidden_clients,
          "unapproved network client(s): " + ", ".join(sorted(set(forbidden_clients))))

    failed = [item for item in checks if not item["passed"]]
    report = {"status": "FAIL" if failed else "PASS", "checks": checks,
              "failed": len(failed), "passed": len(checks) - len(failed)}
    tool_context.state["integration_result"] = json.dumps(report)
    return report


integration_agent = Agent(
    name="integration_agent",
    model=MODEL,
    output_key="integration_summary",
    instruction="""You are a client-side integration validator. First call run_client_integration_checks and report its PASS/FAIL and exact failures accurately. Also inspect the generated files against {project_spec}: verify HTML -> JavaScript -> client logic -> specified JSON/localStorage -> UI, feature traceability, and no unauthorized functionality. Do not repair by expanding scope; if a repair is needed, report the exact authorized defect for the next frontend-only pass. Never claim PASS when the tool returns FAIL.""",
    tools=[inspect_generated_files, run_client_integration_checks],
)
