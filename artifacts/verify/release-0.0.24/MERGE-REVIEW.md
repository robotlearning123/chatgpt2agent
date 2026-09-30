# PR 87 follow-up review

Runtime pin: `b1d4aed95c78cc0c15962ba0e2e86e712247009b`; previous preparation: `3bd6fd5`.

- Corrected queued light research model routing. Four real registered-tool /
  queue-worker regression cases cover configured and explicit light models and
  unchanged heavy defaults/overrides. Before repair: two light failures and two
  heavy passes. After repair: all four pass.
- Corrected heavy research timeout: initial SSE and polling can each take
  1800 seconds; clients need more than 3600 seconds plus startup overhead.
- Narrowed automatic browser fallback to chat, agent and deep_research; doctor
  reports read-only probes and sentinel status rather than selecting tool lanes.
- Declined the proposed raw child-stderr/argument inclusion in fleet receipts.
  These can contain credential-bearing URLs. Kept bounded exit-code/executable
  diagnostics and documented why; no new logging or subprocess behavior.

Primary full suite: 675 passed, 13 skipped; Ruff, release metadata and diff
checks pass. Simplification: one model argument fix, four regression cases,
documentation corrections; no new abstractions or dependencies.

Independent GPT-6.1 review: PASS; four new queue tests passed and the reviewer
independently reproduced both old light-routing failures with heavy controls
passing. Grok 4.7 independently ran 47 focused tests and found two remaining
README agent-guidance duplicates. Both were fixed in `2b76a1e`; Grok and
GPT-6.1 independently re-read the committed delta against implementation and
returned PASS. Primary agrees after execution and source inspection. No
blocking review finding remains.

New wheel and sdist build and Twine checks pass. All 43 wheel package files
match b1d4aed. Artifact hashes are in VALIDATION.json under post_review_delta.
Existing outsider/install/live receipts and SHA256SUMS remain historical at
d6b9b63; they do not certify this delta's installed-device behavior.
