"""Safety contracts for pinned deployment; Git operations run on real scratch repos."""
from __future__ import annotations

from argparse import Namespace
import os
import subprocess
import zipfile

import pytest

from scripts import fleet_sync
from scripts.verify_install import verify_files


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()


@pytest.fixture
def deployment(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    origin = tmp_path / 'origin'
    origin.mkdir()
    git(origin, 'init', '-q')
    git(origin, 'config', 'user.name', 'Test')
    git(origin, 'config', 'user.email', 'test@example.invalid')
    package = origin / 'gpt2agent'
    package.mkdir()
    for version in ('0.0.23', '0.0.24'):
        (package / '__init__.py').write_text(f'__version__ = "{version}"\n')
        git(origin, 'add', '.')
        git(origin, 'commit', '-qm', version)
    target = git(origin, 'rev-parse', 'HEAD')
    previous = git(origin, 'rev-parse', 'HEAD~1')
    clone = tmp_path / 'clone'
    subprocess.check_call(['git', 'clone', '-q', str(origin), str(clone)])
    git(clone, 'checkout', '-q', '--detach', previous)
    args = Namespace(clone=clone, ref=target, version='0.0.24', python=['python-a', 'python-b'],
                     apply=False)
    monkeypatch.setattr(fleet_sync, 'inspect', lambda python: {
        'python': python, 'module': str(clone / 'gpt2agent/__init__.py'),
        'version': fleet_sync.source_version((clone / 'gpt2agent/__init__.py').read_text()),
        'metadata': '0.0.23',
    })
    return args, previous, target


def test_preview_does_not_move_checkout(deployment):
    args, previous, target = deployment
    receipt = {}
    fleet_sync.sync(args, receipt)
    assert receipt['status'] == 'preview'
    assert receipt['target'] == target
    assert git(args.clone, 'rev-parse', 'HEAD') == previous


@pytest.mark.parametrize('unsafe', ['dirty', 'wrong-version', 'wrong-install'])
def test_preflight_refuses_unsafe_deployment(deployment, monkeypatch, unsafe):
    args, previous, _ = deployment
    args.apply = True
    if unsafe == 'dirty':
        (args.clone / 'owner-work').write_text('preserve')
    elif unsafe == 'wrong-version':
        args.version = '9.9.9'
    else:
        monkeypatch.setattr(fleet_sync, 'inspect', lambda _: {'module': '/foreign/gpt2agent.py',
                                                            'python': 'python'})
    with pytest.raises(ValueError):
        fleet_sync.sync(args, {})
    assert git(args.clone, 'rev-parse', 'HEAD') == previous
    if unsafe == 'dirty':
        assert (args.clone / 'owner-work').read_text() == 'preserve'


@pytest.mark.parametrize("stale_metadata", [False, True])
def test_verifier_failure_rolls_back_all_attempted_installs(deployment, monkeypatch, stale_metadata):
    args, previous, _ = deployment
    args.apply = True
    real_run = fleet_sync.run
    installs = []
    if stale_metadata:
        original_inspect = fleet_sync.inspect
        monkeypatch.setattr(fleet_sync, 'inspect', lambda python: {
            **original_inspect(python), 'metadata': '0.0.20',
        })

    def run(*command, **kwargs):
        if command[0] == 'git':
            return real_run(*command, **kwargs)
        if 'pip' in command:
            installs.append((command[0], git(args.clone, 'rev-parse', 'HEAD')))
            return ''
        raise RuntimeError('injected failed installation verification')

    monkeypatch.setattr(fleet_sync, 'run', run)
    receipt = {}
    with pytest.raises(RuntimeError, match='injected'):
        fleet_sync.sync(args, receipt)
    assert git(args.clone, 'rev-parse', 'HEAD') == previous
    assert installs[-2:] == [('python-a', previous), ('python-b', previous)]
    assert receipt['rollback']['status'] == ('failed' if stale_metadata else 'restored')
    if stale_metadata:
        assert 'metadata' in receipt['rollback']['error']
    assert not (args.clone / '.git/fleet-sync.lock').exists()


def test_existing_lock_is_preserved(deployment):
    args, previous, _ = deployment
    args.apply = True
    lock = args.clone / '.git/fleet-sync.lock'
    lock.mkdir()
    with pytest.raises(FileExistsError):
        fleet_sync.sync(args, {})
    assert lock.exists()
    assert git(args.clone, 'rev-parse', 'HEAD') == previous


def test_concurrent_work_is_not_destroyed_by_rollback(deployment, monkeypatch):
    args, _, target = deployment
    args.apply = True
    real_run = fleet_sync.run

    def run(*command, **kwargs):
        if command[0] == 'git':
            return real_run(*command, **kwargs)
        (args.clone / 'new-owner-work').write_text('preserve')
        raise RuntimeError('failure after concurrent edit')

    monkeypatch.setattr(fleet_sync, 'run', run)
    receipt = {}
    with pytest.raises(RuntimeError):
        fleet_sync.sync(args, receipt)
    assert receipt['rollback']['status'] == 'failed'
    assert git(args.clone, 'rev-parse', 'HEAD') == target
    assert (args.clone / 'new-owner-work').read_text() == 'preserve'


def test_wheel_bytes_detect_same_version_modified_install(tmp_path):
    package = tmp_path / 'gpt2agent'
    package.mkdir()
    source = package / '__init__.py'
    source.write_bytes(b'original')
    wheel = tmp_path / 'package.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('gpt2agent/__init__.py', b'original')
    assert verify_files(package, wheel) == 1
    source.write_bytes(b'tampered')
    with pytest.raises(ValueError, match='differs'):
        verify_files(package, wheel)


def test_wheel_empty_package_is_not_verification(tmp_path):
    wheel = tmp_path / 'empty.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('other.txt', b'not the package')
    with pytest.raises(ValueError, match='no gpt2agent'):
        verify_files(tmp_path, wheel)


def test_wheel_verification_rejects_leftover_code_but_allows_python_cache(tmp_path):
    package = tmp_path / 'gpt2agent'
    package.mkdir()
    (package / '__init__.py').write_bytes(b'original')
    cache = package / '__pycache__'
    cache.mkdir()
    (cache / '__init__.cpython-313.pyc').write_bytes(b'generated cache')
    wheel = tmp_path / 'package.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('gpt2agent/__init__.py', b'original')
    assert verify_files(package, wheel) == 1
    (package / 'obsolete_backend.py').write_text('unexpected importable code')
    with pytest.raises(ValueError, match='unexpected.*obsolete_backend'):
        verify_files(package, wheel)


@pytest.mark.parametrize('branch_change', ['stable', 'moved', 'deleted'])
def test_rollback_restores_metadata_when_previous_branch_changes(
    deployment, monkeypatch, branch_change,
):
    args, previous, target = deployment
    args.apply = True
    git(args.clone, 'checkout', '-qb', 'owner-branch', previous)
    versions = dict.fromkeys(args.python, '0.0.23')
    real_run = fleet_sync.run
    original_inspect = fleet_sync.inspect
    monkeypatch.setattr(fleet_sync, 'inspect', lambda python: {
        **original_inspect(python), 'metadata': versions[python],
    })

    def run(*command, **kwargs):
        if command[0] == 'git':
            return real_run(*command, **kwargs)
        if 'pip' in command:
            head = git(args.clone, 'rev-parse', 'HEAD')
            if head == target and command[0] == 'python-b':
                raise RuntimeError('second target install failed')
            versions[command[0]] = '0.0.24' if head == target else '0.0.23'
            if head == target and branch_change == 'moved':
                git(args.clone, 'update-ref', 'refs/heads/owner-branch', target)
            elif head == target and branch_change == 'deleted':
                git(args.clone, 'update-ref', '-d', 'refs/heads/owner-branch')
            return ''
        raise AssertionError(command)

    monkeypatch.setattr(fleet_sync, 'run', run)
    receipt = {}
    with pytest.raises(RuntimeError, match='second target install failed'):
        fleet_sync.sync(args, receipt)
    assert git(args.clone, 'rev-parse', 'HEAD') == previous
    assert versions == dict.fromkeys(args.python, '0.0.23')
    assert receipt['rollback']['status'] == 'restored'
    assert git(args.clone, 'branch', '--show-current') == (
        'owner-branch' if branch_change == 'stable' else ''
    )
    if branch_change == 'moved':
        assert git(args.clone, 'rev-parse', 'owner-branch') == target
    if branch_change != 'stable':
        assert receipt['rollback']['branch'] == 'left detached; previous branch changed'


def test_rollback_never_claims_restored_after_late_same_version_branch_move(
    deployment, monkeypatch,
):
    args, previous, _ = deployment
    args.apply = True
    args.version = '0.0.23'
    git(args.clone, 'config', 'user.name', 'Test')
    git(args.clone, 'config', 'user.email', 'test@example.invalid')
    marker = args.clone / 'gpt2agent/marker.py'
    marker.write_text('candidate = True\n')
    git(args.clone, 'add', '.')
    git(args.clone, 'commit', '-qm', 'same-version candidate')
    target = git(args.clone, 'rev-parse', 'HEAD')
    args.ref = target
    git(args.clone, 'checkout', '-qb', 'owner-branch', previous)
    real_run = fleet_sync.run

    def run(*command, **kwargs):
        if command[0] == 'git':
            if command[-3:] == ('checkout', '--quiet', 'owner-branch'):
                real_run('git', '-C', str(args.clone), 'update-ref',
                         'refs/heads/owner-branch', target)
            return real_run(*command, **kwargs)
        if 'pip' in command:
            return ''
        raise RuntimeError('injected verification failure')

    monkeypatch.setattr(fleet_sync, 'run', run)
    receipt = {}
    with pytest.raises(RuntimeError, match='injected'):
        fleet_sync.sync(args, receipt)
    assert git(args.clone, 'rev-parse', 'owner-branch') == target
    assert receipt['rollback']['status'] == 'failed'
    assert 'checkout changed' in receipt['rollback']['error']
