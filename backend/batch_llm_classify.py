"""Phase B: Batch LLM classification across multiple queue files.

Reads 1+ *_p_llm_queue.json files, classifies pending items with Claude Haiku
using a parallel worker pool (default 10 workers), writes classifications back
to each queue file in-place.

Resumable:
  - Skips items with classification != null
  - Re-running after partial failure processes remaining pending items
  - Incremental save every 10 items to survive crashes

Error handling:
  - API errors: leaves item with classification=null (retry on next run)
  - Parse errors: marks item as PARSE_ERROR (won't retry)

Usage:
    python batch_llm_classify.py --queues form4_index_20251224_p_llm_queue.json
    python batch_llm_classify.py --queues a.json b.json c.json
    python batch_llm_classify.py --date-range 2025-12-24 2025-12-31
    python batch_llm_classify.py --date-range 2025-12-24 2025-12-31 --workers 5
"""

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import anthropic
from dotenv import load_dotenv

sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, ".")

# Reuse prompt from legacy classifier so updates stay DRY
from classify_p_with_prefilter import CLASSIFIER_PROMPT

load_dotenv()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
if not ANTHROPIC_API_KEY:
    print("ERROR: ANTHROPIC_API_KEY not set")
    sys.exit(1)

DEFAULT_WORKERS = 15
SAVE_EVERY = 10  # Flush queue files to disk every N completed items
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 200


def classify_one(client, item: dict) -> dict:
    """Classify a single item via Haiku. Returns classification dict."""
    payload_json = json.dumps(item["payload"], indent=2)
    msg = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": CLASSIFIER_PROMPT + payload_json}],
    )
    text = msg.content[0].text.strip()
    m = re.search(r'\{[^{}]*"classification"[^{}]*\}', text, re.DOTALL)
    if m:
        try:
            parsed = json.loads(m.group(0))
            return {
                "classification": parsed.get("classification", "PARSE_ERROR"),
                "reason": parsed.get("reason", ""),
                "rule_triggered": "LLM",
            }
        except json.JSONDecodeError:
            pass
    return {"classification": "PARSE_ERROR",
            "reason": "Failed to parse LLM JSON",
            "rule_triggered": "LLM"}


def resolve_queue_paths(args) -> list[str]:
    """Resolve queue file paths from --queues or --date-range."""
    if args.queues:
        return args.queues
    if args.date_range:
        start, end = args.date_range
        d = datetime.strptime(start, "%Y-%m-%d")
        end_d = datetime.strptime(end, "%Y-%m-%d")
        paths = []
        while d <= end_d:
            path = f"form4_index_{d.strftime('%Y%m%d')}_p_llm_queue.json"
            if os.path.exists(path):
                paths.append(path)
            d += timedelta(days=1)
        return paths
    return []


def save_queue(path: str, data: dict) -> None:
    """Write queue back to disk, updating pending/completed counters."""
    completed_count = sum(1 for it in data["items"]
                          if it.get("classification") is not None)
    data["completed"] = completed_count
    data["pending"] = len(data["items"]) - completed_count
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queues", nargs="+", help="Queue file paths")
    ap.add_argument("--date-range", nargs=2, metavar=("START", "END"),
                    help="Process all queue files in date range (YYYY-MM-DD)")
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                    help=f"Parallel LLM workers (default: {DEFAULT_WORKERS})")
    args = ap.parse_args()

    queue_paths = resolve_queue_paths(args)
    if not queue_paths:
        print("ERROR: no queue files (use --queues or --date-range)")
        sys.exit(1)

    # Load all queues, collect pending items
    queues = {}  # path -> data
    pending = []  # list of (path, item_idx)
    total_items = 0
    for path in queue_paths:
        with open(path) as f:
            data = json.load(f)
        queues[path] = data
        total_items += len(data["items"])
        for idx, item in enumerate(data["items"]):
            if item.get("classification") is None:
                pending.append((path, idx))

    already_done = total_items - len(pending)
    print(f"Queue files: {len(queue_paths)}")
    print(f"Total items: {total_items}")
    print(f"Already classified: {already_done}")
    print(f"Pending: {len(pending)}")
    print(f"Workers: {args.workers}")

    if not pending:
        print("\nNothing to classify. All items already complete.")
        return

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    start = time.time()
    completed = 0
    counts = {"GENUINE": 0, "NOT_GENUINE": 0, "AMBIGUOUS": 0,
              "PARSE_ERROR": 0, "API_ERROR": 0}
    save_lock = threading.Lock()
    dirty_paths = set()

    def process_one(path_idx):
        path, idx = path_idx
        item = queues[path]["items"][idx]
        try:
            cls = classify_one(client, item)
        except Exception as e:
            # Leave item pending (null) for retry on next run
            return (path, idx, None, str(e)[:120])
        item["classification"] = cls["classification"]
        item["reason"] = cls["reason"]
        item["rule_triggered"] = cls["rule_triggered"]
        item["classified_at"] = datetime.utcnow().isoformat()
        return (path, idx, cls["classification"], None)

    print("\n=== BATCH LLM CLASSIFICATION ===")
    api_errors = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_one, pi): pi for pi in pending}
        for future in as_completed(futures):
            path, idx, cls, err = future.result()
            completed += 1
            if cls:
                counts[cls] = counts.get(cls, 0) + 1
                dirty_paths.add(path)
            elif err:
                api_errors += 1
                counts["API_ERROR"] += 1

            # Incremental save every N items
            if completed % SAVE_EVERY == 0 and dirty_paths:
                with save_lock:
                    for p in list(dirty_paths):
                        save_queue(p, queues[p])
                    dirty_paths.clear()

            # Progress
            if completed % 20 == 0 or completed == len(pending):
                elapsed = round(time.time() - start, 1)
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (len(pending) - completed) / rate if rate > 0 else 0
                print(f"  [{completed}/{len(pending)}] {counts} "
                      f"({elapsed:.0f}s, ~{eta:.0f}s remaining)")

    # Final save
    with save_lock:
        for p in dirty_paths:
            save_queue(p, queues[p])

    elapsed = round(time.time() - start, 1)
    print(f"\n{'=' * 60}")
    print(f"BATCH LLM COMPLETE")
    print(f"  Pending processed: {completed}")
    print(f"  Classifications:   {counts}")
    if api_errors > 0:
        print(f"  ⚠️  API errors:     {api_errors} items left pending (re-run to retry)")
    print(f"  Time:              {elapsed}s ({elapsed/60:.1f} min)")
    print(f"{'=' * 60}")

    # Non-zero exit if any API errors remain
    if api_errors > 0:
        sys.exit(2)


if __name__ == "__main__":
    main()
