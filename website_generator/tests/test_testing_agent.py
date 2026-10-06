import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from website_generator.agents.shared import save_spec, write_project_file
from website_generator.agents.testing_agent.agent import run_project_checks


def spec():
    return {
        "project": "Runtime Smoke",
        "purpose": "Verify add and view behavior",
        "PROJECT_SCOPE": "Add and view entries",
        "APPROVED_FEATURES": [
            {"id": "FEATURE_001", "name": "Add entry", "data_scope": ["entries"], "data_flow": "form to storage"},
            {"id": "FEATURE_002", "name": "View entries", "data_scope": ["entries"], "data_flow": "storage to list"},
        ],
        "OUT_OF_SCOPE_FUNCTIONALITY": [],
        "FRONTEND_SPECIFICATION": {"pages": []},
        "DATA_SPECIFICATION": {
            "files": [], "root_structure": {"entries": []},
            "collections": [{"name": "entries", "fields": [{"name": "title", "type": "string", "required": True}]}],
            "initial_data": {"entries": []},
            "operations": [{"operation": "create", "feature_ids": ["FEATURE_001"]},
                           {"operation": "read", "feature_ids": ["FEATURE_002"]}],
            "persistence": {"strategy": "JSON_SEED_LOCAL_STORAGE", "storage_key": "entries"},
        },
        "CLIENT_LOGIC_SPECIFICATION": {"functions": []},
        "FILE_SPECIFICATION": {"files": [{"path": name} for name in ("index.html", "style.css", "script.js")]},
        "TRACEABILITY_MATRIX": {}, "SCOPE_AUDIT": {}, "FRONTEND_AGENT_PROMPT": "Only these features",
    }


HTML = '''<!doctype html><html><head><link rel="stylesheet" href="style.css"></head><body>
<form id="entryForm" data-feature-ids="FEATURE_001"><input id="titleInput" type="text"><button id="submitButton" type="submit">Add</button></form>
<ul id="entryList" data-feature-ids="FEATURE_002"></ul><script src="script.js"></script></body></html>'''
CSS = "/* FEATURE_001 FEATURE_002 */"
JS = '''// FEATURE_001 FEATURE_002
const KEY = 'entries';
const form = document.getElementById('entryForm');
const titleInput = document.getElementById('titleInput');
const list = document.getElementById('entryList');
function render() { const rows = JSON.parse(localStorage.getItem(KEY) || '[]'); list.innerHTML=''; rows.forEach(row => { const li=document.createElement('li'); li.textContent=row.title; list.appendChild(li); }); }
document.addEventListener('DOMContentLoaded', async () => { if (localStorage.getItem(KEY) === null) { const response=await fetch('./data/data.json'); const data=await response.json(); localStorage.setItem(KEY, JSON.stringify(data.entries)); } render(); });
form.addEventListener('submit', event => { event.preventDefault(); const rows=JSON.parse(localStorage.getItem(KEY) || '[]'); rows.push({title:titleInput.value.trim()}); localStorage.setItem(KEY, JSON.stringify(rows)); render(); });'''


class TestingAgentSmokeTests(unittest.TestCase):
    def _run(self, code):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"OUTPUT_ROOT": directory}):
            context = SimpleNamespace(state={}, actions=SimpleNamespace(escalate=False))
            save_spec(spec(), context)
            context.state["project_spec"] = json.dumps(json.loads(context.state["project_spec"]))
            write_project_file("index.html", HTML, context)
            write_project_file("style.css", CSS, context)
            write_project_file("script.js", code, context)
            write_project_file("data/data.json", '{"entries":[]}', context)
            return run_project_checks(context)

    def test_runtime_check_exercises_seed_view_and_create_persistence(self):
        report = self._run(JS)
        self.assertEqual(report["status"], "PASS", report["errors"])

    def test_runtime_check_fails_when_create_does_not_persist(self):
        broken = JS.replace("localStorage.setItem(KEY, JSON.stringify(rows)); render();", "render();")
        report = self._run(broken)
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any("javascript-runtime-smoke" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
