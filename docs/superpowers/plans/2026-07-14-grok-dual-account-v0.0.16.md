# Grok Dual-Account v0.0.16 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the user's Grok subscription to MCP agents through two explicit, independently authenticated surfaces: the official Grok Build CLI and the private grok.com conversation backend, including resumable Heavy multi-agent runs.

**Architecture:** `GrokBuildClient` owns a bounded official-CLI subprocess and never reads OAuth credentials. `GrokWebAuthStore`, `GrokWebTransport`, and `GrokWebClient` separately own cookie snapshots, browser-compatible HTTP, and allowlisted conversation contracts. Thin MCP modules register provider-prefixed tools; missing Grok auth never prevents the existing ChatGPT server from starting.

**Tech Stack:** Python 3.10+, `asyncio`, `curl_cffi`, MCP Python SDK, pytest/pytest-asyncio, Ruff, the external `grok` and optional `browser-use` CLIs, existing release scripts.

## Global Constraints

- Initial implementation base is the live head of PR #30, `origin/release/v0.0.12-account-design`; at planning time its exact SHA is `0f621d28b834c6165df924fa564c43dcca0bc3d3`.
- Create `.worktrees/gpt2agent-grok-dual-account` on `feat/grok-dual-account-v0.0.16`; never use the dirty prototype worktree or unpublished local `main` as the implementation base.
- Keep the feature PR in draft/do-not-merge state until `v0.0.12` through `v0.0.15` are released and verified.
- Do not bump package version or claim a final tool count on the initial stacked feature branch.
- Reuse only the generic bounded-process behavior from the old prototype; do not inherit its one-turn, no-tools, no-web, no-subagents, or automatic-session-deletion product boundary.
- No new Python dependency. `browser-use` remains an optional external executable discovered with `shutil.which`.
- Build and website credentials, readiness, quotas, errors, caches, and status remain separate. There is no cross-lane fallback.
- Build child environments remove `XAI_API_KEY` and `GROK_CODE_XAI_API_KEY`; the CLI remains the only reader/refresher of Build OAuth state.
- Website cookie files use an owner-private parent, mode `0600`, bounded JSON, atomic replacement, mtime/inode-aware reload, and request-local cookie snapshots.
- Website tools never accept raw cookies or tokens. Status never returns identity, cookie values, auth paths containing secrets, or refresh credentials.
- Website chat defaults to temporary/private. `use_memory=True` requires `temporary=False`. Heavy dispatch is never retried after an ambiguous transport failure.
- Build roots and upload roots default to disabled. Every `cwd` or upload path must remain beneath an explicitly configured root after symlink-safe resolution.
- Build `plan` uses `--permission-mode plan --sandbox read-only`; explicit `apply` uses `--permission-mode bypassPermissions --sandbox strict`. Official child-network blocking for `read-only`/`strict` is Linux-only, so macOS documentation must not claim the same network boundary.
- Build sessions remain in official CLI history; v0.0.16 exposes no Build resume/delete MCP tool and stores no transcript copy.
- Live website routes are private and drift-prone. Capture only sanitized route/schema evidence, fail closed as `GROK_WEB_CONTRACT_CHANGED`, and never describe them as an official xAI API.
- Normal CI skips all account-bearing live tests. Heavy live validation is quota-bearing and requires an explicit opt-in flag.
- Preserve all existing ChatGPT behavior, annotations, resources, release governance, and safe MCP error serialization.

---

## File Structure

### New runtime files

- `gpt2agent/_bounded_process.py` — provider-neutral bounded subprocess and process-tree cleanup.
- `gpt2agent/grok_errors.py` — exact public Grok error codes, bounded route normalization, and content-free exceptions.
- `gpt2agent/grok_paths.py` — configured-root validation for Build directories and upload files.
- `gpt2agent/grok_build.py` — Build configuration, CLI discovery, catalog/status, agent argv, and JSON projection.
- `gpt2agent/grok_web_auth.py` — private cookie schema, reload fingerprint, generation snapshots, and status.
- `gpt2agent/grok_web_transport.py` — request-local cookies, Chrome impersonation, bounded bodies, redirects/proxy/CA controls, and HTTP classification.
- `gpt2agent/grok_web_contracts.py` — model/mode, conversation, citation, tool, trace, history, and deletion allowlists.
- `gpt2agent/grok_web.py` — ordinary chat, continuation, Heavy dispatch/reconnect, discovery, and history operations.
- `gpt2agent/grok_upload.py` — upload policy, descriptor-safe file reads, and auth-generation-scoped attachment registry.
- `gpt2agent/grok_setup.py` — Build probe plus browser-assisted or hidden-manual website cookie import.
- `gpt2agent/tools/grok_build.py` — three Build MCP handlers.
- `gpt2agent/tools/grok_web.py` — nine website MCP handlers.

### New evidence and tests

- `docs/protocol/grok-web-contract-v1.md` — dated, non-secret route and minimum-schema evidence.
- `tests/fixtures/grok_web_models.json`
- `tests/fixtures/grok_web_modes.json`
- `tests/fixtures/grok_web_chat_complete.json`
- `tests/fixtures/grok_web_heavy_in_progress.json`
- `tests/fixtures/grok_web_heavy_complete.json`
- `tests/fixtures/grok_web_conversations.json`
- `tests/fixtures/grok_web_conversation_detail.json`
- `tests/test_bounded_process.py`
- `tests/test_grok_errors.py`
- `tests/test_grok_paths.py`
- `tests/test_grok_build.py`
- `tests/test_grok_build_tools.py`
- `tests/test_grok_build_live.py`
- `tests/test_grok_web_auth.py`
- `tests/test_grok_setup.py`
- `tests/test_grok_web_transport.py`
- `tests/test_grok_web_models.py`
- `tests/test_grok_web_chat.py`
- `tests/test_grok_web_heavy.py`
- `tests/test_grok_web_history.py`
- `tests/test_grok_upload.py`
- `tests/test_grok_web_tools.py`
- `tests/test_grok_web_integration.py`
- `tests/test_grok_web_live.py`

### Existing integration surfaces

- `gpt2agent/_secure_file.py`, `gpt2agent/_log_redact.py`, `gpt2agent/tools/_redact.py`, `gpt2agent/tools/_errors.py`
- `gpt2agent/server.py`, `gpt2agent/tools/__init__.py`, `gpt2agent/tool_contracts.py`, `gpt2agent/tool_manifest.py`
- `gpt2agent/resources/feature-coverage.v1.json`, `gpt2agent/resources.py`
- `README.md`, `SECURITY.md`, `config.example.toml`, `CHANGELOG.md`, `docs/`, `gpt2agent/skills/gpt2agent/`
- `pyproject.toml`, `gpt2agent/__init__.py`, `server.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
- `scripts/package_smoke.sh`, `scripts/verify_release.py`, and their focused tests

---

### Task 1: Create the collision-free implementation worktree

**Files:**
- Read: approved spec and this plan
- No source changes

**Interfaces:**
- Consumes: live GitHub PR #30 head and current worktree registry
- Produces: clean worktree at the exact recorded base SHA

- [ ] **Step 1: Recheck parallel lanes and base truth**

Set the workspace root to the local checkout and run from its nested repository:

```bash
WORKSPACE_ROOT=/absolute/path/to/47-chatgpt2agent
cd "$WORKSPACE_ROOT/gpt2agent"
git worktree list --porcelain
gh pr list --state open --json number,title,headRefName,baseRefName,url
gh pr view 30 --json headRefName,headRefOid,baseRefName,state,url
git fetch origin release/v0.0.12-account-design
git rev-parse origin/release/v0.0.12-account-design
```

Expected: PR #30 is still the account-abstraction dependency; the remote ref and `headRefOid` match. If they differ from the planning SHA, use the new matching SHA and record it in the first feature commit message.

- [ ] **Step 2: Create the worktree with the worktree skill**

Invoke `superpowers:using-git-worktrees`, then run its approved creation flow for:

```text
path:   "$WORKSPACE_ROOT/.worktrees/gpt2agent-grok-dual-account"
branch: feat/grok-dual-account-v0.0.16
base:   origin/release/v0.0.12-account-design at the verified PR #30 SHA
```

Expected: the new path and branch did not exist before creation; the worktree is clean; `git merge-base HEAD origin/release/v0.0.12-account-design` equals `HEAD`.

- [ ] **Step 3: Run the base smoke tests before changing code**

Run:

```bash
python -m pytest -q tests/test_tool_contracts.py tests/test_backend_contracts.py tests/test_secure_local_writes.py
python -m ruff check gpt2agent tests
```

Expected: all selected tests and Ruff pass. Preserve exact counts in the execution log.

---

### Task 2: Establish Grok error, redaction, and private-read boundaries

**Files:**
- Create: `gpt2agent/grok_errors.py`
- Modify: `gpt2agent/_secure_file.py`
- Modify: `gpt2agent/_log_redact.py`
- Modify: `gpt2agent/tools/_redact.py`
- Modify: `gpt2agent/tools/_errors.py`
- Test: `tests/test_grok_errors.py`
- Test: `tests/test_secure_local_writes.py`
- Test: `tests/test_secret_redaction.py`

**Interfaces:**
- Produces: `GrokError`, `normalize_grok_route()`, and `read_private_json()` for every later task

- [ ] **Step 1: Write failing safe-error tests**

Add tests with planted secrets and opaque IDs:

```python
from gpt2agent.grok_errors import GrokError, normalize_grok_route
from gpt2agent.tools._errors import serialize_tool_error


def test_grok_routes_remove_conversation_and_response_ids() -> None:
    assert normalize_grok_route(
        "/rest/app-chat/conversations/conv-private-42"
    ) == "/rest/app-chat/conversations/{id}"
    assert normalize_grok_route(
        "/rest/app-chat/conversations/reconnect-response-v2/resp-private-99"
    ) == "/rest/app-chat/conversations/reconnect-response-v2/{id}"


def test_grok_error_is_typed_bounded_and_secret_free() -> None:
    error = GrokError(
        "GROK_WEB_AUTH_EXPIRED",
        method="POST",
        route="/rest/app-chat/conversations/conv-private-42?token=secret",
        status_code=401,
        retryable=False,
    )
    rendered = serialize_tool_error(error)
    assert rendered == (
        "GROK_WEB_AUTH_EXPIRED: POST "
        "/rest/app-chat/conversations/{id} failed (401)"
    )
    assert "secret" not in rendered
    assert "conv-private-42" not in rendered
```

Extend redaction cases so `sso=`, `sso-rw=`, `cf_clearance=`, `grok_device_id=`, `Cookie:`, `Set-Cookie:`, `xai-...`, signed query credentials, email, and identity/account IDs never survive errors or logs. UUID-like values in untrusted error text and normalized routes are removed, but UUID syntax is not globally erased from successful structured payloads. Add paired tests proving validated `conversation_id`, `response_id`, and `attachment_id` fields survive normal result serialization while the same planted values in free-form exception text, headers, identity fields, or routes do not.

- [ ] **Step 2: Run the focused tests and verify red**

Run:

```bash
python -m pytest -q tests/test_grok_errors.py tests/test_secret_redaction.py
```

Expected: collection or assertions fail because the Grok error type and Grok cookie redaction do not exist.

- [ ] **Step 3: Implement the closed error contract**

Define these exact public codes in `gpt2agent/grok_errors.py`:

```python
GROK_ERROR_CODES = frozenset(
    {
        "GROK_BUILD_CLI_NOT_FOUND",
        "GROK_BUILD_AUTH_MISSING",
        "GROK_BUILD_QUOTA",
        "GROK_BUILD_TIMEOUT",
        "GROK_BUILD_OUTPUT_TOO_LARGE",
        "GROK_BUILD_FAILED",
        "GROK_WEB_AUTH_MISSING",
        "GROK_WEB_AUTH_EXPIRED",
        "GROK_WEB_RATE_LIMITED",
        "GROK_WEB_CONTRACT_CHANGED",
        "GROK_WEB_TIMEOUT",
        "GROK_WEB_OUTPUT_TOO_LARGE",
        "GROK_UPLOAD_BLOCKED",
        "GROK_WEB_FAILED",
    }
)


class GrokError(RuntimeError):
    code: str
    method: str | None
    route: str | None
    status_code: int | None
    retryable: bool
    retry_after: float | None
```

The constructor must accept only a member of `GROK_ERROR_CODES`, uppercase/bound the method, normalize the route, clamp retry timing to 60 seconds, and construct its message only from code, method, normalized route, status, and retry metadata. It must not accept an arbitrary upstream message.

- [ ] **Step 4: Add fail-closed private JSON reads**

Add this exact interface to `_secure_file.py`:

```python
def read_private_json(
    path: Path,
    *,
    maximum_bytes: int = 131_072,
) -> Any:
    """Read bounded JSON only from a current-user regular 0600 file."""
```

Open with `O_RDONLY | O_CLOEXEC | O_NOFOLLOW` where available; compare `lstat` with `fstat`; require a regular file, current ownership, mode with no group/world bits on POSIX, positive bounded size, exact bounded read, UTF-8, and JSON decoding. Every failure message contains only the configured path and a fixed invariant, never file content.

- [ ] **Step 5: Permit only typed Grok errors through the MCP boundary**

Update `serialize_tool_error()` so `GrokError` returns its already-safe string and every unexpected Grok exception still collapses to the existing generic safe failure. Extend both redactors before truncation, not after.

- [ ] **Step 6: Run tests and commit**

Run:

```bash
python -m pytest -q tests/test_grok_errors.py tests/test_secure_local_writes.py tests/test_secret_redaction.py tests/test_security_hardening.py
python -m ruff check gpt2agent/grok_errors.py gpt2agent/_secure_file.py gpt2agent/_log_redact.py gpt2agent/tools/_redact.py gpt2agent/tools/_errors.py tests/test_grok_errors.py
git diff --check
```

Expected: all pass and no planted secret appears. Commit:

```bash
git add gpt2agent/grok_errors.py gpt2agent/_secure_file.py gpt2agent/_log_redact.py gpt2agent/tools/_redact.py gpt2agent/tools/_errors.py tests/test_grok_errors.py tests/test_secure_local_writes.py tests/test_secret_redaction.py tests/test_security_hardening.py
git commit -m "feat: add secret-safe Grok error boundaries"
```

---

### Task 3: Extract the provider-neutral bounded process primitive

**Files:**
- Create: `gpt2agent/_bounded_process.py`
- Create: `tests/test_bounded_process.py`

**Interfaces:**
- Produces: `BoundedProcessError`, `ProcessResult`, and `run_bounded_process()` consumed by Build and setup

- [ ] **Step 1: Port the focused process tests before production code**

Move the nine audited behaviors from the prototype into provider-neutral tests: separate stream capture, disconnected stdin, live output cap, bounded timeout, SIGTERM-resistant grandchild cleanup, live-producer cleanup, caller-cancellation cleanup, concurrent stdout/stderr draining, and independent stderr cap.

Use this public test contract:

```python
result = await run_bounded_process(
    [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr)"],
    cwd=tmp_path,
    env=os.environ.copy(),
    timeout_seconds=5.0,
    max_output_bytes=1024,
)
assert result == ProcessResult(0, b"out\n", b"err\n")
```

For cap and timeout cases assert `BoundedProcessError.code` is respectively
`output_too_large` and `timeout`; do not retain process output in the exception.
Provider clients map these internal categories onto their public typed errors.

- [ ] **Step 2: Run tests and verify red**

Run:

```bash
python -m pytest -q tests/test_bounded_process.py
```

Expected: import failure because `_bounded_process.py` does not exist.

- [ ] **Step 3: Implement the complete runner**

Expose exactly:

```python
class BoundedProcessError(RuntimeError):
    def __init__(self, code: Literal["timeout", "output_too_large"]) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes


async def run_bounded_process(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    timeout_seconds: float,
    max_output_bytes: int,
) -> ProcessResult:
    """Run one argv without a shell and own its complete process tree."""
```

Retain `start_new_session=True` plus TERM/KILL group cleanup on POSIX and suspended-process plus kill-on-close Job Object on Windows. Drain both pipes concurrently, disconnect stdin, cancel/drain tasks on timeout, output overflow, and caller cancellation, and remove no external files.

- [ ] **Step 4: Verify and commit**

Run:

```bash
python -m pytest -q tests/test_bounded_process.py
python -m ruff check gpt2agent/_bounded_process.py tests/test_bounded_process.py
git diff --check
```

Expected: all pass. Commit:

```bash
git add gpt2agent/_bounded_process.py tests/test_bounded_process.py
git commit -m "feat: add bounded subprocess primitive"
```

---

### Task 4: Implement configured-root policy and the Grok Build client

**Files:**
- Create: `gpt2agent/grok_paths.py`
- Create: `gpt2agent/grok_build.py`
- Create: `tests/test_grok_paths.py`
- Create: `tests/test_grok_build.py`

**Interfaces:**
- Consumes: `run_bounded_process()`, `BoundedProcessError`, `GrokError`
- Produces: `GrokBuildConfig`, `GrokBuildClient.models()`, `.status()`, and `.agent()`

- [ ] **Step 1: Write failing root and argv tests**

Cover disabled roots, contained directories, missing/non-directory paths, `..`, parent/leaf symlink escapes, command PATH resolution, explicit executable paths, disappearance races, prompt byte bounds, catalog validation, and exact environment filtering.

Assert the two mode mappings exactly:

```python
assert plan_argv[plan_argv.index("--permission-mode") + 1] == "plan"
assert plan_argv[plan_argv.index("--sandbox") + 1] == "read-only"
assert apply_argv[apply_argv.index("--permission-mode") + 1] == "bypassPermissions"
assert apply_argv[apply_argv.index("--sandbox") + 1] == "strict"
assert "--no-subagents" in plan_argv
assert "--no-subagents" not in subagent_argv
assert "XAI_API_KEY" not in recorded_env
assert "GROK_CODE_XAI_API_KEY" not in recorded_env
```

The prompt must occur as exactly one argv element; no shell is used. `cwd=None` resolves to the process working directory only if it is beneath a configured Build root.

- [ ] **Step 2: Run tests and verify red**

Run:

```bash
python -m pytest -q tests/test_grok_paths.py tests/test_grok_build.py
```

Expected: import failures for the new modules.

- [ ] **Step 3: Implement exact Build data contracts**

Define:

```python
_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


class RootPolicy:
    def __init__(self, roots: Sequence[Path]) -> None:
        self.roots = tuple(path.expanduser().resolve() for path in roots)

    def directory(self, value: str | Path | None) -> Path:
        """Return one existing directory contained by a configured root."""


@dataclass(frozen=True)
class GrokBuildConfig:
    command: str
    home: Path | None
    auth_path: Path | None
    roots: tuple[Path, ...]
    default_model: str | None
    timeout_seconds: float
    max_output_bytes: int
    default_max_turns: int

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None) -> "GrokBuildConfig":
        data = dict(values or {})
        command = str(data.get("command", "grok")).strip()
        if not command:
            raise InputValidationError("grok_build.command must not be empty")
        raw_roots = data.get("roots", [])
        if not isinstance(raw_roots, list) or not all(
            isinstance(value, str) and value.strip() for value in raw_roots
        ):
            raise InputValidationError("grok_build.roots must be a string list")
        roots = tuple(Path(value).expanduser().resolve() for value in raw_roots)
        home_value = data.get("home")
        auth_value = data.get("auth_path")
        model_value = data.get("default_model")
        default_model = str(model_value).strip() if model_value else None
        if default_model is not None and not _MODEL_ID_RE.fullmatch(default_model):
            raise InputValidationError("grok_build.default_model is invalid")
        timeout_seconds = float(data.get("timeout_seconds", 120.0))
        max_output_bytes = int(data.get("max_output_bytes", 1_048_576))
        default_max_turns = int(data.get("default_max_turns", 20))
        if not 1.0 <= timeout_seconds <= 600.0:
            raise InputValidationError("grok_build.timeout_seconds must be 1..600")
        if not 1_024 <= max_output_bytes <= 16_777_216:
            raise InputValidationError("grok_build.max_output_bytes is out of range")
        if not 1 <= default_max_turns <= 100:
            raise InputValidationError("grok_build.default_max_turns must be 1..100")
        return cls(
            command=command,
            home=Path(str(home_value)).expanduser().resolve() if home_value else None,
            auth_path=Path(str(auth_value)).expanduser().resolve() if auth_value else None,
            roots=roots,
            default_model=default_model,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
            default_max_turns=default_max_turns,
        )


@dataclass(frozen=True)
class GrokBuildModelCatalog:
    authenticated: bool
    default_model: str | None
    models: tuple[str, ...]


@dataclass(frozen=True)
class GrokBuildResult:
    surface: str
    status: str
    session_id: str | None
    model: str
    text: str
    stop_reason: str | None
    usage: dict[str, int] | None
    changed_files: tuple[str, ...]
```

`from_mapping()` must additionally reject booleans/non-finite numeric values before
numeric conversion. `RootPolicy.directory()` returns a canonical contained
directory or raises the existing `InputValidationError` with a fixed invariant;
`GROK_UPLOAD_BLOCKED` is reserved for the upload surface.

- [ ] **Step 4: Implement CLI parsing and client methods**

Expose:

```python
class GrokBuildClient:
    def __init__(
        self,
        config: GrokBuildConfig,
        *,
        runner: Runner = run_bounded_process,
        resolver: Resolver = shutil.which,
        cwd_policy: RootPolicy | None = None,
    ) -> None:
        self.config = config
        self._runner = runner
        self._resolver = resolver
        self._cwd_policy = cwd_policy or RootPolicy(config.roots)

    async def models(self) -> dict[str, Any]:
        """Return authenticated/default_model/models/count from `grok models`."""

    async def status(self) -> dict[str, Any]:
        """Return installed/version/authenticated/catalog counts without identity."""

    async def agent(
        self,
        prompt: str,
        *,
        cwd: str | None = None,
        mode: Literal["plan", "apply"] = "plan",
        model: str | None = None,
        max_turns: int | None = None,
        subagents: bool = False,
    ) -> dict[str, Any]:
        """Run one bounded official Build headless agent session."""
```

Use `grok --no-auto-update --cwd <validated> -p <prompt> --output-format json --max-turns <n> --no-memory`, add the selected model only after catalog validation, and apply the exact mode/subagent flags asserted above. Parse only `text`, `stopReason`, `sessionId`, bounded integer usage keys, and bounded root-relative changed paths. Missing optional fields become `None` or an empty tuple. Do not return request IDs, arbitrary metadata, stderr, credentials, identity, or prompt text.

Map missing binary, unauthenticated output, quota markers, timeout, output cap, nonzero exit, malformed UTF-8/JSON, and empty text onto the closed `GROK_BUILD_*` contract. `status()` alone returns an installed/authenticated false record for a missing binary; action calls raise.

- [ ] **Step 5: Verify against current CLI drift and commit**

Run:

```bash
python -m pytest -q tests/test_grok_paths.py tests/test_grok_build.py tests/test_bounded_process.py
python -m ruff check gpt2agent/grok_paths.py gpt2agent/grok_build.py tests/test_grok_paths.py tests/test_grok_build.py
grok --no-auto-update --version
grok --no-auto-update models
git diff --check
```

Expected: unit tests pass; the live read-only probes parse the current contract without pinning version `0.2.99` or `0.2.101`. Commit:

```bash
git add gpt2agent/grok_paths.py gpt2agent/grok_build.py tests/test_grok_paths.py tests/test_grok_build.py
git commit -m "feat: add bounded Grok Build client"
```

---

### Task 5: Implement website auth storage and `grok-setup`

**Files:**
- Create: `gpt2agent/grok_web_auth.py`
- Create: `gpt2agent/grok_setup.py`
- Modify: `gpt2agent/server.py`
- Test: `tests/test_grok_web_auth.py`
- Test: `tests/test_grok_setup.py`
- Test: `tests/test_secure_local_writes.py`

**Interfaces:**
- Consumes: `read_private_json()`, `write_private_json()`, `run_bounded_process()`
- Produces: `GrokWebAuthStore.snapshot()`, `.status()`, and CLI command `gpt2agent grok-setup`

- [ ] **Step 1: Write failing cookie-schema and reload tests**

Use only planted fixture secrets. Require schema version `1`, both `sso` and `sso-rw`, allow optional `grok_device_id` and `cf_clearance`, domain `grok.com` or `.grok.com`, path `/`, bounded values, secure metadata, unexpired cookies, private file mode, and no duplicate names. A stored `browser_impersonation` must be one supported enumerated curl-cffi profile, never a raw User-Agent string. Retain `cf_clearance` only when browser setup proves the source Chrome major is compatible with that profile; otherwise omit the optional cookie.

Assert the snapshot contract:

```python
snapshot = store.snapshot()
assert snapshot.generation == 0
assert set(snapshot.cookies) == {"sso", "sso-rw"}

replacement = original_payload | {
    "cookies": [cookie | {"value": "rotated-secret"} for cookie in original_payload["cookies"]]
}
write_private_json(auth_path, replacement)
next_snapshot = store.snapshot()
assert next_snapshot.generation == 1
assert next_snapshot.cookies["sso"] == "rotated-secret"
assert snapshot.cookies["sso"] == "first-secret"
```

Also replace the file while preserving mtime; inode/device/size/mtime-ns fingerprinting must still reload it.

- [ ] **Step 2: Write failing setup runner tests**

Inject a fake runner and assert exact owned-session argv order:

```python
assert calls[0] == [
    "browser-use", "--headed", "--profile", "Default",
    "--session", owned_session, "--json", "open", "https://grok.com/",
]
assert calls[1] == [
    "browser-use", "--profile", "Default", "--session", owned_session,
    "--json", "cookies", "get", "--url", "https://grok.com/",
]
assert calls[-1] == [
    "browser-use", "--profile", "Default", "--session", owned_session, "close",
]
```

Test `finally` closure on open failure, cookie parse failure, and write failure; never use `cookies export` or `close --all`. Hidden manual fallback uses injected `getpass.getpass` and prints no input. Capture `navigator.userAgent` only in process memory, reduce it to a supported enumerated impersonation profile, and test that an incompatible or unparseable browser identity causes `cf_clearance` to be discarded rather than guessed.

Add failure-isolation tests for the aggregate setup receipt: Build probe failure must not prevent website import and validation; website import failure must not erase a successful Build probe. Both lanes are always attempted, and the returned bounded receipt reports separate `build` and `web` status/code objects without exception text, credentials, identity, or cookie values.

- [ ] **Step 3: Run tests and verify red**

Run:

```bash
python -m pytest -q tests/test_grok_web_auth.py tests/test_grok_setup.py
```

Expected: imports fail.

- [ ] **Step 4: Implement auth store and setup schema**

Define:

```python
@dataclass(frozen=True)
class GrokWebAuthSnapshot:
    generation: int
    cookies: Mapping[str, str]
    browser_impersonation: str


class GrokWebAuthStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path.home() / ".gpt2agent" / "grok-web-auth.json"

    @property
    def auth_generation(self) -> int:
        return self.snapshot().generation

    def snapshot(self) -> GrokWebAuthSnapshot:
        """Return immutable cookies plus one validated impersonation profile."""

    def status(self) -> dict[str, Any]:
        """Return configured/authenticated/expires_at/cookie_names only."""
```

Write the stored document as:

```json
{
  "schema_version": 1,
  "source": "browser-use",
  "browser_impersonation": "chrome131",
  "cookies": [
    {
      "name": "sso",
      "domain": ".grok.com",
      "path": "/",
      "expires": 1800000000,
      "secure": true,
      "http_only": true,
      "value": "PLANTED_TEST_SECRET"
    }
  ]
}
```

Production docs and committed fixtures must use planted placeholders only. Status may return the allowlisted cookie names but never values or identity.

- [ ] **Step 5: Add the CLI parser branch**

Add:

```text
gpt2agent grok-setup
gpt2agent grok-setup --refresh
gpt2agent grok-setup --chrome-profile Default
gpt2agent grok-setup --manual
```

`run_grok_setup()` attempts two independent operations: the read-only Build version/models probes and website cookie import/validation. Each lane catches only its own typed failures, the second lane still runs if the first fails, and the command returns an aggregate bounded receipt with separate `build` and `web` results. It exits success only when both requested lanes succeed; partial success is preserved and clearly reported without secret-bearing exception text. Browser-assisted mode discovers `browser-use` with `shutil.which`, parses at most 128 KiB of cookie JSON in memory, captures the User-Agent only in memory to choose a compatible enumerated impersonation, filters before persistence, closes its unique session, writes atomically, and immediately validates through `GrokWebAuthStore.status()`. `--manual` and automatic browser-unavailable fallback use hidden input; manual setup omits `cf_clearance` unless a compatible profile was independently established.

- [ ] **Step 6: Verify and commit**

Run:

```bash
python -m pytest -q tests/test_grok_web_auth.py tests/test_grok_setup.py tests/test_secure_local_writes.py tests/test_install.py
python -m ruff check gpt2agent/grok_web_auth.py gpt2agent/grok_setup.py gpt2agent/server.py tests/test_grok_web_auth.py tests/test_grok_setup.py
python -m gpt2agent grok-setup --help
git diff --check
```

Expected: tests pass; help exits zero without reading auth or starting a browser. Commit:

```bash
git add gpt2agent/grok_web_auth.py gpt2agent/grok_setup.py gpt2agent/server.py tests/test_grok_web_auth.py tests/test_grok_setup.py tests/test_secure_local_writes.py
git commit -m "feat: add secure Grok website setup"
```

---

### Task 6: Capture the missing website protocol and implement bounded transport

**Files:**
- Create: `docs/protocol/grok-web-contract-v1.md`
- Create: `gpt2agent/grok_web_transport.py`
- Create: sanitized `tests/fixtures/grok_web_*.json` listed above
- Test: `tests/test_grok_web_transport.py`

**Interfaces:**
- Consumes: `GrokWebAuthSnapshot`, `RequestPolicy`, account TLS policy
- Produces: `GrokWebTransport.request()` and a reviewed, value-free protocol table

- [ ] **Step 1: Capture only missing live contract evidence**

Use an owned browser session and the already-approved account. Inspect, without printing cookie/header/body values, the exact methods/routes and minimum response fields for:

```text
auth probe, models, modes, new ordinary chat, continuation,
Heavy dispatch, reconnect v1/v2, list, get, delete, upload
```

One minimal private ordinary prompt and one minimal private Heavy prompt may be used because these are the release's explicit opt-in gates. Record conversation/response IDs only in process memory, delete any persisted conversation through the observed exact route, and close only the owned browser session.

Write `docs/protocol/grok-web-contract-v1.md` with date, method, normalized route template, request field names/types, response field names/types, terminal/in-progress markers, and evidence class. Store sanitized fixtures whose content values are synthetic (`conv_test_1`, `resp_test_1`, `https://example.com/source`); never copy a live body.

- [ ] **Step 2: Write failing transport tests from the sanitized fixtures**

Assert request-local cookie use, stable Origin/Referer/locale, snapshot-selected allowlisted impersonation, direct certifi CA, `trust_env=False`, libcurl proxy disabled, redirects disabled, `SSLKEYLOGFILE` rejection, 4 MiB JSON/SSE caps, and a separate Grok `RequestPolicy` instance. Every request sets `discard_cookies=True`; response `Set-Cookie` data is ignored and cannot mutate state. Add concurrent requests from two planted auth generations and prove neither cookies nor impersonation cross between them.

Map statuses exactly:

```python
expected = {
    401: "GROK_WEB_AUTH_EXPIRED",
    403: "GROK_WEB_AUTH_EXPIRED",
    429: "GROK_WEB_RATE_LIMITED",
    500: "GROK_WEB_FAILED",
}
```

404/405 on a captured route, unexpected HTML/Cloudflare content, malformed JSON/SSE, blank required response, redirect, and missing minimum fields become `GROK_WEB_CONTRACT_CHANGED`. Network timeout becomes `GROK_WEB_TIMEOUT`; native/body overflow becomes `GROK_WEB_OUTPUT_TOO_LARGE`.

- [ ] **Step 3: Run tests and verify red**

Run:

```bash
python -m pytest -q tests/test_grok_web_transport.py
```

Expected: import failure.

- [ ] **Step 4: Implement the injectable transport**

Define:

```python
class GrokWebTransport(Protocol):
    async def request(
        self,
        method: str,
        route: str,
        *,
        cookies: Mapping[str, str],
        browser_impersonation: str,
        json_body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        upload: "ValidatedUpload | None" = None,
        timeout_seconds: float = 20.0,
    ) -> Any:
        """Return one bounded decoded response or raise a typed GrokError."""
```

Implement `CurlGrokWebTransport` with a request-scoped curl-cffi session created and closed inside each synchronous worker call. Pass a copied cookie mapping and the allowlisted snapshot impersonation per request, set `discard_cookies=True`, and never retain a cookie jar or store a `Cookie` header. Use `asyncio.to_thread` around the synchronous curl call, bounded callbacks before retention, `allow_redirects=False`, and a transport-owned request policy/cooldown namespace. Tests inject a response with `Set-Cookie` and then inspect the next request plus concurrent cross-generation calls to prove no shared mutable cookie state exists.

- [ ] **Step 5: Verify and commit**

Run:

```bash
python -m pytest -q tests/test_grok_web_transport.py tests/test_backend_contracts.py tests/test_request_policy.py
python -m ruff check gpt2agent/grok_web_transport.py tests/test_grok_web_transport.py
git diff --check
```

Expected: all pass; a scan of fixtures and protocol docs finds none of `sso=`, `sso-rw=`, `cf_clearance=`, live account IDs, email, or signed URLs. Commit:

```bash
git add docs/protocol/grok-web-contract-v1.md gpt2agent/grok_web_transport.py tests/fixtures/grok_web_*.json tests/test_grok_web_transport.py
git commit -m "feat: add bounded Grok website transport"
```

---

### Task 7: Implement website model/mode discovery and status

**Files:**
- Create: `gpt2agent/grok_web_contracts.py`
- Create: `gpt2agent/grok_web.py`
- Test: `tests/test_grok_web_models.py`

**Interfaces:**
- Consumes: `GrokWebAuthStore.snapshot()`, `GrokWebTransport.request()`
- Produces: `GrokWebModelCatalog.models()`, `.validate_mode()`, `GrokWebClient.status()`

- [ ] **Step 1: Write failing model/mode normalizer tests**

Load the sanitized `/rest/models` and `/rest/modes` fixtures. Require bounded lists and allowlist only model ID, display label after redaction, mode ID, mode enum, tags, availability, and default markers. Assert the current four account-visible public modes by semantic name, not by hard-coded model selection:

```python
catalog = normalize_grok_catalog(models_fixture, modes_fixture)
assert set(catalog["modes"]) == {"auto", "fast", "expert", "heavy"}
assert catalog["modes"]["heavy"]["mode_enum"] == "MODEL_MODE_HEAVY"
assert catalog["modes"]["heavy"]["available"] is True
assert catalog["modes"]["heavy"]["model"] == "grok-4-heavy"
```

Also test duplicate IDs, overlong lists/strings, unknown shapes, unavailable Heavy, missing mode mapping, and identity/secret-looking labels. Contract drift must fail closed.

- [ ] **Step 2: Write generation-cache race tests**

Mirror the existing `ModelCatalog` invariant: a slow response under cookie generation `0` may satisfy its original caller but cannot overwrite or clear generation `1`. `force=True` bypasses TTL; default TTL is 60 seconds. A validation miss forces one refresh before rejecting a mode.

- [ ] **Step 3: Run tests and verify red**

Run:

```bash
python -m pytest -q tests/test_grok_web_models.py
```

Expected: imports or assertions fail.

- [ ] **Step 4: Implement catalog and status contracts**

Define:

```python
@dataclass(frozen=True)
class GrokWebMode:
    name: Literal["auto", "fast", "expert", "heavy"]
    mode_id: str
    mode_enum: str
    model: str
    tags: tuple[str, ...]
    available: bool
    is_default: bool


class GrokWebModelCatalog:
    def __init__(
        self,
        auth_store: GrokWebAuthStore,
        transport: GrokWebTransport,
        *,
        ttl: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._auth_store = auth_store
        self._transport = transport
        self._ttl = ttl
        self._clock = clock

    async def models(self, *, force: bool = False) -> dict[str, Any]:
        """Return generation-bound sanitized model and mode metadata."""

    async def validate_mode(self, mode: str, *, heavy: bool) -> GrokWebMode:
        """Return a live available mode, refreshing once on a miss."""


class GrokWebClient:
    def __init__(
        self,
        auth_store: GrokWebAuthStore,
        transport: GrokWebTransport,
        *,
        catalog: GrokWebModelCatalog | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._auth_store = auth_store
        self._transport = transport
        self._catalog = catalog or GrokWebModelCatalog(auth_store, transport)
        self._clock = clock
        self._sleep = sleep

    async def status(self) -> dict[str, Any]:
        """Return configured/authenticated/contract_ready and capabilities."""
```

Every catalog/client operation obtains exactly one auth snapshot and passes both `snapshot.cookies` and `snapshot.browser_impersonation` to every transport call derived from that operation. It never combines cookies from one generation with browser identity from another.

`status()` must not throw for missing/expired auth. Return independent booleans and a fixed code:

```json
{
  "surface": "web",
  "configured": true,
  "authenticated": true,
  "contract_ready": true,
  "auth_generation": 2,
  "modes": ["auto", "fast", "expert", "heavy"],
  "capabilities": {
    "chat": true,
    "heavy": true,
    "web_search": true,
    "x_search": true,
    "attachments": true,
    "history": true
  },
  "error_code": null
}
```

Do not return identity, plan name, quota guesses, cookie values, or raw response metadata.

- [ ] **Step 5: Verify and commit**

Run:

```bash
python -m pytest -q tests/test_grok_web_models.py tests/test_model_catalog.py
python -m ruff check gpt2agent/grok_web_contracts.py gpt2agent/grok_web.py tests/test_grok_web_models.py
git diff --check
```

Expected: all pass. Commit:

```bash
git add gpt2agent/grok_web_contracts.py gpt2agent/grok_web.py tests/test_grok_web_models.py
git commit -m "feat: add Grok website discovery and status"
```

---

### Task 8: Implement ordinary chat, continuation, citations, and history

**Files:**
- Modify: `gpt2agent/grok_web_contracts.py`
- Modify: `gpt2agent/grok_web.py`
- Create: `tests/test_grok_web_chat.py`
- Create: `tests/test_grok_web_history.py`

**Interfaces:**
- Produces: `GrokWebClient.chat()`, `.list_conversations()`, `.get_conversation()`, `.delete_conversation()`

- [ ] **Step 1: Write failing public-input and exact-request tests**

Cover prompt UTF-8 bytes `1..65536`, `mode` in `auto/fast/expert`, search in `off/web/web+x`, at most 20 attachment IDs, bounded conversation ID, and the memory/persistence rule. Heavy passed to ordinary chat must raise a fixed invalid-input instruction to use `grok_heavy`.

For every mode/search/persistence combination, compare the full request dictionary with the sanitized protocol document. The test must assert explicit values for the captured fields, including model/mode, `temporary`, `disableSearch`, X/web tool controls, attachments, memory controls, and async flag. Unknown defaulted website fields must not be invented.

Continuation must call only the captured continuation route with the supplied conversation ID and must never call the new-conversation route.

- [ ] **Step 2: Write failing stable-result projection tests**

Assert the exact ordinary result:

```python
assert result == {
    "surface": "web",
    "status": "complete",
    "conversation_id": "conv_test_1",
    "response_id": "resp_test_1",
    "model": "grok-4",
    "mode": "expert",
    "temporary": True,
    "text": "Synthetic answer",
    "citations": [
        {"title": "Example", "url": "https://example.com/source"}
    ],
    "search_results": [],
    "tool_results": [],
    "agents": [],
    "warning": None,
}
```

Citation URLs allow only public absolute HTTP(S), reject userinfo/IP/internal hosts/fragments, remove tracking and credential-bearing query fields, and never return a signed asset URL. Titles/text/tool summaries are redacted before truncation. Unknown server keys are ignored.

- [ ] **Step 3: Write failing history/delete tests**

Use the captured fixtures to require bounded sanitized summaries, exact requested/returned ID matching, active message chain only, allowlisted text/citations/tool/agent summaries, and deterministic ordering. Delete calls the exact route once and returns:

```python
{
    "surface": "web",
    "status": "deleted",
    "conversation_id": "conv_test_1",
    "deleted": True,
}
```

404 on delete is not silently converted into success. No history operation returns cookie state, identity, hidden system prompts, raw tool payloads, signed URLs, or unknown server fields.

- [ ] **Step 4: Run tests and verify red**

Run:

```bash
python -m pytest -q tests/test_grok_web_chat.py tests/test_grok_web_history.py
```

Expected: missing methods or assertions fail.

- [ ] **Step 5: Implement the ordinary client surface**

Add:

```python
async def chat(
    self,
    prompt: str,
    *,
    mode: Literal["auto", "fast", "expert"] = "auto",
    conversation_id: str | None = None,
    temporary: bool = True,
    search: Literal["off", "web", "web+x"] = "web+x",
    attachment_ids: Sequence[str] = (),
    use_memory: bool = False,
) -> dict[str, Any]:
    """Dispatch or continue one ordinary website conversation."""


async def list_conversations(self, limit: int = 20) -> list[dict[str, Any]]:
    """Return at most 100 sanitized website summaries."""


async def get_conversation(self, conversation_id: str) -> dict[str, Any]:
    """Return one sanitized active website conversation chain."""


async def delete_conversation(self, conversation_id: str) -> dict[str, Any]:
    """Delete exactly one website conversation and return a receipt."""
```

Take a new cookie snapshot for each top-level operation. Validate the live catalog before request construction. Complete only on the captured terminal marker plus required IDs/text; HTTP success or quiet transport alone is insufficient.

- [ ] **Step 6: Verify and commit**

Run:

```bash
python -m pytest -q tests/test_grok_web_chat.py tests/test_grok_web_history.py tests/test_grok_web_models.py tests/test_secret_redaction.py
python -m ruff check gpt2agent/grok_web.py gpt2agent/grok_web_contracts.py tests/test_grok_web_chat.py tests/test_grok_web_history.py
git diff --check
```

Expected: all pass. Commit:

```bash
git add gpt2agent/grok_web.py gpt2agent/grok_web_contracts.py tests/test_grok_web_chat.py tests/test_grok_web_history.py
git commit -m "feat: add Grok website conversations"
```

---

### Task 9: Implement Heavy dispatch and exact response reconnect

**Files:**
- Modify: `gpt2agent/grok_web_contracts.py`
- Modify: `gpt2agent/grok_web.py`
- Create: `tests/test_grok_web_heavy.py`

**Interfaces:**
- Produces: `GrokWebClient.heavy()` and `.heavy_result()` with the same stable result schema

- [ ] **Step 1: Write the non-duplication tests first**

Use a scripted fake transport and assert:

```python
receipt = await client.heavy("Synthetic prompt", wait_seconds=1)
assert receipt["status"] == "in_progress"
assert receipt["conversation_id"] == "conv_test_heavy"
assert receipt["response_id"] == "resp_test_heavy"
assert transport.count("POST", new_conversation_route) == 1

complete = await client.heavy_result("resp_test_heavy", wait_seconds=10)
assert complete["status"] == "complete"
assert transport.count("POST", new_conversation_route) == 1
assert transport.reconnect_ids == ["resp_test_heavy", "resp_test_heavy"]
```

Add timeout, cancellation, rate limit, malformed partial, terminal failure, late completion, and unknown status cases. `heavy_result()` must have no code path that references the new-conversation route. An ambiguous Heavy dispatch network failure raises and is never retried.

- [ ] **Step 2: Write Heavy evidence and result-shape tests**

Require live-catalog Heavy selection, asynchronous request fields, `wait_seconds` in `0..600`, bounded progress, exact IDs, and at least one allowlisted agent or trace item before a live gate can claim multi-agent parity. `status="in_progress"` is a successful receipt and includes:

```python
{
    "surface": "web",
    "status": "in_progress",
    "conversation_id": "conv_test_heavy",
    "response_id": "resp_test_heavy",
    "model": "grok-4-heavy",
    "mode": "heavy",
    "temporary": True,
    "text": "",
    "citations": [],
    "search_results": [],
    "tool_results": [],
    "agents": [{"name": "expert-1", "status": "running"}],
    "progress": [{"kind": "agent", "status": "running"}],
    "warning": "Call grok_heavy_result with response_id=resp_test_heavy",
}
```

The `warning` is constructed from the validated response ID, not copied from upstream.

- [ ] **Step 3: Run tests and verify red**

Run:

```bash
python -m pytest -q tests/test_grok_web_heavy.py
```

Expected: missing methods or assertions fail.

- [ ] **Step 4: Implement structurally separate dispatch and reconnect paths**

Add:

```python
async def heavy(
    self,
    prompt: str,
    *,
    temporary: bool = True,
    search: Literal["off", "web", "web+x"] = "web+x",
    attachment_ids: Sequence[str] = (),
    use_memory: bool = False,
    wait_seconds: int = 600,
) -> dict[str, Any]:
    """Dispatch Heavy exactly once, then reconnect by its returned response ID."""


async def heavy_result(
    self,
    response_id: str,
    *,
    wait_seconds: int = 600,
) -> dict[str, Any]:
    """Reconnect to one existing Heavy response without dispatch capability."""
```

Implement private `_dispatch_heavy()` and `_reconnect_heavy()` methods. Only `_dispatch_heavy()` may access the new route. `_reconnect_heavy()` selects the captured v2 route when supported and falls back to v1 only on an explicitly captured compatibility marker, never on timeout/429/5xx/ambiguous failure. Poll until terminal marker or monotonic deadline; do not infer completion from partial text.

- [ ] **Step 5: Verify and commit**

Run:

```bash
python -m pytest -q tests/test_grok_web_heavy.py tests/test_grok_web_chat.py tests/test_grok_web_transport.py
python -m ruff check gpt2agent/grok_web.py gpt2agent/grok_web_contracts.py tests/test_grok_web_heavy.py
git diff --check
```

Expected: all pass and the fake transport proves one paid dispatch. Commit:

```bash
git add gpt2agent/grok_web.py gpt2agent/grok_web_contracts.py tests/test_grok_web_heavy.py
git commit -m "feat: add resumable Grok Heavy mode"
```

---

### Task 10: Implement root-contained uploads and attachment provenance

**Files:**
- Create: `gpt2agent/grok_upload.py`
- Modify: `gpt2agent/grok_web.py`
- Test: `tests/test_grok_upload.py`

**Interfaces:**
- Consumes: `RootPolicy`, `GrokWebTransport`, auth generation
- Produces: `GrokUploadPolicy`, `AttachmentRegistry`, `GrokWebClient.upload_file()`

- [ ] **Step 1: Write failing path and descriptor-race tests**

Cover disabled roots, outside roots, `..`, symlinked parents/leaves, FIFO/socket/device/directory, extension/MIME rejection, empty and oversized files, replacement between validation/open, and descriptor metadata mismatch. Use `O_NOFOLLOW` plus `fstat`; read at most configured maximum plus one byte.

Default allowlist:

```python
DEFAULT_UPLOAD_TYPES = frozenset(
    {
        "text/plain",
        "text/markdown",
        "application/pdf",
        "application/json",
        "text/csv",
        "image/png",
        "image/jpeg",
        "image/webp",
    }
)
DEFAULT_UPLOAD_MAX_BYTES = 25 * 1024 * 1024
```

Configuration may lower the maximum or narrow the allowlist; it cannot exceed 25 MiB or add an unrecognized type in v0.0.16.

- [ ] **Step 2: Write failing attachment-registry tests**

An uploaded ID is accepted only when issued by this process under the current cookie generation. Registry maximum is 256 entries; evict oldest first; reject unknown, duplicate, overlong, cross-generation, and post-restart IDs before chat dispatch.

```python
registry.record(auth_generation=3, attachment_id="att_test_1")
assert registry.validate_many(3, ["att_test_1"]) == ("att_test_1",)
with pytest.raises(GrokError) as caught:
    registry.validate_many(4, ["att_test_1"])
assert caught.value.code == "GROK_UPLOAD_BLOCKED"
```

Construct one client with injected policy and registry, upload through that client, then pass the returned ID through its ordinary chat and Heavy request builders. Assert all three touch the same registry instance. A second client, even with the same auth snapshot, must reject the first client's ID as post-restart/process-local state.

- [ ] **Step 3: Run tests and verify red**

Run:

```bash
python -m pytest -q tests/test_grok_upload.py
```

Expected: import failure.

- [ ] **Step 4: Implement upload and stable receipt**

Define:

```python
@dataclass(frozen=True)
class ValidatedUpload:
    fd: int
    name: str
    media_type: str
    size: int


class GrokUploadPolicy:
    def __init__(
        self,
        roots: Sequence[Path],
        *,
        maximum_bytes: int = DEFAULT_UPLOAD_MAX_BYTES,
        allowed_types: AbstractSet[str] = DEFAULT_UPLOAD_TYPES,
    ) -> None:
        self._roots = RootPolicy(roots)
        self._maximum_bytes = maximum_bytes
        self._allowed_types = frozenset(allowed_types)

    def open(self, path: str) -> ValidatedUpload:
        """Open one root-contained regular file and return descriptor metadata."""


class AttachmentRegistry:
    def record(self, auth_generation: int, attachment_id: str) -> None:
        """Remember one sanitized server-issued ID for the current process."""

    def validate_many(
        self, auth_generation: int, attachment_ids: Sequence[str]
    ) -> tuple[str, ...]:
        """Return unique current-generation IDs or fail closed."""


class GrokWebClient:
    def __init__(
        self,
        auth_store: GrokWebAuthStore,
        transport: GrokWebTransport,
        *,
        catalog: GrokWebModelCatalog | None = None,
        upload_policy: GrokUploadPolicy | None = None,
        attachment_registry: AttachmentRegistry | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Own the upload policy and the process-local attachment registry."""

    async def upload_file(self, path: str) -> dict[str, Any]:
        """Upload one policy-approved file and record its issued attachment ID."""
```

Task 10 extends the Task 7 constructor with these two upload arguments. A missing policy becomes a disabled `GrokUploadPolicy(())`; a missing registry creates one client-owned `AttachmentRegistry`. The same owned registry is used by `upload_file()`, ordinary `chat()`, and `heavy()`—never a per-call or server-global substitute.

`upload_file()` owns/always closes the descriptor, calls the captured upload route, rejects redirects/signed credential output, exact-matches the response metadata, records the ID, and returns only:

```python
{
    "surface": "web",
    "status": "uploaded",
    "attachment_id": "att_test_1",
    "name": "notes.txt",
    "media_type": "text/plain",
    "size": 12,
}
```

- [ ] **Step 5: Wire attachment validation into chat and Heavy**

Before request construction, call `validate_many()` using the auth snapshot generation. Document that restart/auth rotation requires re-upload. Chat never accepts a filesystem path.

- [ ] **Step 6: Verify and commit**

Run:

```bash
python -m pytest -q tests/test_grok_upload.py tests/test_grok_web_chat.py tests/test_grok_web_heavy.py
python -m ruff check gpt2agent/grok_upload.py gpt2agent/grok_web.py tests/test_grok_upload.py
git diff --check
```

Expected: all pass. Commit:

```bash
git add gpt2agent/grok_upload.py gpt2agent/grok_web.py tests/test_grok_upload.py tests/test_grok_web_chat.py tests/test_grok_web_heavy.py
git commit -m "feat: add root-contained Grok uploads"
```

---

### Task 11: Register the explicit Build and website MCP surfaces

**Files:**
- Create: `gpt2agent/tools/grok_build.py`
- Create: `gpt2agent/tools/grok_web.py`
- Modify: `gpt2agent/tools/__init__.py`
- Modify: `gpt2agent/server.py`
- Modify: `gpt2agent/tool_contracts.py`
- Modify: `gpt2agent/tool_manifest.py`
- Modify: `gpt2agent/resources.py`
- Modify: `gpt2agent/resources/feature-coverage.v1.json`
- Create: `tests/test_grok_build_tools.py`
- Create: `tests/test_grok_web_tools.py`
- Modify: `tests/test_tool_contracts.py`
- Modify: `tests/test_resources.py`
- Modify: `tests/test_audit_2026_07_09_tools.py`

**Interfaces:**
- Consumes: both clients and all stable public method contracts
- Produces: 12 provider-prefixed MCP tools without changing existing ChatGPT names

- [ ] **Step 1: Write failing exact-registry tests**

Add these names and annotations:

```python
GROK_ANNOTATIONS = {
    "grok_build_agent": (False, True, False, True),
    "grok_build_models": (True, False, True, False),
    "grok_build_status": (True, False, True, False),
    "grok_chat": (False, False, False, True),
    "grok_heavy": (False, False, False, True),
    "grok_heavy_result": (True, False, True, True),
    "grok_upload_file": (False, False, False, True),
    "grok_list_conversations": (True, False, True, False),
    "grok_get_conversation": (True, False, True, False),
    "grok_delete_conversation": (False, True, True, True),
    "grok_web_models": (True, False, True, False),
    "grok_web_status": (True, False, True, False),
}
```

Registry tests must assert all four hints, exact names, no raw auth parameters, and the public signatures from the spec. Server construction with no Grok binary/cookie file must still register every status/action tool without probing or failing startup.

- [ ] **Step 2: Write failing thin-handler tests**

Fake clients record one call per handler. Validate public inputs before dispatch and exact return passthrough. `grok_build_agent(mode="apply")` remains annotated destructive because annotations cannot vary per invocation. Website deletion is the only destructive website history operation.

- [ ] **Step 3: Run tests and verify red**

Run:

```bash
python -m pytest -q tests/test_grok_build_tools.py tests/test_grok_web_tools.py tests/test_tool_contracts.py tests/test_resources.py
```

Expected: registry mismatch and missing modules.

- [ ] **Step 4: Implement provider manifests and resource separation**

Change `tool_manifest.py` to expose:

```python
TOOL_NAMES: tuple[str, ...] = tuple(TOOL_ANNOTATION_MANIFEST)
GROK_TOOL_NAMES: tuple[str, ...] = tuple(
    name for name in TOOL_NAMES if name.startswith("grok_")
)
CHATGPT_TOOL_NAMES: tuple[str, ...] = tuple(
    name for name in TOOL_NAMES if not name.startswith("grok_")
)
```

Keep `chatgpt://feature-coverage` provider-specific by comparing its `tools` array to `CHATGPT_TOOL_NAMES`, not the global manifest. Do not insert Grok names into a `chatgpt://` resource.

- [ ] **Step 5: Implement lazy client construction and tool registration**

`build_server()` constructs `GrokBuildClient`, `GrokWebAuthStore`, `CurlGrokWebTransport`, one `GrokUploadPolicy`, one `AttachmentRegistry`, and `GrokWebClient` from `cfg.get("grok_build", {})`, `cfg.get("grok_web", {})`, and `cfg.get("grok_upload", {})`. Pass the policy and registry explicitly into `GrokWebClient`; the client owns and uses that same registry for upload, ordinary chat, and Heavy validation. Constructors perform no account I/O. Add optional injected client parameters to `register_all()` so tests can replace them without patching credentials.

Tool modules contain only MCP decorators, bounded argument checks, and one client call. No token, HTTP, subprocess, parser, or response-normalization logic belongs in them.

- [ ] **Step 6: Verify and commit**

Run:

```bash
python -m pytest -q tests/test_grok_build_tools.py tests/test_grok_web_tools.py tests/test_tool_contracts.py tests/test_resources.py tests/test_audit_2026_07_09_tools.py tests/test_tools.py
python -m ruff check gpt2agent/tools gpt2agent/server.py gpt2agent/tool_contracts.py gpt2agent/tool_manifest.py gpt2agent/resources.py tests/test_grok_build_tools.py tests/test_grok_web_tools.py tests/test_tool_contracts.py
git diff --check
```

Expected: all pass. Commit:

```bash
git add gpt2agent/tools/grok_build.py gpt2agent/tools/grok_web.py gpt2agent/tools/__init__.py gpt2agent/server.py gpt2agent/tool_contracts.py gpt2agent/tool_manifest.py gpt2agent/resources.py gpt2agent/resources/feature-coverage.v1.json tests/test_grok_build_tools.py tests/test_grok_web_tools.py tests/test_tool_contracts.py tests/test_resources.py tests/test_audit_2026_07_09_tools.py
git commit -m "feat: expose dual Grok MCP surfaces"
```

---

### Task 12: Add count-independent configuration, docs, security, and bundled guidance

**Files:**
- Modify: `config.example.toml`
- Modify: `README.md`
- Modify: `SECURITY.md`
- Modify: `docs/README.md`
- Modify: `docs/configuration.md`
- Modify: `docs/how-it-works.md`
- Modify: `docs/quickstart.md`
- Modify: `docs/troubleshooting.md`
- Modify: `docs/faq.md`
- Modify: `gpt2agent/skills/gpt2agent/SKILL.md`
- Modify: `gpt2agent/skills/gpt2agent/tools-reference.md`
- Modify: `scripts/package_smoke.sh`
- Modify: `gpt2agent/install.py`
- Modify: `tests/test_package_resources.py`
- Modify: `tests/test_release_metadata.py`
- Modify: `tests/test_install.py`
- Modify: `tests/test_resources.py`

**Interfaces:**
- Produces: truthful operator setup and packaged agent guidance while release count/version remain deferred

- [ ] **Step 1: Add configuration examples with disabled roots**

Document this shape, using placeholders rather than host paths:

```toml
[grok_build]
command = "grok"
# home = "~/.grok"
# auth_path = "~/.grok/auth.json"
roots = []
timeout_seconds = 120
max_output_bytes = 1048576
default_max_turns = 20

[grok_web]
auth_path = "~/.gpt2agent/grok-web-auth.json"
timeout_seconds = 20
max_output_bytes = 4194304

[grok_upload]
roots = []
max_bytes = 26214400
types = ["text/plain", "text/markdown", "application/pdf", "application/json", "text/csv", "image/png", "image/jpeg", "image/webp"]
```

State that Build and upload actions remain disabled until roots are explicitly configured.

- [ ] **Step 2: Replace fragile global tool-count claims**

During the stacked feature phase, replace hard-coded `32` runtime/package assertions with manifest consistency and provider-specific subset checks. Use prose such as “all registered tools” rather than temporarily claiming `44`, because v0.0.13-v0.0.15 can add tools before the final v0.0.16 rebase.

Update `scripts/package_smoke.sh` to assert uniqueness, non-empty ChatGPT/Grok provider subsets, and exact installed/source manifest equality instead of a numeric literal.

- [ ] **Step 3: Document feature and security boundaries**

README/quickstart must show `gpt2agent grok-setup`, independent `grok_build_status` and `grok_web_status`, `grok_chat`, `grok_heavy` plus `grok_heavy_result`, and explicit Build apply mode. Security docs must state: private unsupported website contract, cookie sensitivity, local stdio only, request-local cookies, no cross-lane fallback, root constraints, Heavy quota/no ambiguous retry, session retention in the official CLI, and website cleanup behavior.

Troubleshooting must map every `GROK_BUILD_*`, `GROK_WEB_*`, and `GROK_UPLOAD_BLOCKED` code to a bounded operator action. Do not suggest pasting secrets into shell arguments, logs, issues, or MCP calls.

- [ ] **Step 4: Update bundled skill/tool reference**

Teach agents explicit routing:

```text
Use grok_build_agent for repository coding work.
Use grok_chat for ordinary current-information conversation.
Use grok_heavy for a new Team-of-Experts run.
Use grok_heavy_result only with the exact response_id from an in-progress receipt.
Never call grok_heavy again to poll an existing response.
Upload with grok_upload_file first; pass only issued attachment_ids to chat.
```

Keep Imagine/video/voice/connectors/projects explicitly out of the Grok v0.0.16 scope.

- [ ] **Step 5: Verify docs/package surfaces and commit**

Run:

```bash
rg -n "32 MCP tools|len\(TOOL_NAMES\) == 32" README.md docs gpt2agent scripts tests server.json .claude-plugin
python -m pytest -q tests/test_package_resources.py tests/test_release_metadata.py tests/test_install.py tests/test_resources.py
python -m ruff check gpt2agent tests
git diff --check
```

Expected: no active hard-coded pre-Grok global count remains outside historical changelog/migration text; tests pass; no version field changed. Commit:

```bash
git add config.example.toml README.md SECURITY.md docs/README.md docs/configuration.md docs/how-it-works.md docs/quickstart.md docs/troubleshooting.md docs/faq.md gpt2agent/skills/gpt2agent/SKILL.md gpt2agent/skills/gpt2agent/tools-reference.md scripts/package_smoke.sh gpt2agent/install.py tests/test_package_resources.py tests/test_release_metadata.py tests/test_install.py tests/test_resources.py
git commit -m "docs: document Grok dual-account operation"
```

---

### Task 13: Add local integration and opt-in live gates

**Files:**
- Create: `tests/test_grok_build_live.py`
- Create: `tests/test_grok_web_live.py`
- Create: `tests/test_grok_web_integration.py`
- Create: `scripts/verify_grok_live_receipt.py`
- Test: `tests/test_grok_live_receipt.py`

**Interfaces:**
- Produces: separate sanitized Build/web/Heavy evidence without changing the closed ChatGPT release receipt

- [ ] **Step 1: Add an end-to-end fake transport integration test**

Serve the captured protocol from an injectable local fake transport. In one test: status, model discovery, ordinary new chat, continuation, upload issuance, attachment chat, Heavy dispatch, in-progress receipt, exact reconnect, completion, history get/list, and delete. Assert the fake saw exactly one Heavy new-dispatch request and no raw secret/identity in outputs.

- [ ] **Step 2: Add the Build live gate**

Skip unless `RUN_GROK_BUILD_LIVE=1`. Require explicit `GROK_HOME` and optional `GROK_AUTH_PATH`, configured Build root, OAuth-only selection, version/models probes, exact sentinel, bounded completion, retained owned session ID, and no credential reads/prints.

Run command:

```bash
RUN_GROK_BUILD_LIVE=1 GROK_HOME=/absolute/reviewed/profile python -m pytest -q tests/test_grok_build_live.py
```

- [ ] **Step 3: Add separate ordinary and Heavy website live gates**

Skip all website live tests unless `RUN_GROK_WEB_LIVE=1`. Ordinary gate: private Auto and Expert exact sentinels plus one bounded search proving citation/search metadata; delete any persisted object. Heavy additionally requires `RUN_GROK_HEAVY_LIVE=1`, one minimal private prompt, observable agent/trace evidence, exact response-ID reconnect, terminal completion, and one dispatch count.

Heavy run command:

```bash
RUN_GROK_WEB_LIVE=1 RUN_GROK_HEAVY_LIVE=1 python -m pytest -q tests/test_grok_web_live.py -k heavy
```

- [ ] **Step 4: Create a closed sanitized receipt verifier**

Use a separate schema so `scripts/run_account_release.sh` and `verify_account_receipt.py` remain ChatGPT-only. Permit only:

```json
{
  "schema_version": "1",
  "candidate_commit": "40_HEX",
  "observed_at": "RFC3339_UTC",
  "build": {"version": "STRING", "models_count": 2, "sentinel": true, "session_id_present": true},
  "web": {"auto": true, "expert": true, "search_metadata": true, "cleanup": true},
  "heavy": {"model_mode": "MODEL_MODE_HEAVY", "agent_trace": true, "dispatch_count": 1, "reconnect": true, "complete": true}
}
```

Verifier rejects extra keys, identity, paths, prompt/result text, IDs, tokens, cookies, headers, signed URLs, and stale/future timestamps.

- [ ] **Step 5: Verify and commit**

Run offline by default:

```bash
python -m pytest -q tests/test_grok_web_integration.py tests/test_grok_build_live.py tests/test_grok_web_live.py tests/test_grok_live_receipt.py
python -m ruff check tests/test_grok_web_integration.py tests/test_grok_build_live.py tests/test_grok_web_live.py tests/test_grok_live_receipt.py scripts/verify_grok_live_receipt.py
git diff --check
```

Expected: live tests skip without flags; verifier tests pass. Then run each explicitly approved live gate, save only the sanitized receipt outside the repo in an owner-private directory, and delete any intermediate raw logs. Commit code/tests only:

```bash
git add tests/test_grok_web_integration.py tests/test_grok_build_live.py tests/test_grok_web_live.py tests/test_grok_live_receipt.py scripts/verify_grok_live_receipt.py
git commit -m "test: add opt-in Grok account gates"
```

---

### Task 14: Run full verification, review, and open the draft stacked PR

**Files:**
- Modify only files required by review findings
- No version bump

**Interfaces:**
- Produces: reviewed draft PR against `release/v0.0.12-account-design`

- [ ] **Step 1: Run focused and full offline verification**

Run:

```bash
python -m pytest -q tests/test_bounded_process.py tests/test_grok_errors.py tests/test_grok_paths.py tests/test_grok_build.py tests/test_grok_build_tools.py tests/test_grok_web_auth.py tests/test_grok_setup.py tests/test_grok_web_transport.py tests/test_grok_web_models.py tests/test_grok_web_chat.py tests/test_grok_web_heavy.py tests/test_grok_web_history.py tests/test_grok_upload.py tests/test_grok_web_tools.py tests/test_grok_web_integration.py tests/test_grok_live_receipt.py
python -m pytest -q
python -m ruff check .
python -m compileall -q gpt2agent tests scripts
git diff --check origin/release/v0.0.12-account-design...HEAD
```

Expected: all offline tests pass; only explicit live tests skip; no syntax/lint/diff errors.

- [ ] **Step 2: Build and inspect both distributions without changing version**

Use the repository's existing clean build flow and run:

```bash
python -m build
python -m twine check dist/*
scripts/package_smoke.sh dist 0.0.12 0.0.12
```

Expected: wheel/sdist pass, both include the Grok modules/docs/fixtures required by source tests, setup help works from a clean install, and artifacts are deleted or retained only in the repository's established ignored build location.

- [ ] **Step 3: Run two-stage independent review**

Invoke `superpowers:requesting-code-review`. Require one correctness/contract review and one security review focused on cookie storage, route/ID redaction, root containment, subprocess permissions, Heavy non-duplication, and package/release coupling. Fix findings test-first in narrowly scoped commits and rerun affected plus full gates.

- [ ] **Step 4: Audit the exact feature diff and prototype isolation**

Run:

```bash
git log --oneline --decorate origin/release/v0.0.12-account-design..HEAD
git diff --stat origin/release/v0.0.12-account-design...HEAD
git diff --name-status origin/release/v0.0.12-account-design...HEAD
git status --short --branch
```

Expected: only Grok feature/docs/test work; no version bump; no files copied from the dirty prototype without review; implementation worktree clean. Keep the old prototype untouched until this proof is recorded.

- [ ] **Step 5: Push and open a draft stacked PR**

Push `feat/grok-dual-account-v0.0.16` and open a draft PR with base `release/v0.0.12-account-design`. The body must state:

```text
Draft / do not merge.
Depends on PR #30 and predecessor releases v0.0.12-v0.0.15.
No version bump is included.
Website integration uses a private unsupported grok.com contract.
Heavy live evidence is quota-bearing and stored only as a sanitized local receipt.
Final release target is v0.0.16 after replay onto verified v0.0.15.
```

Record PR URL, head/base SHAs, checks, review state, and exact remaining release blocker.

---

### Task 15: Replay onto verified v0.0.15 and release v0.0.16

**Files:**
- Modify: final conflict resolutions only
- Modify: `pyproject.toml`
- Modify: `gpt2agent/__init__.py`
- Modify: `server.json`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json` when its schema requires the version/count
- Modify: `CHANGELOG.md`
- Create: `docs/migration-0.0.16.md`
- Modify: final count-bearing docs/tests/package gates

**Interfaces:**
- Consumes: exact verified `v0.0.15` tag/merge, Grok-only commit range, green draft PR
- Produces: reviewed merge, annotated `v0.0.16`, PyPI/GitHub release, clean-install receipt

- [ ] **Step 1: Verify all predecessor releases before mutation**

Recheck GitHub/PyPI/tag truth for `v0.0.12` through `v0.0.15`. Require annotated tags, exact release commits, successful release workflows, immutable GitHub releases, published PyPI artifacts, and clean-install version checks. Fetch `origin/main` and require `refs/tags/v0.0.15^{commit}` to be an ancestor of it before choosing `main` as the replacement PR base. Do not use the local v0.0.15 placeholder as proof.

- [ ] **Step 2: Rebuild from the exact verified v0.0.15 state**

Derive and record the original PR #30 base from the reviewed feature branch, create safety refs for both ends of that range, create a new branch/worktree from the exact verified v0.0.15 tag/merge commit, and replay only the recorded Grok commits. Do not merge the divergent release train into the old feature branch.

Run from the canonical nested repository, replacing the worktree path only if live collision checks require another repository-owned path:

```bash
WORKSPACE_ROOT=/absolute/path/to/47-chatgpt2agent
REVIEWED_GROK_HEAD="$(git rev-parse refs/heads/feat/grok-dual-account-v0.0.16^{commit})"
PR30_BASE_SHA="$(git merge-base refs/remotes/origin/release/v0.0.12-account-design "$REVIEWED_GROK_HEAD")"
VERIFIED_V015="$(git rev-parse refs/tags/v0.0.15^{commit})"
git update-ref refs/grok-v016/pr30-base "$PR30_BASE_SHA"
git update-ref refs/grok-v016/reviewed-head "$REVIEWED_GROK_HEAD"
git worktree add -b release/v0.0.16-grok-dual-account "$WORKSPACE_ROOT/.worktrees/gpt2agent-v0.0.16-grok-dual-account" "$VERIFIED_V015"
cd "$WORKSPACE_ROOT/.worktrees/gpt2agent-v0.0.16-grok-dual-account"
mapfile -t GROK_COMMITS < <(git rev-list --reverse --ancestry-path "$PR30_BASE_SHA..$REVIEWED_GROK_HEAD")
test "${#GROK_COMMITS[@]}" -gt 0
git cherry-pick "${GROK_COMMITS[@]}"
git range-diff "$PR30_BASE_SHA..$REVIEWED_GROK_HEAD" "$VERIFIED_V015..HEAD"
git diff --name-status "$VERIFIED_V015...HEAD"
git diff --check "$VERIFIED_V015...HEAD"
```

Expected: feature intent preserved; upstream Voice/Live Voice/Realtime files appear only as baseline or deliberate conflict resolutions. The original stacked PR remains open and unchanged at this stage because GitHub cannot replace its head branch.

- [ ] **Step 3: Compute the final tool manifest and bump coordinated metadata**

Calculate `len(TOOL_NAMES)`, `len(CHATGPT_TOOL_NAMES)`, and `len(GROK_TOOL_NAMES)` from the rebased tree. Update exact count-bearing release prose/tests once. Change all coordinated version fields from `0.0.15` to `0.0.16` in `pyproject.toml`, `gpt2agent/__init__.py`, `server.json` top-level and package entry, plugin metadata, dated changelog, and migration docs.

- [ ] **Step 4: Run final release, package, account, and governance gates**

Run the repository's current `v0.0.15`-derived commands, at minimum:

```bash
python scripts/verify_release.py
python -m pytest -q
python -m ruff check .
python -m compileall -q gpt2agent tests scripts
python -m build
python -m twine check dist/*
scripts/package_smoke.sh dist 0.0.16 0.0.16
```

Run Build/web/Heavy live gates against the exact candidate commit and verify the sanitized Grok receipt. Keep it separate from the closed ChatGPT account receipt unless the then-current release design explicitly revises that contract.

Push `release/v0.0.16-grok-dual-account` without rewriting the old remote head and open a new replacement PR against `main`. Its body links the original stacked draft, records both saved range endpoints, includes the `range-diff` result/receipt, explains that GitHub approvals do not transfer, and requests fresh review. Only after the replacement PR exists, comment its URL on the stacked PR and close the stacked PR as superseded—never force-push it. Require the replacement PR's own GitHub checks, required approval, `mergeable=MERGEABLE`, merge-ready state, governance audit, and no unresolved review threads.

- [ ] **Step 5: Merge, tag, publish, and verify from clean install**

Merge the replacement PR through repository governance. Create annotated `v0.0.16` only from the exact verified merge commit using the repository release tooling; monitor the exact release workflow, GitHub Release, artifact hashes, and PyPI publication. Install `gpt2agent==0.0.16` in a fresh isolated environment and verify:

```text
gpt2agent --version
gpt2agent grok-setup --help
all 12 Grok tool registrations
grok_build_status without credential disclosure
grok_web_status without credential disclosure
```

Run only non-destructive account status probes after clean install. Final handoff must list exact commits, PR, reviews/checks, tag object/commit, release workflow, package URL/hashes, clean-install results, live receipt digest, changed files, and any remaining private-contract drift risk.

---

## Execution Order and Review Gates

Tasks 1-6 establish safety and transport before any website feature call. Tasks 7-10 build independently testable website capabilities. Task 11 is the first global MCP registry change. Task 12 removes count fragility before packaging. Task 13 supplies offline integration and explicit live proof. Task 14 opens a draft feature PR without a release bump. Task 15 is intentionally blocked on real, verified `v0.0.15` release state and must not be simulated with the current placeholder worktree.

Every task ends with a focused commit. A task does not pass merely because its unit tests are green: its public result must remain allowlisted and secret-free, and any live website evidence must be sanitized before it reaches disk.
