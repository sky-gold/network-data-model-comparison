#!/usr/bin/env python3
"""Бенчмарк Q1–Q5: wait → seed → queries → timing → JSON."""

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from db.benchmark import (
    DEFAULT_SCALES,
    dataset_summary_for_scales,
    format_table,
    run_benchmark,
)
from db.config import RESULTS_DIR
from wait_for_db import wait_all


def main() -> None:
    parser = argparse.ArgumentParser(description="Замер времени SQL vs Cypher (мс)")
    parser.add_argument("--player-id", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--scales", choices=["all", "sm", "sml"], default="all")
    parser.add_argument("--no-wait", action="store_true")
    parser.add_argument("--no-verify", action="store_true")
    parser.add_argument("--json-out", type=Path, default=RESULTS_DIR / "benchmark_results.json")
    args = parser.parse_args()

    if args.scales == "sm":
        scales = (DEFAULT_SCALES[0],)
    elif args.scales == "sml":
        scales = DEFAULT_SCALES[:2]
    else:
        scales = DEFAULT_SCALES

    if not args.no_wait:
        print("Ожидание PostgreSQL и Neo4j...", flush=True)
        wait_all()

    print("=== Объёмы данных ===")
    for label, stats in dataset_summary_for_scales(scales):
        print(f"  {label}: {stats}")

    try:
        results = run_benchmark(
            scales=scales,
            player_id=args.player_id,
            repeats=args.repeats,
            warmup=args.warmup,
            verify=not args.no_verify,
        )
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(2)

    table = format_table(results)
    print("\n=== Время выполнения (мс, median) ===")
    print(table)

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "scale_query": r.query,
            "engine": r.engine,
            "median_ms": r.median_ms,
            "min_ms": r.min_ms,
            "max_ms": r.max_ms,
            "rows": r.rows,
        }
        for r in results
    ]
    args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nJSON: {args.json_out}")


if __name__ == "__main__":
    main()
