import os
import tempfile
import unittest
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from urllib.request import urlopen
from unittest.mock import patch

from website_generator.runner import create_server, resolve_project
from website_generator.agents.runner_agent.agent import prepare_static_runner


class RunnerTests(unittest.TestCase):
    def test_runner_uses_dynamic_port_and_serves_only_the_project(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "sites"
            project = output / "sample"
            project.mkdir(parents=True)
            (project / "index.html").write_text("<h1>client app</h1>", encoding="utf-8")
            (project / "test_report.json").write_text('{"status":"PASS","failed":0}', encoding="utf-8")
            with patch.dict(os.environ, {"OUTPUT_ROOT": str(output)}):
                self._check_served_project()

    def _check_served_project(self):
        server = create_server(resolve_project("sample"))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            self.assertEqual(host, "127.0.0.1")
            self.assertGreater(port, 0)
            with urlopen(f"http://{host}:{port}/", timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(b"client app", response.read())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_runner_rejects_paths_outside_generated_root(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "sites"
            with patch.dict(os.environ, {"OUTPUT_ROOT": str(output)}):
                with self.assertRaises(ValueError):
                    resolve_project("..")

    def test_runner_refuses_projects_without_a_passing_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "sites"
            project = output / "unfinished"
            project.mkdir(parents=True)
            (project / "index.html").write_text("<h1>not tested</h1>", encoding="utf-8")
            (project / "test_report.json").write_text('{"status":"FAIL","failed":1}', encoding="utf-8")
            with patch.dict(os.environ, {"OUTPUT_ROOT": str(output)}):
                with self.assertRaisesRegex(ValueError, "has not passed"):
                    resolve_project("unfinished")

    def test_runner_handoff_requires_pass_and_returns_fixed_command(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "sites"
            project = output / "tested-app"
            project.mkdir(parents=True)
            (project / "index.html").write_text("<h1>tested</h1>", encoding="utf-8")
            (project / "test_report.json").write_text('{"status":"PASS","failed":0}', encoding="utf-8")
            context = SimpleNamespace(state={"project_slug": "tested-app", "test_report": '{"status":"PASS","failed":0}'})
            with patch.dict(os.environ, {"OUTPUT_ROOT": str(output)}):
                result = prepare_static_runner(context)
            self.assertEqual(result["command"], "python -m website_generator.runner tested-app")
            self.assertIn("Ctrl+C", result["stop"])

            context.state["test_report"] = '{"status":"FAIL","failed":1}'
            with patch.dict(os.environ, {"OUTPUT_ROOT": str(output)}):
                with self.assertRaisesRegex(ValueError, "has not passed"):
                    prepare_static_runner(context)


if __name__ == "__main__":
    unittest.main()
