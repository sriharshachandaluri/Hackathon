"""Serve a generated client-side project on an automatically assigned local port."""

from __future__ import annotations

import argparse
import json
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def resolve_project(slug: str) -> Path:
    configured_root = Path(os.getenv("OUTPUT_ROOT", "generated_sites"))
    if not configured_root.is_absolute():
        configured_root = Path(__file__).resolve().parents[2] / configured_root
    output_root = configured_root.resolve()
    project = (output_root / slug).resolve()
    if project.parent != output_root:
        raise ValueError("Project must be a direct child of the generated projects directory")
    if not (project / "index.html").is_file():
        raise FileNotFoundError(f"No index.html found in generated project: {project}")
    report_path = project / "test_report.json"
    if not report_path.is_file():
        raise ValueError("Runner blocked: project has no persisted PASS report")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Runner blocked: test report is invalid") from exc
    if report.get("status") != "PASS" or int(report.get("failed", 0)) != 0:
        raise ValueError("Runner blocked: project has not passed testing")
    return project


def serve_project(project: Path) -> None:
    server = create_server(project)
    address, port = server.server_address[:2]
    print(f"Generated application ready!\n\nFrontend:\nhttp://{address}:{port}\n\nPress Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping static server...", flush=True)
    finally:
        server.shutdown()
        server.server_close()


def create_server(project: Path) -> ThreadingHTTPServer:
    """Create a static server bound to an OS-selected available port."""
    handler = partial(SimpleHTTPRequestHandler, directory=str(project))
    return ThreadingHTTPServer(("127.0.0.1", 0), handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a generated static frontend locally")
    parser.add_argument("project", help="Generated project slug under OUTPUT_ROOT")
    args = parser.parse_args()
    serve_project(resolve_project(args.project))


if __name__ == "__main__":
    main()
