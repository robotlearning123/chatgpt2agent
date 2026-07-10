<!-- One concern per PR (see CONTRIBUTING.md). Never commit tokens or auth.json. -->

## What & why

What does this change and why?

## Type

- [ ] fix
- [ ] feat
- [ ] docs
- [ ] chore / refactor / test

## Checklist

- [ ] `ruff check gpt2agent tests scripts` is clean
- [ ] `python scripts/verify_release.py` is clean
- [ ] `pytest -q` passes (offline suite; live tests gated by `SKIP_LIVE`)
- [ ] CHANGELOG.md updated (for user-visible changes)
- [ ] No secrets/tokens added; new error/log output is redacted
- [ ] Touches one concern only
