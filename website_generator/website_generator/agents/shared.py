from __future__ import annotations

import json
import os
import re
from pathlib import Path
from google.adk.tools.tool_context import ToolContext


def project_dir_from_context(tool_context: ToolContext) -> Path:
    slug = str(tool_context.state.get("project_slug", "website"))
    configured_root = Path(os.getenv("OUTPUT_ROOT", "generated_sites"))
    if not configured_root.is_absolute():
        configured_root = Path(__file__).resolve().parents[3] / configured_root
    root = configured_root.resolve()
    target = (root / slug).resolve()
    if root not in target.parents:
        raise ValueError("Invalid project path")
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_project_file(relative_path: str, content: str, tool_context: ToolContext) -> dict:
    """Write only a file authorized by FILE_SPECIFICATION inside this project."""
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Path must stay inside the generated project")
    normalized = path.as_posix()
    if _is_server_artifact(normalized):
        raise ValueError(f"Server-side or framework artifact is forbidden: {normalized}")
    if normalized == "project_spec.json":
        raise ValueError("The generated project specification is factory-managed")
    raw_spec = tool_context.state.get("project_spec")
    if raw_spec:
        spec = json.loads(raw_spec)
        allowed = {
            str(item.get("path", "")) if isinstance(item, dict) else str(item)
            for item in spec.get("FILE_SPECIFICATION", {}).get("files", [])
        }
        if normalized not in allowed:
            raise ValueError(f"File is not authorized by FILE_SPECIFICATION: {normalized}")
    target = project_dir_from_context(tool_context) / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    written = list(tool_context.state.get("written_files", []))
    if relative_path not in written:
        written.append(relative_path)
    tool_context.state["written_files"] = written
    return {"written": relative_path, "bytes": len(content.encode("utf-8"))}


def _is_server_artifact(relative_path: str) -> bool:
    path = Path(relative_path)
    blocked_dirs = {"backend", "database", "deployment", "node_modules"}
    blocked_names = {"dockerfile", "requirements.txt", "package.json", "server.py", "main.py", "routes.py", "schema.sql"}
    return (any(part.lower() in blocked_dirs for part in path.parts)
            or path.name.lower() in blocked_names
            or path.suffix.lower() in {".py", ".sql"})


def save_spec(spec_json: str, tool_context: ToolContext) -> dict:
    """Validate and persist the closed-world client-side project specification."""
    if isinstance(spec_json, dict):
        spec = spec_json
    else:
        raw = str(spec_json).strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
        spec = json.loads(raw)
    if not isinstance(spec, dict):
        raise ValueError("Specification must be a JSON object")

    for forbidden in ("BACKEND_SPECIFICATION", "API_CONTRACT", "DATABASE_SPECIFICATION"):
        if forbidden in spec and spec[forbidden] not in (None, {}, [], ""):
            raise ValueError(f"Server-side specification is forbidden: {forbidden}")

    project_name = spec.get("project") or spec.get("project_name") or spec.get("name") or spec.get("title")
    if not isinstance(project_name, str) or not project_name.strip():
        raise ValueError("The Orchestrator must provide an explicit nonempty project name")
    spec["project"] = project_name.strip()
    spec.setdefault("purpose", "A website generated from the user's request")
    if not isinstance(spec.get("APPROVED_FEATURES"), list):
        raise ValueError("APPROVED_FEATURES must be a list")
    feature_ids = [item.get("id") for item in spec["APPROVED_FEATURES"] if isinstance(item, dict)]
    if len(feature_ids) != len(spec["APPROVED_FEATURES"]) or any(not item for item in feature_ids):
        raise ValueError("Every approved feature must be an object with an id")
    if len(feature_ids) != len(set(feature_ids)):
        raise ValueError("APPROVED_FEATURES contains duplicate IDs")
    if "DATA_FLOW_SPECIFICATION" not in spec:
        # This is a lossless registry view, not inferred functionality.
        spec["DATA_FLOW_SPECIFICATION"] = {
            feature["id"]: {"feature_ids": [feature["id"]], "flow": feature.get("data_flow", "")}
            for feature in spec["APPROVED_FEATURES"]
        }
    for section in ("PROJECT_SCOPE", "OUT_OF_SCOPE_FUNCTIONALITY", "FRONTEND_SPECIFICATION",
                    "DATA_SPECIFICATION", "DATA_FLOW_SPECIFICATION", "CLIENT_LOGIC_SPECIFICATION",
                    "FILE_SPECIFICATION", "TRACEABILITY_MATRIX", "SCOPE_AUDIT", "FRONTEND_AGENT_PROMPT"):
        if section not in spec:
            raise ValueError(f"Missing required scope section: {section}")
    file_spec = spec.get("FILE_SPECIFICATION", {})
    files = file_spec.get("files")
    if not isinstance(files, list):
        raise ValueError("FILE_SPECIFICATION.files must be a list")
    normalized_files = [dict(item) if isinstance(item, dict) else {"path": item} for item in files]
    paths = [item.get("path") for item in normalized_files]
    if any(not isinstance(path, str) or not path.strip() for path in paths):
        raise ValueError("Every DATA_SPECIFICATION.files and FILE_SPECIFICATION.files entry requires a nonempty path")
    for relative_path in paths:
        path = Path(relative_path)
        if path.is_absolute() or ".." in path.parts or _is_server_artifact(relative_path):
            raise ValueError(f"Forbidden or non-project-relative application file: {relative_path}")
    if len(paths) != len(set(paths)):
        raise ValueError("FILE_SPECIFICATION contains duplicate paths")
    for required in ("index.html", "style.css", "script.js"):
        if required not in paths:
            raise ValueError(f"Client application must declare {required}")
    data_spec = spec.get("DATA_SPECIFICATION") or {}
    if not isinstance(data_spec, dict):
        raise ValueError("DATA_SPECIFICATION must be an object")
    persistence_spec = data_spec.get("persistence") or {}
    persistence = persistence_spec.get("strategy") if isinstance(persistence_spec, dict) else None
    if persistence not in (None, "READ_ONLY_JSON", "JSON_SEED_LOCAL_STORAGE"):
        raise ValueError("Unsupported persistence strategy")
    collections = data_spec.get("collections", [])
    operations = data_spec.get("operations", [])
    needs_data = bool(collections or operations or data_spec.get("initial_data") is not None)
    operation_names = {str(item.get("operation", "")).lower() if isinstance(item, dict)
                       else str(item).lower() for item in operations}
    mutable_data = bool(operation_names & {"create", "update", "delete"})
    if mutable_data and persistence != "JSON_SEED_LOCAL_STORAGE":
        raise ValueError("Mutable client data requires JSON_SEED_LOCAL_STORAGE persistence")
    if needs_data:
        if persistence not in ("READ_ONLY_JSON", "JSON_SEED_LOCAL_STORAGE"):
            raise ValueError("Data applications must declare READ_ONLY_JSON or JSON_SEED_LOCAL_STORAGE")
        data_spec.setdefault("files", [])
        data_file = next((item for item in data_spec["files"]
                          if isinstance(item, dict) and item.get("path") == "data/data.json"), None)
        if data_file is None:
            data_file = {"path": "data/data.json", "purpose": "Initial or read-only application data"}
            data_spec["files"].append(data_file)
        relevant_ids = sorted({feature_id for operation in operations if isinstance(operation, dict)
                               for feature_id in operation.get("feature_ids", [])})
        if not relevant_ids:
            relevant_ids = [feature["id"] for feature in spec["APPROVED_FEATURES"]
                            if feature.get("data_scope") or feature.get("data_flow")]
        if not relevant_ids:
            relevant_ids = list(feature_ids)
        data_file.setdefault("feature_ids", relevant_ids)
        if isinstance(persistence_spec, dict) and persistence == "JSON_SEED_LOCAL_STORAGE":
            persistence_spec["seed_path"] = "data/data.json"
            collection_name = next((item.get("name") for item in collections
                                    if isinstance(item, dict) and item.get("name")), None)
            if collection_name:
                persistence_spec.setdefault("seed_collection", collection_name)
            storage_key = persistence_spec.get("storage_key")
            initial_data = data_spec.get("initial_data", {})
            seed_value = initial_data.get(collection_name) if collection_name and isinstance(initial_data, dict) else None
            if seed_value is not None:
                persistence_spec["initial_storage_value"] = seed_value
        if "data/data.json" not in paths:
            normalized_files.append({"path": "data/data.json", "purpose": data_file["purpose"],
                                     "feature_ids": data_file["feature_ids"]})
            paths.append("data/data.json")
    all_feature_ids = set(feature_ids)
    for file_entry in normalized_files:
        file_entry.setdefault("feature_ids", sorted(all_feature_ids))
        unknown = set(file_entry["feature_ids"]) - all_feature_ids
        if unknown:
            raise ValueError(f"File references unknown feature IDs: {sorted(unknown)}")
    file_spec["files"] = normalized_files
    spec["FILE_SPECIFICATION"] = file_spec
    spec["DATA_SPECIFICATION"] = data_spec
    if persistence == "JSON_SEED_LOCAL_STORAGE":
        persistence = data_spec["persistence"]
        seed_instructions = (
            "\nMANDATORY SEED INITIALIZATION: Because DATA_SPECIFICATION.persistence.strategy is JSON_SEED_LOCAL_STORAGE, "
            "data/data.json is the initial data source and MUST be loaded into localStorage when the specified key is absent. "
            "Fetch only './data/data.json'; read the specified seed_collection from its root object; serialize that collection "
            "under the specified storage_key. On later loads use the existing localStorage value. All create/update/delete "
            "operations write only to localStorage. Never use an empty in-code default instead of loading the JSON seed, "
            "and never claim JavaScript writes changes back to data.json. FILE_SPECIFICATION authorizes data/data.json."
        )
        spec["FRONTEND_AGENT_PROMPT"] = str(spec["FRONTEND_AGENT_PROMPT"]).rstrip() + seed_instructions
        flow_ids = sorted({feature_id for operation in operations if isinstance(operation, dict)
                           for feature_id in operation.get("feature_ids", [])}) or list(feature_ids)
        if isinstance(spec["DATA_FLOW_SPECIFICATION"], dict):
            spec["DATA_FLOW_SPECIFICATION"]["PERSISTENCE_FLOW"] = {
                "feature_ids": flow_ids,
                "steps": ["Check localStorage storage_key", "If absent fetch data/data.json",
                          "Read seed_collection and initialize localStorage", "Use localStorage at runtime",
                          "Render application state"],
                "writes_data_json": False,
            }
    for data_file in data_spec.get("files", []):
        path = data_file.get("path") if isinstance(data_file, dict) else None
        if path not in paths:
            raise ValueError(f"Data file is not declared in FILE_SPECIFICATION: {path}")
    # Preserve legacy fields as empty; they cannot authorize implementation.
    spec["backend"] = {}
    spec["database"] = {}
    spec.setdefault("frontend", {"pages": [], "features": []})

    base_slug = re.sub(r"[^a-z0-9]+", "-", spec["project"].lower()).strip("-")[:48] or "website"
    configured_root = Path(os.getenv("OUTPUT_ROOT", "generated_sites"))
    if not configured_root.is_absolute():
        configured_root = Path(__file__).resolve().parents[3] / configured_root
    output_root = configured_root.resolve()
    slug, suffix = base_slug, 2
    while (output_root / slug).exists():
        suffix_text = f"-{suffix}"
        slug = base_slug[:48 - len(suffix_text)] + suffix_text
        suffix += 1
    tool_context.state["project_spec"] = json.dumps(spec, indent=2)
    tool_context.state["project_slug"] = slug
    tool_context.state["test_report"] = json.dumps({"status": "NOT_RUN"})
    tool_context.state["written_files"] = []
    project_dir_from_context(tool_context).joinpath("project_spec.json").write_text(
        json.dumps(spec, indent=2), encoding="utf-8"
    )
    return {"project": spec["project"], "slug": slug, "saved": True}


def inspect_generated_files(tool_context: ToolContext) -> dict:
    """Report exactly the files declared by FILE_SPECIFICATION and whether present."""
    root = project_dir_from_context(tool_context)
    spec = json.loads(tool_context.state.get("project_spec", "{}"))
    expected = [str(item.get("path", "")) if isinstance(item, dict) else str(item)
                for item in spec.get("FILE_SPECIFICATION", {}).get("files", [])]
    files = {name: (root / name).is_file() for name in expected}
    return {"project_dir": str(root), "files": files,
            "missing": [name for name, exists in files.items() if not exists]}
