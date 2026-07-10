"""Tests for the release metadata and changelog verifier."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.verify_pypi_artifacts import artifact_hashes, compare_artifacts
from scripts.verify_release import distribution_version


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERIFIER = PROJECT_ROOT / "scripts" / "verify_release.py"


def _project(root: Path, version: str = "1.2.3") -> Path:
    (root / "gpt2agent").mkdir(parents=True)
    (root / ".claude-plugin").mkdir()
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "gpt2agent"\nversion = "{version}"\n'
    )
    (root / "gpt2agent" / "__init__.py").write_text(f'__version__ = "{version}"\n')
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"version": version})
    )
    (root / "server.json").write_text(
        json.dumps({"version": version, "packages": [{"version": version}]})
    )
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n"
        "## [Unreleased]\n\n"
        f"## [{version}] - 2026-07-09\n\n"
        "### Fixed\n\n- Verified release metadata.\n"
    )
    return root


def _verify(root: Path, tag: str | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(VERIFIER), "--root", str(root)]
    if tag is not None:
        command.extend(["--tag", tag])
    return subprocess.run(command, capture_output=True, text=True, check=False)


def test_release_verifier_accepts_consistent_tree(tmp_path) -> None:
    result = _verify(_project(tmp_path), "v1.2.3")

    assert result.returncode == 0, result.stderr
    assert "release metadata verified: 1.2.3" in result.stdout


@pytest.mark.parametrize(
    ("project_version", "expected_distribution_version"),
    [
        ("1.2.3", "1.2.3"),
        ("1.2.3-alpha1", "1.2.3a1"),
        ("1.2.3-beta2", "1.2.3b2"),
        ("1.2.3-rc10", "1.2.3rc10"),
    ],
)
def test_distribution_version_normalizes_supported_semver_prereleases(
    project_version: str, expected_distribution_version: str
) -> None:
    assert distribution_version(project_version) == expected_distribution_version


@pytest.mark.parametrize("version", ["1.2.3-preview1", "1.2.3-rc.1", "1.2.3+build.1"])
def test_release_verifier_rejects_unsupported_version_suffixes(
    tmp_path: Path, version: str
) -> None:
    result = _verify(_project(tmp_path, version), f"v{version}")

    assert result.returncode == 1
    assert "not supported" in result.stderr


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("package", "gpt2agent/__init__.py"),
        ("plugin", ".claude-plugin/plugin.json"),
        ("server", "server.json version"),
        ("server_package", "server.json packages[0].version"),
        ("changelog_missing", "CHANGELOG.md"),
        ("changelog_empty", "CHANGELOG.md"),
    ],
)
def test_release_verifier_names_each_inconsistent_surface(tmp_path, mutation, expected) -> None:
    root = _project(tmp_path)
    if mutation == "package":
        (root / "gpt2agent" / "__init__.py").write_text('__version__ = "1.2.4"\n')
    elif mutation == "plugin":
        (root / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"version": "1.2.4"})
        )
    elif mutation == "server":
        (root / "server.json").write_text(
            json.dumps({"version": "1.2.4", "packages": [{"version": "1.2.3"}]})
        )
    elif mutation == "server_package":
        (root / "server.json").write_text(
            json.dumps({"version": "1.2.3", "packages": [{"version": "1.2.4"}]})
        )
    elif mutation == "changelog_missing":
        (root / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n")
    elif mutation == "changelog_empty":
        (root / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [1.2.3] - 2026-07-09\n\n## [1.2.2] - 2026-07-01\n"
        )

    result = _verify(root, "v1.2.3")

    assert result.returncode == 1
    assert expected in result.stderr


def test_release_verifier_rejects_mismatched_tag(tmp_path) -> None:
    result = _verify(_project(tmp_path), "v1.2.4")

    assert result.returncode == 1
    assert "tag v1.2.4" in result.stderr


def test_release_verifier_accepts_live_tree_without_tag() -> None:
    result = _verify(PROJECT_ROOT)

    assert result.returncode == 0, result.stderr


def test_pypi_artifact_verifier_hashes_only_release_files(tmp_path) -> None:
    wheel = tmp_path / "gpt2agent-1.2.3-py3-none-any.whl"
    sdist = tmp_path / "gpt2agent-1.2.3.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    (tmp_path / "ignored.txt").write_text("ignored")

    hashes = artifact_hashes(tmp_path)

    assert set(hashes) == {wheel.name, sdist.name}
    assert all(re.fullmatch(r"[0-9a-f]{64}", digest) for digest in hashes.values())


@pytest.mark.parametrize(
    ("remote", "require_complete", "expected"),
    [
        ({"wheel.whl": "aaa"}, False, []),
        ({"wheel.whl": "aaa", "source.tar.gz": "bbb"}, True, []),
        ({"wheel.whl": "wrong"}, False, ["SHA-256 mismatch for wheel.whl"]),
        ({"other.whl": "aaa"}, False, ["PyPI has unexpected artifact other.whl"]),
        ({"wheel.whl": "aaa"}, True, ["PyPI is missing artifact source.tar.gz"]),
        (None, False, []),
        (None, True, ["PyPI release does not exist"]),
    ],
)
def test_pypi_artifact_verifier_fails_closed_on_drift(
    remote, require_complete, expected
) -> None:
    local = {"wheel.whl": "aaa", "source.tar.gz": "bbb"}

    assert compare_artifacts(local, remote, require_complete=require_complete) == expected


def test_pypi_pre_publish_verifier_rejects_partial_existing_release() -> None:
    local = {"wheel.whl": "aaa", "source.tar.gz": "new-sdist"}
    remote = {"wheel.whl": "aaa"}

    assert compare_artifacts(
        local,
        remote,
        require_complete=False,
        require_absent=True,
    ) == ["PyPI release already exists; refusing rebuilt artifacts"]


def test_workflow_actions_are_pinned_to_full_commit_shas() -> None:
    workflows = list((PROJECT_ROOT / ".github" / "workflows").glob("*.yml"))
    uses_pattern = re.compile(r"^\s*(?:-\s*)?uses:\s+([^@\s]+)@([^\s#]+)", re.MULTILINE)

    references = [
        (path.name, action, revision)
        for path in workflows
        for action, revision in uses_pattern.findall(path.read_text(encoding="utf-8"))
    ]

    assert references
    assert all(re.fullmatch(r"[0-9a-f]{40}", revision) for _, _, revision in references)


def test_release_workflows_keep_required_source_and_artifact_gates() -> None:
    ci = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    release = (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    readme_flat = re.sub(r"\s+", " ", readme)

    assert "name: Required checks" in ci
    assert "needs: [quality, test, lint-installer]" in ci
    assert 'git cat-file -t "$GITHUB_REF"' in release
    assert "must be an annotated tag" in release
    assert 'git merge-base --is-ancestor "$GITHUB_SHA" origin/main' in release
    assert "python scripts/verify_release.py --tag" in release
    assert "distribution_version" in release
    assert "DIST_VERSION" in release
    assert 'assert version("gpt2agent") == expected_distribution' in release
    assert "Test built artifacts in clean environments" in release
    assert 'python" -m gpt2agent --version' in release
    assert "Require the PyPI version to be absent before publication" in release
    assert "--require-absent --attempts 3 --delay 5" in release
    assert "skip-existing: true" in release
    assert "name: Verify published PyPI artifacts" in release
    assert "--require-complete --attempts 7 --delay 10" in release
    assert "needs: [verify-pypi, verify]" in release
    assert (
        'SKIP_LIVE=1 "$TMP_ROOT/sdist-venv/bin/python" -m pytest -q \\\n'
        "              tests/test_heavy_dr_parser.py"
    ) in release
    assert 'gh pr view "$PR_NUMBER" --json mergeCommit,state' in readme
    assert "```bash\nset -euo pipefail\ngit switch main" in readme
    assert 'git merge-base --is-ancestor "$RELEASE_SHA" origin/main' in readme
    assert 'git switch --detach "$RELEASE_SHA"' in readme
    assert 'git tag -a "$TAG" "$RELEASE_SHA"' in readme
    assert 'git push origin "refs/tags/$TAG"' in readme
    assert "Re-run failed jobs" in readme_flat
    assert "Do not re-run the whole workflow" in readme_flat
    assert "python scripts/verify_release.py --tag v0.0.10" not in readme


def test_account_reported_quota_is_not_documented_as_a_fixed_limit() -> None:
    sse = (PROJECT_ROOT / "gpt2agent" / "sse.py").read_text(encoding="utf-8")

    assert "248 uses / reset cycle" not in sse
