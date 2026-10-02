from __future__ import annotations

import json
import os
import re
from pathlib import Path
from google.adk.tools.tool_context import ToolContext


def project_dir_from_context(tool_context: ToolContext) -> Path:
    slug = str(tool_context.state.get("project_slug", "website"))
    root = Path(os.getenv("OUTPUT_ROOT", "generated_sites")).resolve()
    target = (root / slug).resolve()
    if root not in target.parents:
        raise ValueError("Invalid project path")
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_project_file(relative_path: str, content: str, tool_context: ToolContext) -> dict:
    """Write a generated artifact inside the current project directory only."""
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Path must stay inside the generated project")
    target = project_dir_from_context(tool_context) / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    written = list(tool_context.state.get("written_files", []))
    if relative_path not in written:
        written.append(relative_path)
    tool_context.state["written_files"] = written
    return {"written": relative_path, "bytes": len(content.encode("utf-8"))}


def save_spec(spec_json: str, tool_context: ToolContext) -> dict:
    """Validate and persist the manager's shared project specification."""
    if isinstance(spec_json, dict):
        spec = spec_json
    else:
        raw = str(spec_json).strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
        spec = json.loads(raw)
    if not isinstance(spec, dict):
        raise ValueError("Specification must be a JSON object")

    # Models occasionally return `name` or `title` instead of the requested
    # `project` key. Normalize those common variants instead of failing the run.
    project_name = (spec.get("project") or spec.get("project_name") or
                    spec.get("name") or spec.get("title") or "Generated Website")
    spec["project"] = str(project_name).strip() or "Generated Website"
    spec.setdefault("purpose", "A website generated from the user's request")
    for section, default in (("frontend", {"pages": [], "features": []}),
                             ("backend", {"apis": []}), ("database", {"tables": []})):
        if not isinstance(spec.get(section), dict):
            spec[section] = default
    apis = spec["backend"].get("apis", [])
    normalized_apis = []
    if isinstance(apis, list):
        for api in apis:
            if isinstance(api, str):
                match = re.match(r"\s*(GET|POST|PUT|PATCH|DELETE)\s+(\S+)", api, re.IGNORECASE)
                api = ({"method": match.group(1).upper(), "path": match.group(2)}
                       if match else {"method": "GET", "path": api.strip()})
            if isinstance(api, dict) and api.get("path"):
                normalized_apis.append(api)
    spec["backend"]["apis"] = normalized_apis
    tables = spec["database"].get("tables", [])
    if isinstance(tables, list):
        spec["database"]["tables"] = [
            table if isinstance(table, dict) else {"name": str(table), "columns": []}
            for table in tables if isinstance(table, (dict, str))
        ]
    else:
        spec["database"]["tables"] = []

    slug = re.sub(r"[^a-z0-9]+", "-", spec["project"].lower()).strip("-")[:48] or "website"
    tool_context.state["project_spec"] = json.dumps(spec, indent=2)
    tool_context.state["project_slug"] = slug
    tool_context.state["test_report"] = json.dumps({"status": "NOT_RUN"})
    tool_context.state["written_files"] = []
    project_dir_from_context(tool_context).joinpath("project_spec.json").write_text(
        json.dumps(spec, indent=2), encoding="utf-8"
    )
    return {"project": spec["project"], "slug": slug, "saved": True}


def inspect_generated_files(tool_context: ToolContext) -> dict:
    """Report which expected outputs exist and their sizes."""
    root = project_dir_from_context(tool_context)
    expected = ["frontend/index.html", "frontend/style.css", "frontend/script.js",
                "backend/main.py", "database/schema.sql", "database/database.py"]
    files = {name: (root / name).exists() for name in expected}
    return {"project_dir": str(root), "files": files,
            "missing": [name for name, exists in files.items() if not exists]}
