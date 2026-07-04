#!/usr/bin/env python3
"""Upload the Caltech-101 dataset into the CBIR Engine (demo helper).

This reuses the project's existing Python SDK (`cbir.CBIRClient`) and the API
key you already provisioned with `scripts/provision_tenant.py` — it adds NO new
client, auth flow, or API calls.

Dataset layout expected (the standard Caltech-101 shape):

    101_ObjectCategories/
        accordion/
            image_0001.jpg
            image_0002.jpg
        airplanes/
            ...

The category is inferred from each image's parent folder name, and folders that
are not image classes (e.g. BACKGROUND_Google) are skipped.

Usage:

    # once, so `import cbir` works (or the script adds the SDK to sys.path itself)
    pip install -e sdks/python-sdk

    python scripts/upload_caltech101.py \
        --dataset "C:\\Datasets\\101_ObjectCategories" \
        --api-key cbir_...

    # preview what would be uploaded, without touching the API:
    python scripts/upload_caltech101.py --dataset "C:\\Datasets\\101_ObjectCategories" --dry-run
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# --- make the existing SDK importable without requiring `pip install` ---------
# The SDK lives at <repo>/sdks/python-sdk. If it isn't installed, add it to the
# path so the demo "just works". We reuse this client instead of writing a new one.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SDK_PATH = _REPO_ROOT / "sdks" / "python-sdk"
if _SDK_PATH.exists():
    sys.path.insert(0, str(_SDK_PATH))

try:
    from cbir import CBIRAPIError, CBIRClient
except ImportError:
    sys.exit(
        "Could not import the 'cbir' SDK. Install it once with:\n"
        "    pip install -e sdks/python-sdk\n"
        "(it only needs httpx)."
    )

# Image types the catalog accepts, and folders that are not real classes.
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
IGNORED_FOLDERS = {"BACKGROUND_Google"}

# Statuses that mean the ingestion pipeline has finished with an item.
TERMINAL_STATUSES = {"indexed", "duplicate", "failed"}


def find_images(dataset_dir: Path) -> list[tuple[Path, str]]:
    """Walk the dataset and return (image_path, category) pairs.

    The category is the name of the image's parent folder; non-class folders
    are skipped."""
    items: list[tuple[Path, str]] = []
    for path in sorted(dataset_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        category = path.parent.name
        if category in IGNORED_FOLDERS:
            continue
        items.append((path, category))
    return items


def call_with_backoff(action, *, retries: int = 5):
    """Run an SDK call, pausing and retrying if we hit the per-key rate limit
    (HTTP 429). Any other error is raised to the caller."""
    for attempt in range(retries):
        try:
            return action()
        except CBIRAPIError as exc:
            if exc.status_code == 429 and attempt < retries - 1:
                wait = 2 * (attempt + 1)
                print(f"  rate limited; waiting {wait}s...")
                time.sleep(wait)
                continue
            raise


def wait_until_indexed(
    client: CBIRClient, item_id: str, poll_interval: float, poll_timeout: float
) -> str:
    """Poll the item until the ingestion worker reaches a terminal status
    (indexed / duplicate / failed) or we time out. Returns the final status."""
    deadline = time.time() + poll_timeout
    while time.time() < deadline:
        status = call_with_backoff(lambda: client.get_item(item_id)).status
        if status in TERMINAL_STATUSES:
            return status
        time.sleep(poll_interval)
    return "timeout"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload Caltech-101 into the CBIR Engine."
    )
    parser.add_argument(
        "--dataset", required=True, help="path to the 101_ObjectCategories folder"
    )
    parser.add_argument(
        "--api-key", help="CBIR API key (from scripts/provision_tenant.py)"
    )
    parser.add_argument("--catalog-url", default="http://localhost:8002")
    parser.add_argument("--query-url", default="http://localhost:8004")
    parser.add_argument(
        "--limit", type=int, default=None, help="cap the number of images (demo)"
    )
    parser.add_argument(
        "--poll-interval", type=float, default=1.0, help="seconds between polls"
    )
    parser.add_argument(
        "--poll-timeout", type=float, default=60.0, help="max seconds to index one"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list what would be uploaded, without uploading",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    dataset_dir = Path(args.dataset)
    if not dataset_dir.is_dir():
        sys.exit(f"dataset folder not found: {dataset_dir}")

    images = find_images(dataset_dir)
    if args.limit is not None:
        images = images[: args.limit]
    total = len(images)
    if total == 0:
        sys.exit("no images found (check the dataset path and folder layout)")

    # --- dry run: just show the plan, no API key or stack needed ---
    if args.dry_run:
        categories = sorted({c for _, c in images})
        print(f"Would upload {total} images across {len(categories)} categories.")
        for category in categories:
            count = sum(1 for _, c in images if c == category)
            print(f"  {category}: {count}")
        return

    if not args.api_key:
        sys.exit("--api-key is required (or use --dry-run to preview)")

    client = CBIRClient(
        api_key=args.api_key, catalog_url=args.catalog_url, query_url=args.query_url
    )

    uploaded = 0  # reached "indexed"
    duplicates = 0  # detected as near-duplicates (still a success)
    failed = 0  # errored, timed out, or the worker marked them failed
    start = time.time()

    for index, (image_path, category) in enumerate(images, start=1):
        print(f"Uploading image {index}/{total}")
        print(f"Category: {category}")
        try:
            item = call_with_backoff(
                lambda: client.ingest_image(image_path, metadata={"category": category})
            )
            status = wait_until_indexed(
                client, item.id, args.poll_interval, args.poll_timeout
            )
            if status == "indexed":
                uploaded += 1
            elif status == "duplicate":
                duplicates += 1
                print("  (duplicate - already indexed, skipped)")
            else:
                failed += 1
                print(f"  ! not indexed (status: {status})")
        except Exception as exc:  # noqa: BLE001 — one bad image must not stop the demo
            failed += 1
            print(f"  ! failed: {exc}")

    elapsed = time.time() - start
    print("\n" + "=" * 40)
    print(f"Total uploaded (indexed): {uploaded}")
    if duplicates:
        print(f"Duplicates skipped:       {duplicates}")
    print(f"Failed uploads:           {failed}")
    print(f"Elapsed time:             {elapsed:.1f}s")


if __name__ == "__main__":
    main()
