#!/usr/bin/env python3
"""Preview/apply a pinned update to one clean clone and its editable installs.

Inventory other devices separately: a local PASS is not a fleet-wide PASS.
Existing MCP sessions need a controlled reconnect after verification.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import tempfile


def run(*command: str, cwd: Path | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {command[0]}")
    return result.stdout.strip()


def git(clone: Path, *args: str) -> str:
    return run("git", "-C", str(clone), *args)


def source_version(text: str) -> str:
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        ):
            return str(ast.literal_eval(node.value))
    raise ValueError("target has no literal package version")


def inspect(python: str) -> dict:
    code = ("import json,sys,importlib.metadata as m,gpt2agent; "
            "print(json.dumps({'python':sys.executable,'module':gpt2agent.__file__,"
            "'version':gpt2agent.__version__,'metadata':m.version('gpt2agent')}))")
    return json.loads(run(python, "-I", "-c", code))


def sync(args: argparse.Namespace, receipt: dict) -> None:
    clone = args.clone.resolve()
    if git(clone, "status", "--porcelain"):
        raise ValueError("clone has uncommitted changes; no update performed")
    git(clone, "fetch", "origin", "--quiet")
    # Resolve once, then use only the pinned commit for mutation and checks.
    target = git(clone, "rev-parse", "--verify", f"{args.ref}^{{commit}}")
    previous = git(clone, "rev-parse", "HEAD")
    previous_branch = git(clone, "branch", "--show-current")
    version = source_version(git(clone, "show", f"{target}:gpt2agent/__init__.py"))
    if version != args.version:
        raise ValueError(f"target version {version} != expected {args.version}")
    before = [inspect(python) for python in args.python]
    for item in before:
        if Path(item["module"]).resolve() != clone / "gpt2agent" / "__init__.py":
            raise ValueError(f"interpreter is not attached to this clone: {item['python']}")
    receipt.update(previous=previous, previous_branch=previous_branch, target=target,
                   version=version, before=before, clone=str(clone))
    if not args.apply:
        receipt["status"] = "preview"
        return
    lock = Path(git(clone, "rev-parse", "--path-format=absolute", "--git-path", "fleet-sync.lock"))
    lock.mkdir()  # Never remove somebody else's lock.
    attempted = []
    changed = False
    try:
        if git(clone, "status", "--porcelain") or git(clone, "rev-parse", "HEAD") != previous:
            raise ValueError("clone changed since preflight")
        git(clone, "checkout", "--quiet", "--detach", target)
        changed = True
        for python in args.python:
            attempted.append(python)
            # Refresh dist-info too; checkout alone leaves stale pip metadata.
            run(python, "-m", "pip", "install", "--disable-pip-version-check", "--no-deps",
                "--editable", str(clone), cwd=clone.parent)
        verifier = str(Path(__file__).with_name("verify_install.py"))
        receipt["after"] = [json.loads(run(
            python, "-I", verifier, "--version", version,
            "--root", str(clone / "gpt2agent"), "--mcp", cwd=clone.parent,
        )) for python in args.python]
        if git(clone, "status", "--porcelain") or git(clone, "rev-parse", "HEAD") != target:
            raise ValueError("clone changed during verification")
        receipt["status"] = "verified"
        receipt["running_sessions"] = "existing MCP clients require reconnect; not restarted"
    except Exception:
        if changed:
            try:
                if git(clone, "status", "--porcelain") or git(clone, "rev-parse", "HEAD") != target:
                    raise ValueError("concurrent clone changes prevent safe rollback")
                git(clone, "checkout", "--quiet", "--detach", previous)
                branch_state = "detached"
                if previous_branch:
                    try:
                        branch_tip = git(clone, "rev-parse", "--verify", f"refs/heads/{previous_branch}")
                    except RuntimeError:
                        branch_tip = None
                    if branch_tip == previous:
                        git(clone, "checkout", "--quiet", previous_branch)
                        branch_state = "restored"
                    else:
                        # Preserve another actor's ref change while restoring
                        # editable metadata against the detached old commit.
                        branch_state = "left detached; previous branch changed"
                for python in attempted:
                    run(python, "-m", "pip", "install", "--disable-pip-version-check", "--no-deps",
                        "--editable", str(clone), cwd=clone.parent)
                restored = [inspect(python) for python in args.python]
                old_version = source_version(git(clone, "show", f"{previous}:gpt2agent/__init__.py"))
                if any(item["version"] != old_version or item["metadata"] != old_version
                       for item in restored):
                    raise ValueError("rollback code or metadata version mismatch")
                receipt["rollback"] = {"status": "restored", "installs": restored,
                                       "branch": branch_state}
            except Exception as exc:
                receipt["rollback"] = {"status": "failed", "error": str(exc)}
        raise
    finally:
        lock.rmdir()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ref", help="reviewed commit, tag or remote ref (resolved once)")
    parser.add_argument("--version", required=True, help="expected package version")
    parser.add_argument("--clone", type=Path,
                        default=Path.home() / "workspace/47-chatgpt2agent/gpt2agent")
    parser.add_argument("--python", action="append", required=True,
                        help="editable-install Python; repeat for every installation on this device")
    parser.add_argument("--apply", action="store_true", help="perform update; default is preview")
    parser.add_argument("--receipt", type=Path, required=True, help="new JSON file; never overwritten")
    args = parser.parse_args()
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x", encoding="utf-8") as stream:
        os.chmod(args.receipt, 0o600)
        json.dump({"status": "incomplete"}, stream)
    receipt = {"status": "failed"}
    code = 0
    try:
        sync(args, receipt)
    except Exception as exc:
        receipt.update(status="failed", error=str(exc))
        code = 1
    fd, name = tempfile.mkstemp(prefix=".fleet-sync-", dir=args.receipt.parent)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    os.replace(name, args.receipt)
    print(json.dumps(receipt))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
