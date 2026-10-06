from __future__ import annotations

import json
import re
import shutil
import subprocess

from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext

from ..integration_agent.agent import run_client_integration_checks
from ..shared import inspect_generated_files, project_dir_from_context
from ...config import MODEL


def _node_runtime_smoke(root, html: str, js: str, data: dict) -> tuple[bool, str]:
    node = shutil.which("node")
    if not node:
        return False, "Node.js is required for JavaScript syntax and runtime smoke checks"
    harness = r'''const vm = require("node:vm");
const html = JSON.parse(process.env.SMOKE_HTML);
const script = JSON.parse(process.env.SMOKE_JS);
const seed = JSON.parse(process.env.SMOKE_DATA || "{}");
const elements = new Map();
const listeners = [];
const errors = [];
class Element {
  constructor(id="") { this.id=id; this.value=""; this._innerHTML=""; this._textContent=""; this.listeners={}; this.dataset={}; this.style={}; this.children=[]; this.classList={add(){},remove(){},toggle(){}}; }
  get innerHTML() { return this._innerHTML; }
  set innerHTML(value) { this._innerHTML=String(value); if(this._innerHTML==="") this.children=[]; this._textContent=this._innerHTML.replace(/<[^>]*>/g,""); }
  get textContent() { return this._textContent; }
  set textContent(value) { this._textContent=String(value); this._innerHTML=this._textContent.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
  addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); }
  appendChild(child) { this.children.push(child); return child; }
  remove() {}
  reset() {}
  setAttribute() {}
  getAttribute() { return null; }
  querySelector(s) { return selector(s); }
  querySelectorAll() { return []; }
}
function selector(s) { const m=String(s).match(/^#([\w:.-]+)/); return m ? element(m[1]) : new Element(); }
function element(id) { if (!elements.has(id)) elements.set(id,new Element(id)); return elements.get(id); }
for (const m of html.matchAll(/\bid=["']([^"']+)/g)) element(m[1]);
for (const tag of html.matchAll(/<(input|textarea)\b[^>]*>/gi)) {
  const id=tag[0].match(/\bid=["']([^"']+)/i);
  const type=tag[0].match(/\btype=["']([^"']+)/i);
  if(id) element(id[1]).type=type?type[1].toLowerCase():tag[1].toLowerCase();
}
for (const tag of html.matchAll(/<button\b[^>]*>/gi)) {
  const id=tag[0].match(/\bid=["']([^"']+)/i); const type=tag[0].match(/\btype=["']([^"']+)/i);
  if(id) element(id[1]).type=type?type[1].toLowerCase():"button";
}
const document = { getElementById:element, querySelector:selector, querySelectorAll(){return [];}, createElement(){return new Element();}, addEventListener(n,fn){(listeners.push([n,fn]));} };
const store = new Map();
const localStorage = {getItem(k){return store.has(k)?store.get(k):null;},setItem(k,v){store.set(k,String(v));},removeItem(k){store.delete(k);},clear(){store.clear();}};
const context = {document, localStorage, console:{log(){},warn(){},error(...a){errors.push(a.join(" "));}}, window:{addEventListener(n,fn){listeners.push(["window:"+n,fn]);}}, fetch:async()=>({ok:true,json:async()=>seed}), setTimeout(fn){fn();return 1;}, clearTimeout(){}, Event:function(n){this.type=n;}, alert(){}, confirm(){return true;}, URL, URLSearchParams, Date, Math, JSON, Promise};
context.globalThis=context;
(async()=>{
  vm.runInNewContext(script,context,{timeout:1500});
  for(const [n,fn] of listeners) if(n==="DOMContentLoaded") await fn();
  await new Promise(r=>setImmediate(r));
  const submitters=[...elements.values()].filter(e=>e.listeners.submit);
  const clickers=[...elements.values()].filter(e=>e.listeners.click && (e.type==="submit" || !submitters.length));
  const fillInputs=()=>{for(const e of elements.values()) if(e.type!==undefined && e.type!=="submit" && e.type!=="button") e.value=e.type==="email"?"scope@example.test":"Scope smoke test";};
  if(submitters.length){ for(const form of submitters){ fillInputs(); for(const fn of form.listeners.submit) await fn({preventDefault(){},target:form,submitter:null}); } }
  else if(clickers.length){ fillInputs(); for(const fn of clickers[0].listeners.click) await fn({preventDefault(){},target:clickers[0],currentTarget:clickers[0]}); }
  await new Promise(r=>setImmediate(r));
const allText=[]; const walk=e=>{allText.push(e.textContent+" "+e.innerHTML); for(const c of e.children) walk(c);}; for(const e of elements.values()) walk(e);
  const stored=Object.fromEntries(store.entries());
  process.stdout.write(JSON.stringify({ok:true,submitHandlers:submitters.length,storage:stored,rendered:allText.join(" ").slice(0,2000),errors}));
})().catch(e=>{process.stdout.write(JSON.stringify({ok:false,error:String(e),stack:e.stack}));process.exitCode=1;});
'''
    env = dict(__import__("os").environ)
    env["SMOKE_HTML"] = json.dumps(html)
    env["SMOKE_JS"] = json.dumps(js)
    env["SMOKE_DATA"] = json.dumps(data)
    try:
        result = subprocess.run([node, "-e", harness], cwd=root, env=env,
                                capture_output=True, text=True, timeout=8, check=False)
    except subprocess.TimeoutExpired:
        return False, "JavaScript runtime smoke check timed out"
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False, (result.stderr or result.stdout or "Node smoke check returned no report")[:1000]
    if result.returncode or not report.get("ok"):
        return False, report.get("error", result.stderr or "JavaScript runtime error")
    if report.get("errors"):
        return False, "browser console errors: " + "; ".join(report["errors"])
    return True, json.dumps(report)


def run_project_checks(tool_context: ToolContext) -> dict:
    """Run client integration, syntax, JSON, and isolated JavaScript smoke checks."""
    root = project_dir_from_context(tool_context)
    spec = json.loads(tool_context.state.get("project_spec", "{}"))
    integration = run_client_integration_checks(tool_context)
    checks: list[dict] = []

    def check(name: str, passed: bool, component: str, detail: str = "") -> None:
        checks.append({"name": name, "passed": bool(passed), "component": component, "detail": detail})

    for item in integration["checks"]:
        check("integration:" + item["name"], item["passed"], "integration", item["detail"])

    js_path, html_path = root / "script.js", root / "index.html"
    js = js_path.read_text(encoding="utf-8") if js_path.is_file() else ""
    html = html_path.read_text(encoding="utf-8") if html_path.is_file() else ""
    node = shutil.which("node")
    if node and js_path.is_file():
        result = subprocess.run([node, "--check", str(js_path)], capture_output=True, text=True, timeout=8)
        check("javascript-syntax", result.returncode == 0, "frontend",
              result.stderr.strip() or "Node.js parsed script.js")
    else:
        check("javascript-syntax", False, "frontend", "Node.js or script.js is unavailable")

    seed_data = {}
    data_spec = spec.get("DATA_SPECIFICATION", {})
    seed_paths = [item.get("path") for item in data_spec.get("files", []) if isinstance(item, dict)]
    for seed_path in seed_paths:
        target = root / seed_path
        if target.is_file():
            try:
                seed_data = json.loads(target.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
            break
    if js_path.is_file() and html_path.is_file() and node:
        smoke_seed = json.loads(json.dumps(seed_data))
        for collection in data_spec.get("collections", []):
            name = collection.get("name")
            if not name or not isinstance(smoke_seed.get(name), list) or smoke_seed[name]:
                continue
            sample = {}
            for field in collection.get("fields", []):
                field_type = str(field.get("type", "string")).lower()
                if field_type in ("number", "integer"):
                    sample[field["name"]] = 123
                elif field_type in ("boolean", "bool"):
                    sample[field["name"]] = True
                else:
                    sample[field["name"]] = f"Seed smoke {field['name']}"
            if sample:
                smoke_seed[name] = [sample]
        passed, detail = _node_runtime_smoke(root, html, js, smoke_seed)
        if passed:
            try:
                runtime = json.loads(detail)
                rendered = runtime.get("rendered", "")
                operations = {str(item.get("operation", "")).lower() for item in data_spec.get("operations", [])
                              if isinstance(item, dict)}
                if "read" in operations and smoke_seed != {}:
                    sample_text = next((value for values in smoke_seed.values() if isinstance(values, list) and values
                                        for value in values[0].values() if isinstance(value, str)), None)
                    if sample_text and sample_text not in rendered:
                        passed, detail = False, "runtime did not render seed data: " + sample_text
                if "create" in operations:
                    persistence = data_spec.get("persistence", {})
                    key = persistence.get("storage_key") if isinstance(persistence, dict) else None
                    stored_raw = runtime.get("storage", {}).get(str(key)) if key else None
                    try:
                        stored = json.loads(stored_raw) if stored_raw else None
                    except json.JSONDecodeError:
                        stored = None
                    collection_name = next((item.get("name") for item in data_spec.get("collections", [])
                                            if isinstance(item, dict) and item.get("name")), None)
                    records = stored.get(collection_name, []) if isinstance(stored, dict) and collection_name else stored
                    if not isinstance(records, list) or not records:
                        passed, detail = False, "submit smoke event did not persist a created collection record"
                    elif smoke_seed.get(collection_name) and len(records) < len(smoke_seed[collection_name]) + 1:
                        passed, detail = False, "runtime persistence did not retain JSON seed records and the created record"
                    else:
                        required_fields = {field.get("name") for collection in data_spec.get("collections", [])
                                           if collection.get("name") == collection_name
                                           for field in collection.get("fields", []) if field.get("required")}
                        if required_fields and not required_fields.issubset(records[-1]):
                            passed, detail = False, "created record is missing required fields: " + ", ".join(sorted(required_fields))
            except (json.JSONDecodeError, TypeError, AttributeError) as exc:
                passed, detail = False, f"could not interpret runtime smoke result: {exc}"
        check("javascript-runtime-smoke", passed, "frontend", detail)

    failed = [item for item in checks if not item["passed"]]
    report = {
        "status": "FAIL" if failed else "PASS",
        "tests": len(checks), "passed": len(checks) - len(failed), "failed": len(failed),
        "errors": [f"{item['name']}: {item['detail']}" for item in failed],
        "feature_results": [
            {"feature_id": feature.get("id"), "expected_behavior": feature.get("expected_behavior"),
             "source_traceable": str(feature.get("id")) in (html + js)}
            for feature in spec.get("APPROVED_FEATURES", [])
        ],
    }
    if failed:
        report["failed_component"] = failed[0]["component"]
        report["error"] = report["errors"][0]
        report["suggested_fix"] = f"Repair only this scoped failure: {failed[0]['name']}"
    tool_context.state["test_report"] = json.dumps(report)
    (root / "test_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if report["status"] == "PASS":
        tool_context.actions.escalate = True
    return report


testing_agent = Agent(
    name="testing_agent",
    model=MODEL,
    output_key="testing_result",
    instruction="""You are the strict client application Testing Agent. Call run_project_checks and report its structured result accurately. Review every APPROVED_FEATURE in {project_spec}; for each, state feature ID, expected behavior, implementation evidence, and PASS/FAIL. PASS requires all deterministic integration checks, JavaScript syntax/runtime smoke checks, data shape and storage checks, scope checks, and evidence that every feature behavior is actually implemented. If evidence is insufficient or a feature does not work, report FAIL with exact file/behavior and a scoped suggested_fix. Do not claim full browser testing; the runtime harness is an isolated DOM/localStorage smoke test.""",
    tools=[inspect_generated_files, run_project_checks],
)
