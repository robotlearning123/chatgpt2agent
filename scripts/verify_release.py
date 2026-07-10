#!/usr/bin/env python3
"""Fail closed when release versions or changelog metadata disagree."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 after installing project dependencies
    import tomli as tomllib  # type: ignore[no-redef]


_VERSION_RE = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?\Z")


def _package_version(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == "__version__" for target in targets):
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
    raise ValueError("gpt2agent/__init__.py has no literal __version__ assignment")


def _changelog_errors(path: Path, version: str) -> list[str]:
    text = path.read_text(encoding="utf-8")
    heading = re.compile(
        rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}\s*$",
        re.MULTILINE,
    )
    match = heading.search(text)
    if match is None:
        return [f"CHANGELOG.md missing exact dated section for {version}"]
    next_section = re.search(r"^## \[", text[match.end() :], re.MULTILINE)
    end = match.end() + next_section.start() if next_section else len(text)
    body_lines = [
        line.strip()
        for line in text[match.end() : end].splitlines()
        if line.strip() and not line.lstrip().startswith("###")
    ]
    if not body_lines:
        return [f"CHANGELOG.md section for {version} has no release notes"]
    return []


def verify(root: Path, tag: str | None = None) -> tuple[str | None, list[str]]:
    errors: list[str] = []
    try:
        with (root / "pyproject.toml").open("rb") as stream:
            version = str(tomllib.load(stream)["project"]["version"])
    except (OSError, KeyError, TypeError, ValueError) as exc:
        return None, [f"pyproject.toml: {exc}"]

    if not _VERSION_RE.fullmatch(version):
        errors.append(f"pyproject.toml version is not SemVer-shaped: {version!r}")

    try:
        package_version = _package_version(root / "gpt2agent" / "__init__.py")
        if package_version != version:
            errors.append(
                "gpt2agent/__init__.py version "
                f"{package_version!r} does not match pyproject.toml {version!r}"
            )
    except (OSError, SyntaxError, ValueError) as exc:
        errors.append(str(exc))

    try:
        plugin_version = str(
            json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))[
                "version"
            ]
        )
        if plugin_version != version:
            errors.append(
                ".claude-plugin/plugin.json version "
                f"{plugin_version!r} does not match pyproject.toml {version!r}"
            )
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        errors.append(f".claude-plugin/plugin.json: {exc}")

    try:
        server = json.loads((root / "server.json").read_text(encoding="utf-8"))
        server_version = str(server["version"])
        package_entry_version = str(server["packages"][0]["version"])
        if server_version != version:
            errors.append(
                f"server.json version {server_version!r} does not match pyproject.toml {version!r}"
            )
        if package_entry_version != version:
            errors.append(
                "server.json packages[0].version "
                f"{package_entry_version!r} does not match pyproject.toml {version!r}"
            )
    except (OSError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        errors.append(f"server.json: {exc}")

    try:
        errors.extend(_changelog_errors(root / "CHANGELOG.md", version))
    except OSError as exc:
        errors.append(f"CHANGELOG.md: {exc}")

    if tag is not None:
        expected_tag = f"v{version}"
        if tag != expected_tag:
            errors.append(f"tag {tag} does not match project version tag {expected_tag}")

    return version, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--tag", help="Expected git tag, including the leading v")
    args = parser.parse_args(argv)

    version, errors = verify(args.root.resolve(), args.tag)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"release metadata verified: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
