

import argparse
import importlib.util
import os
import sys
import time
from pathlib import Path
from typing import Callable


# ── Resolve producer directory regardless of CWD ─────────────────────────────
PRODUCERS_DIR = Path(__file__).parent.resolve()


_fastapi_url = os.getenv("FASTAPI_URL", "http://fastapi:8000")
os.environ.setdefault("FASTAPI_URL", _fastapi_url)


def load_producer(filename: str):
    """Dynamically import a producer module from the producers/ directory."""
    path = PRODUCERS_DIR / filename
    spec = importlib.util.spec_from_file_location(
        filename.replace(".py", ""), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_step(name: str, filename: str, dry_run: bool = False) -> bool:
    """Load and execute a producer's main() function. Returns True on success."""
    print(f"\n{'='*60}")
    print(f"  STEP: {name}")
    print(f"  File: {filename}")
    print(f"{'='*60}")

    if dry_run:
        print(f"  [DRY RUN] Skipping execution of {filename}")
        return True

    start = time.perf_counter()
    try:
        module = load_producer(filename)
        module.main()
        elapsed = time.perf_counter() - start
        print(f"\n  ✓ {name} completed in {elapsed:.1f}s")
        return True
    except Exception as exc:
        elapsed = time.perf_counter() - start
        print(f"\n  ✗ {name} FAILED after {elapsed:.1f}s: {exc}",
              file=sys.stderr)
        return False


# ── Pipeline definition ───────────────────────────────────────────────────────
PIPELINE: list[tuple[str, str]] = [
    # (step_key, filename)
    ("routes",        "produce_routes.py"),
    ("operators",     "produce_operators.py"),
    ("stops",         "produce_stops.py"),
    ("vehicles",      "produce_vehicles.py"),
    ("trips",         "produce_trips.py"),        # slow — ~500K records
    ("passengers",    "produce_passengers.py"),
    ("ab_experiment", "produce_ab_experiment.py"),
]


def health_check(base_url: str) -> bool:
    """Ping the FastAPI /health endpoint before starting."""
    import httpx
    url = f"{base_url}/health"
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        print(f"[produce_all] ✓ FastAPI health check passed: {url}")
        return True
    except Exception as exc:
        print(
            f"[produce_all] ✗ FastAPI not reachable at {url}: {exc}", file=sys.stderr)
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Master runner for Davao Jeepney synthetic data producers"
    )
    parser.add_argument(
        "--skip",
        nargs="*",
        metavar="STEP",
        default=[],
        help="Step keys to skip (e.g. --skip trips ab_experiment)",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        metavar="STEP",
        default=None,
        help="Run only these step keys (e.g. --only routes stops)",
    )
    parser.add_argument(
        "--skip-trips",
        action="store_true",
        help="Shortcut: skip the slow trips step",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the pipeline plan without executing any producer",
    )
    parser.add_argument(
        "--no-health-check",
        action="store_true",
        help="Skip the FastAPI /health ping before starting",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("  Davao Jeepney Route Optimization")
    print("  Master Data Producer Runner")
    print(f"  FastAPI: {_fastapi_url}")
    print("=" * 60)

    # Health check
    if not args.dry_run and not args.no_health_check:
        if not health_check(_fastapi_url):
            print(
                "\n[produce_all] Aborting — FastAPI is not available.\n"
                "  Make sure the service is running:\n"
                "    docker-compose up -d fastapi\n"
                "  Or override the URL:\n"
                "    FASTAPI_URL=http://localhost:8000 python producers/produce_all.py",
                file=sys.stderr,
            )
            sys.exit(1)

    # Build skip set
    skip_keys: set[str] = set(args.skip or [])
    if args.skip_trips:
        skip_keys.add("trips")

    # Build run set
    if args.only:
        run_keys = set(args.only)
    else:
        run_keys = {key for key, _ in PIPELINE}

    # Print plan
    print("\n[produce_all] Pipeline plan:")
    for key, filename in PIPELINE:
        will_run = (key in run_keys) and (key not in skip_keys)
        status = "RUN " if will_run else "SKIP"
        print(f"  [{status}] {key:15s} → {filename}")

    if args.dry_run:
        print("\n[produce_all] Dry run complete — no producers executed.")
        return

    # Execute
    wall_start = time.perf_counter()
    results: list[tuple[str, bool]] = []

    for key, filename in PIPELINE:
        will_run = (key in run_keys) and (key not in skip_keys)
        if not will_run:
            continue
        success = run_step(key, filename)
        results.append((key, success))
        if not success:
            print(
                f"\n[produce_all] ✗ Step '{key}' failed — aborting pipeline "
                f"to prevent FK violations downstream.",
                file=sys.stderr,
            )
            break

    # Final report
    wall_elapsed = time.perf_counter() - wall_start
    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE — {wall_elapsed:.1f}s total")
    print(f"{'='*60}")
    passed = [k for k, ok in results if ok]
    failed = [k for k, ok in results if not ok]
    print(f"  Passed : {', '.join(passed) or 'none'}")
    print(f"  Failed : {', '.join(failed) or 'none'}")

    if failed:
        print(
            "\n  Check FastAPI logs:\n"
            "    docker-compose logs fastapi\n"
            "  Check MinIO:\n"
            "    http://localhost:9001  (admin / password123)"
        )
        sys.exit(1)
    else:
        print(
            "\n  All producers succeeded.\n"
            "  Verify Bronze layer:\n"
            "    http://localhost:9001  (admin / password123)\n"
            "    Bucket: raw/jeepney/{entity}/date=YYYY-MM-DD/\n"
            "\n  Next step:\n"
            "    docker-compose run --rm pipeline python /app/ingestion/ingest_to_postgres.py"
        )


if __name__ == "__main__":
    main()
