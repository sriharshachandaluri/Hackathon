import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from website_generator.agents.integration_agent.agent import run_client_integration_checks
from website_generator.agents.shared import save_spec, write_project_file


class Context:
    def __init__(self):
        self.state = {}


def sample_spec():
    return {
        "project": "Scope Demo",
        "purpose": "Test local data behavior",
        "PROJECT_SCOPE": "One-page app",
        "APPROVED_FEATURES": [
            {"id": "FEATURE_001", "name": "Add item", "data_scope": ["items"], "data_flow": "UI to localStorage"},
            {"id": "FEATURE_002", "name": "View items", "data_scope": ["items"], "data_flow": "localStorage to UI"},
        ],
        "OUT_OF_SCOPE_FUNCTIONALITY": [],
        "FRONTEND_SPECIFICATION": {"pages": []},
        "DATA_SPECIFICATION": {
            "files": [], "root_structure": {"items": []},
            "collections": [{"name": "items", "fields": [{"name": "title", "type": "string", "required": True}]}],
            "initial_data": {"items": []},
            "operations": [{"operation": "create", "feature_ids": ["FEATURE_001"]},
                           {"operation": "read", "feature_ids": ["FEATURE_002"]}],
            "persistence": {"strategy": "JSON_SEED_LOCAL_STORAGE", "storage_key": "items"},
        },
        "CLIENT_LOGIC_SPECIFICATION": {"functions": []},
        "FILE_SPECIFICATION": {"files": [{"path": name} for name in ("index.html", "style.css", "script.js")]},
        "TRACEABILITY_MATRIX": {},
        "SCOPE_AUDIT": {},
        "FRONTEND_AGENT_PROMPT": "Only approved scope",
    }


class SharedSpecificationTests(unittest.TestCase):
    def test_save_spec_adds_required_seed_file_and_avoids_existing_slug(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"OUTPUT_ROOT": directory}):
            first = Context()
            saved = save_spec(sample_spec(), first)
            self.assertEqual(saved["slug"], "scope-demo")
            spec = json.loads(first.state["project_spec"])
            self.assertIn("data/data.json", [item["path"] for item in spec["FILE_SPECIFICATION"]["files"]])
            self.assertIn("data/data.json", [item["path"] for item in spec["DATA_SPECIFICATION"]["files"]])
            self.assertIn("FEATURE_001", next(item for item in spec["FILE_SPECIFICATION"]["files"]
                                                if item["path"] == "data/data.json")["feature_ids"])

            second = Context()
            saved_again = save_spec(sample_spec(), second)
            self.assertEqual(saved_again["slug"], "scope-demo-2")

    def test_save_spec_rejects_missing_project_name_and_mutable_without_seed_strategy(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"OUTPUT_ROOT": directory}):
            missing_name = sample_spec()
            missing_name.pop("project")
            with self.assertRaisesRegex(ValueError, "explicit nonempty project name"):
                save_spec(missing_name, Context())
            no_seed = sample_spec()
            no_seed["DATA_SPECIFICATION"]["persistence"]["strategy"] = "READ_ONLY_JSON"
            with self.assertRaisesRegex(ValueError, "Mutable client data"):
                save_spec(no_seed, Context())

    def test_integration_check_catches_undeclared_server_artifacts(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"OUTPUT_ROOT": directory}):
            context = Context()
            save_spec(sample_spec(), context)
            spec = json.loads(context.state["project_spec"])
            root = Path(directory) / context.state["project_slug"]
            context.state["project_spec"] = json.dumps(spec)
            write_project_file("index.html", '<link href="style.css"><script src="script.js"></script><div id="list" data-feature-ids="FEATURE_001 FEATURE_002"></div>', context)
            write_project_file("style.css", "/* FEATURE_001 FEATURE_002 */", context)
            write_project_file("script.js", "// FEATURE_001 FEATURE_002\nlocalStorage.getItem('items'); fetch('./data/data.json'); document.getElementById('list');", context)
            write_project_file("data/data.json", '{"items":[]}', context)
            self.assertEqual(run_client_integration_checks(context)["status"], "PASS")
            (root / "Dockerfile").write_text("FROM python", encoding="utf-8")
            report = run_client_integration_checks(context)
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any(item["name"] == "file-scope" and not item["passed"]
                                for item in report["checks"]))

    def test_project_writer_rejects_unlisted_and_server_files(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"OUTPUT_ROOT": directory}):
            context = Context()
            save_spec(sample_spec(), context)
            context.state["project_spec"] = json.dumps(json.loads(context.state["project_spec"]))
            with self.assertRaisesRegex(ValueError, "not authorized"):
                write_project_file("README.md", "not listed", context)
            with self.assertRaisesRegex(ValueError, "forbidden"):
                write_project_file("backend/main.py", "pass", context)


if __name__ == "__main__":
    unittest.main()
