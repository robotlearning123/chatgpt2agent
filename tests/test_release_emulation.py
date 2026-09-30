"""Exercise release-gate failures through the real shell entrypoint, offline."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/release-emulation-test.sh"

FAKE_TOOL = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
name = Path(sys.argv[0]).name
stage = os.environ.get("FAIL_STAGE", "")
with open(os.environ["CALLS"], "a") as log:
    log.write(json.dumps([name, *args]) + "\n")
if name == "python3":
    if args[:1] == ["-c"] and args[1].startswith("import tomllib;"):
        print("0.0.24")
    else:
        os.execv(sys.executable, [sys.executable, *args])
elif name == "python":
    if args[:2] == ["-m", "build"]:
        if stage == "build":
            sys.exit(1)
        out = Path(args[args.index("--outdir") + 1])
        out.mkdir(parents=True)
        (out / "gpt2agent-0.0.24-py3-none-any.whl").touch()
    elif args[:2] == ["-m", "twine"]:
        sys.exit(1 if stage == "twine" else 0)
    elif args[:2] == ["-m", "venv"]:
        dest = Path(args[-1]) / "bin"
        dest.mkdir(parents=True)
        for tool in ["python", "pip", "gpt2agent"]:
            target = dest / tool
            target.write_bytes(Path(sys.argv[0]).read_bytes())
            target.chmod(0o755)
    else:
        print(json.dumps({"tool_count": 30, "manual_param_on_9": True,
                          "account_status": "OK", "chat_manual": "OK",
                          "list_conversations": "OK"}))
elif name == "pip":
    if args[0] == "uninstall":
        Path(sys.argv[0]).with_name("gpt2agent").unlink()
    elif stage == "install":
        sys.exit(1)
elif name == "gpt2agent":
    if args == ["--version"]:
        upgrading = Path(sys.argv[0]).parent.parent.name == "upgrade"
        version = os.environ.get("UPGRADE_VERSION", "0.0.24") if upgrading else "0.0.24"
        print("gpt2agent " + version)
    elif args[0] == "doctor":
        if Path(os.environ["HOME"]).name == "home":
            print("Nothing was probed. Log in, then run doctor again.")
            sys.exit(2)
        failures = os.environ.get("DOCTOR_FAILURES", "0")
        print(f"gpt2agent doctor: 24 OK, {failures} failed, 1 blocked upstream")
        sys.exit(1)
    elif args[0] == "install":
        (Path(os.environ["HOME"]) / ".claude.json").write_text('{"gpt2agent": {}}')
'''


@pytest.fixture
def run_emulation(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nversion = "0.0.24"\n')
    tools = tmp_path / "tools"
    tools.mkdir()
    # Mock build metadata too: this tests the shell gate, not tomllib support in
    # the system's python3, which can differ from the test interpreter on CI.
    for name in ["python", "python3"]:
        tool = tools / name
        tool.write_text(FAKE_TOOL.replace("#!/usr/bin/env python3", f"#!{sys.executable}"))
        tool.chmod(0o755)
    owner = tmp_path / "owner"
    owner.mkdir()
    calls = tmp_path / "calls.jsonl"

    def run(**settings):
        env = dict(os.environ, PATH=f"{tools}{os.pathsep}{os.environ['PATH']}",
                   HOME=str(owner), CODEX_HOME=str(owner / ".codex"),
                   TMPDIR=str(tmp_path), CALLS=str(calls), **settings)
        result = subprocess.run(["bash", str(SCRIPT), str(repo)], env=env,
                                capture_output=True, text=True, timeout=30)
        recorded = [json.loads(line) for line in calls.read_text().splitlines()]
        return result, recorded

    return run


@pytest.mark.parametrize("failures,success", [("0", True), ("1", False), ("10", False)])
def test_doctor_failure_count(run_emulation, failures, success):
    result, _ = run_emulation(DOCTOR_FAILURES=failures)
    assert (result.returncode == 0) is success, result.stdout + result.stderr
    if success:
        assert "RESULT: 11 passed, 0 failed" in result.stdout
    else:
        assert "FAIL  D1 doctor live" in result.stdout


def test_upgrade_must_report_candidate_version(run_emulation):
    result, _ = run_emulation(UPGRADE_VERSION="0.0.23")
    assert result.returncode != 0, result.stdout
    assert "FAIL  F1" in result.stdout


@pytest.mark.parametrize("stage", ["build", "twine", "install"])
def test_prerequisite_failure_stops_before_live_calls(run_emulation, stage):
    result, calls = run_emulation(FAIL_STAGE=stage)
    assert result.returncode != 0, result.stdout
    assert not any(call[0] == "gpt2agent" for call in calls), calls
    assert "RESULT: 11 passed, 0 failed" not in result.stdout
