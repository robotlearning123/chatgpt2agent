"""ChatGPT Pro Deep Research runner (calls gpt2agent's ConversationClient directly).

Two modes:
  light  -> conv.deep_research(query)        ~1 min,  citations preserved
  heavy  -> conv.deep_research_heavy(query)  5-30 min, citations LOST due to
            gpt2agent 0.0.1 wrapper bug — reconstructed from progress events

Outputs (in --out-dir):
  report.md   final markdown report
  events.jsonl all raw SSE events
  status.txt  START / DONE / ERROR + elapsed
  meta.json   server metadata (model slug, request id, plan type, ...)

Run with any Python that has gpt2agent installed, e.g.

  python deep_research.py [...]

or via the bundled `run.sh` wrapper, which discovers the right interpreter
from the `gpt2agent` CLI on PATH.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from gpt2agent.backend import BackendClient
from gpt2agent.sse import ConversationClient


def _read_query(arg: str) -> str:
    if arg == "-":
        return sys.stdin.read()
    if arg.startswith("@"):
        return Path(arg[1:]).read_text()
    return arg


async def _run(query: str, mode: str, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    events_path = out_dir / "events.jsonl"
    report_path = out_dir / "report.md"
    status_path = out_dir / "status.txt"
    meta_path = out_dir / "meta.json"

    status_path.write_text(f"START\t{time.strftime('%Y-%m-%d %H:%M:%S')}\tmode={mode}\n")

    backend = BackendClient()
    conv = ConversationClient(backend)
    gen = conv.deep_research_heavy(query) if mode == "heavy" else conv.deep_research(query)

    t0 = time.time()
    n_events = 0
    seen_first_done = False
    light_final_text = ""
    light_refs: list = []
    light_groups: list = []
    progress_before_done: list[str] = []
    progress_after_done: list[str] = []
    tool_calls: list[str] = []
    meta_data: list = []
    tool_error_msg = ""
    connector_failed = False

    with events_path.open("w") as ef:
        try:
            async for ev in gen:
                n_events += 1
                ef.write(json.dumps(ev, default=str) + "\n")
                ef.flush()
                et = ev.get("type")
                if et == "tool":
                    tool_calls.append(ev.get("call", ""))
                elif et == "tool_error":
                    tool_error_msg = ev.get("message", "")
                elif et == "meta":
                    md = ev.get("data") or {}
                    meta_data.append(md)
                elif et == "done":
                    txt = ev.get("text", "") or ""
                    if ev.get("connector_failed"):
                        connector_failed = True
                    # Pick the LONGEST done as the real report. The research model
                    # often emits a short tool-dispatch JSON as the FIRST done
                    # (e.g. {"queries": [...], "source_filter": [...]}); the real
                    # report is a later, longer done. Taking the first done here
                    # silently discarded the actual report (observed 2026-06-03).
                    if not seen_first_done or len(txt) > len(light_final_text):
                        light_final_text = txt
                        light_refs = ev.get("content_references", []) or light_refs
                        light_groups = ev.get("search_result_groups", []) or light_groups
                    seen_first_done = True
                elif et == "progress":
                    txt = ev.get("text", "")
                    (progress_after_done if seen_first_done else progress_before_done).append(txt)
                if n_events % 100 == 0:
                    print(f"[t+{int(time.time() - t0)}s] events={n_events}", flush=True)
        except Exception as exc:
            status_path.write_text(f"ERROR\t{type(exc).__name__}: {exc}\telapsed={time.time() - t0:.0f}s\n")
            print(f"[error] {type(exc).__name__}: {exc}", flush=True)
            return 2

    # --- Build report body ---
    if mode == "heavy":
        body = "".join(progress_after_done)
        if not body and light_final_text:
            body = light_final_text  # Fallback: maybe wrapper actually delivered the real report.
    else:
        body = light_final_text or "".join(progress_before_done + progress_after_done) or "(empty)"

    # --- Sources (light mode only; heavy loses URLs upstream) ---
    sources = ""
    seen: set[str] = set()
    lines: list[str] = []
    for ref in light_refs:
        for item in (ref.get("items") or []):
            url = item.get("url", "")
            title = item.get("title", url)
            if url and url not in seen:
                seen.add(url)
                lines.append(f"- [{title}]({url})")
    if lines:
        sources = "\n\n---\n\n## Sources\n\n" + "\n".join(lines)

    notes_block = ""
    if connector_failed:
        notes_block += "\n\n> **Note:** Deep Research connector reported failure — text may be a fallback answer.\n"
    if tool_error_msg:
        notes_block += f"\n\n> **Tool error:** {tool_error_msg}\n"
    if mode == "heavy" and not lines:
        notes_block += "\n\n> **Citations:** Not recovered (gpt2agent 0.0.1 heavy DR wrapper limitation). To get URLs, open the corresponding chatgpt.com conversation.\n"

    header = (
        f"# Deep Research Report\n\n"
        f"- Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- Mode: `{mode}`\n"
        f"- Elapsed: {time.time() - t0:.0f}s\n"
        f"- Events: {n_events} (tool={len(tool_calls)}, meta={len(meta_data)})\n"
        f"- Tool: `{tool_calls[0][:80] if tool_calls else 'none'}`\n\n"
        f"---\n\n"
    )

    report_path.write_text(header + body + sources + notes_block)
    if meta_data:
        meta_path.write_text(json.dumps(meta_data, indent=2, default=str))

    elapsed = time.time() - t0
    status_path.write_text(
        f"DONE\t{time.strftime('%Y-%m-%d %H:%M:%S')}\tmode={mode}\t"
        f"elapsed={elapsed:.0f}s\tevents={n_events}\t"
        f"body_chars={len(body)}\trefs={len(lines)}\t"
        f"tool_calls={len(tool_calls)}\tconnector_failed={connector_failed}\n"
    )
    print(f"[done] mode={mode} elapsed={elapsed:.0f}s body={len(body)} refs={len(lines)} -> {report_path}", flush=True)
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("query", help="Inline string, '-' for stdin, or '@path' to read from file")
    p.add_argument("--heavy", action="store_true", help="Use deep_research_heavy (5-30 min)")
    p.add_argument("--out-dir", "-o", default=None, help="Output directory")
    args = p.parse_args()

    query = _read_query(args.query)
    if not query.strip():
        print("error: empty query", file=sys.stderr)
        return 1

    mode = "heavy" if args.heavy else "light"
    out_dir = Path(args.out_dir) if args.out_dir else Path(f"research/dr-{time.strftime('%Y%m%d-%H%M')}")
    return asyncio.run(_run(query, mode, out_dir))


if __name__ == "__main__":
    sys.exit(main())
