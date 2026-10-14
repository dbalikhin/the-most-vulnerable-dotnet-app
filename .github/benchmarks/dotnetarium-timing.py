import collections
import json
import os
from pathlib import Path
import subprocess
import time

root = Path.cwd()
out = root / "timing-results"
out.mkdir(exist_ok=True)
mode, budget = os.environ["SCAN_MODE"], os.environ["SCAN_BUDGET"]
cmd = [str(Path(os.environ["TOOL_HOME"]) / "dotnetarium"), str(root / "DotnetSecurityFailures/DotnetSecurityFailures.csproj"), "--configuration", "Debug", "--framework", "net10.0", "--sarif", str(out / "results.sarif")]
if mode == "nb":
    cmd.append("-nb")
if budget != "default":
    config = out / "dotnetarium.json"
    config.write_text(json.dumps({"Version": "2.0", "AnalysisProfile": budget}, indent=2))
    cmd.extend(["--config", str(config)])
start = time.perf_counter()
with (out / "scan.log").open("w") as log:
    p = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
elapsed = time.perf_counter() - start
record = {
    "tool": "Dotnetarium", "version": "2.6.0",
    "package_source_commit": "6e268487368ba65f6407b7a81cc46c8e3f3db9c5",
    "local_package_source_commit": "50e5bdc1951ac452b5d030cc583c00f50f5cb669",
    "package_note": "Published release commit differs from the local package commit; scanner source trees were verified identical.",
    "mode": mode, "requested_budget": budget, "effective_budget": "full" if budget == "default" else budget,
    "scanner_wall_seconds": round(elapsed, 6), "scanner_exit_code": p.returncode, "command": cmd,
    "application_baseline_commit": "60d060faf08079887e71a98498fe9a9d623e8ffc",
    "application_tree": subprocess.check_output(["git", "rev-parse", "HEAD:DotnetSecurityFailures"], text=True).strip(),
    "workflow_commit": os.environ["GITHUB_SHA"], "run_id": os.environ["GITHUB_RUN_ID"],
    "dotnet_sdk": subprocess.check_output(["dotnet", "--version"], text=True).strip(),
    "rule_policy": "All CLI security rules; no editorconfig suppression; remote model; no online secret verification."
}
assert record["application_tree"] == "53601be69437b9af12d385e673c7831518709a50"
sarif = out / "results.sarif"
if sarif.exists():
    run = json.loads(sarif.read_text())["runs"][0]
    record["findings"] = len(run.get("results", []))
    record["by_rule"] = dict(collections.Counter(x["ruleId"] for x in run.get("results", [])))
    invocation = run.get("invocations", [{}])[0]
    props = invocation.get("properties", {})
    record["coverage"] = props.get("dotnetarium.coverage")
    record["scanner_stages"] = props.get("dotnetarium.stageSeconds", {})
    record["notifications"] = dict(collections.Counter(n.get("descriptor", {}).get("id") for n in invocation.get("toolExecutionNotifications", [])))
(out / "timing.json").write_text(json.dumps(record, indent=2))
print("DOTNETARIUM_TIMING " + json.dumps(record, separators=(",", ":")))
with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
    f.write(f"Scanner: {elapsed:.3f}s; exit {p.returncode}; findings {record.get('findings')}; coverage {record.get('coverage')}\\n")
# Exit 2 is retained as an incomplete scanner result; do not discard SARIF or fail artifact collection.
if not sarif.exists():
    raise SystemExit(2)
