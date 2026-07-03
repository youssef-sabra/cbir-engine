#!/usr/bin/env python3
"""End-to-end pipeline smoke test (Milestones 2-9), stdlib-only.

Exercises the whole loop against a running Compose stack:

  provision tenant + key (auth) -> register 2 items (catalog) -> upload bytes
  to the signed URLs (object storage) -> confirm (enqueues ingestion) -> the
  ingestion-worker embeds + indexes into Qdrant -> image search returns the
  matching item first (query) -> a duplicate upload is deduplicated ->
  feedback is recorded.

Exits non-zero on the first failed assertion. Used both by CI and locally
(`make smoke` after `docker compose up`). No third-party deps: two tiny PNGs
are embedded below so no image library is needed.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

AUTH = os.environ.get("SMOKE_AUTH_URL", "http://localhost:8001")
CATALOG = os.environ.get("SMOKE_CATALOG_URL", "http://localhost:8002")
QUERY = os.environ.get("SMOKE_QUERY_URL", "http://localhost:8004")
ADMIN_TOKEN = os.environ.get("AUTH_ADMIN_TOKEN", "local-dev-admin-token")

# Two 24x24 PNGs with distinct spatial patterns AND colors ("red left half"
# vs "blue top half"). Structured on purpose: a perceptual (average) hash of a
# SOLID-colour image has no internal variance and collapses to all-zeros, so
# two solid images would collide as duplicates. Real catalog images have
# structure; these fixtures reflect that.
RED_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAIAAABvFaqvAAAAKUlEQVR4nGO8o6HBQAjoPXpEUA0T"
    "QRVEglGDRg0aNWjUoFGDRg0iHwAAtV8DTvb0PyMAAAAASUVORK5CYII="
)
BLUE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAIAAABvFaqvAAAAK0lEQVR4nGPU0LjDQA3ARBVTRg0a"
    "NWjYGsTIxcVFFYMGn9dGDRo1aFAZBAAQswF5BV3SZAAAAABJRU5ErkJggg=="
)

_passed = 0


def check(name: str, cond: bool) -> None:
    global _passed
    if cond:
        _passed += 1
        print(f"PASS: {name}")
    else:
        print(f"FAIL: {name}")
        sys.exit(1)


def _req(method: str, url: str, *, headers=None, data=None, json_body=None, raw=None):
    body = raw
    hdrs = dict(headers or {})
    if json_body is not None:
        body = json.dumps(json_body).encode()
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            payload = resp.read()
            return resp.status, json.loads(payload) if payload else {}
    except urllib.error.HTTPError as exc:
        raw_err = exc.read()
        try:
            return exc.code, json.loads(raw_err)
        except ValueError:
            return exc.code, {"raw": raw_err.decode(errors="replace")}


def _multipart_image(field_files: dict, fields: dict) -> tuple[bytes, str]:
    boundary = "----cbirsmoke"
    parts = []
    for name, value in fields.items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n"
        )
    body = b"".join(p.encode() for p in parts)
    for name, (filename, content) in field_files.items():
        body += (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; "
            f"filename=\"{filename}\"\r\nContent-Type: image/png\r\n\r\n"
        ).encode()
        body += content + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def main() -> None:
    admin = {"X-Admin-Token": ADMIN_TOKEN}

    # --- provision tenant + key ---
    _, tenant = _req("POST", f"{AUTH}/admin/tenants", headers=admin, json_body={"name": f"smoke-{int(time.time())}"})
    status, issued = _req(
        "POST", f"{AUTH}/admin/tenants/{tenant['id']}/api-keys", headers=admin, json_body={"name": "k"}
    )
    api_key = issued["api_key"]
    check("provision tenant + key", status == 201 and api_key.startswith("cbir_"))
    key_headers = {"X-API-Key": api_key}

    # --- register + upload two distinct images ---
    item_ids = {}
    for label, png in (("red", RED_PNG), ("blue", BLUE_PNG)):
        _, reg = _req(
            "POST",
            f"{CATALOG}/v1/items",
            headers=key_headers,
            json_body={"content_type": "image/png", "metadata": {"color": label}},
        )
        item_id = reg["item"]["id"]
        item_ids[label] = item_id
        upload = reg["upload"]
        st, _ = _put(upload["url"], png, upload["headers"])
        check(f"upload {label} bytes to signed URL", st in (200, 204))
        st, conf = _req("POST", f"{CATALOG}/v1/items/{item_id}/confirm", headers=key_headers)
        check(f"confirm {label} -> queued", st == 200 and conf["status"] == "queued")

    # --- wait for the worker to index both items ---
    indexed = _wait_for_status(key_headers, item_ids.values(), "indexed", timeout=60)
    check("ingestion worker indexed both items", indexed)

    # --- image search returns the matching colour first ---
    body, ctype = _multipart_image({"file": ("q.png", RED_PNG)}, {"top_k": "5"})
    st, results = _req(
        "POST", f"{QUERY}/v1/search/image", headers={**key_headers, "Content-Type": ctype}, raw=body
    )
    check("image search returns results", st == 200 and results["count"] >= 1)
    check("nearest result is the matching (red) item", results["results"][0]["item_id"] == item_ids["red"])

    # --- hybrid filter: restrict to blue ---
    body, ctype = _multipart_image(
        {"file": ("q.png", RED_PNG)}, {"filters": json.dumps({"color": "blue"})}
    )
    st, filtered = _req(
        "POST", f"{QUERY}/v1/search/image", headers={**key_headers, "Content-Type": ctype}, raw=body
    )
    check(
        "metadata filter constrains results to blue",
        st == 200 and all(r["item_id"] == item_ids["blue"] for r in filtered["results"]),
    )

    # --- deduplication: re-upload the red image; it should be marked duplicate ---
    _, reg = _req(
        "POST", f"{CATALOG}/v1/items", headers=key_headers,
        json_body={"content_type": "image/png", "metadata": {"color": "red-dup"}},
    )
    dup_id = reg["item"]["id"]
    _put(reg["upload"]["url"], RED_PNG, reg["upload"]["headers"])
    _req("POST", f"{CATALOG}/v1/items/{dup_id}/confirm", headers=key_headers)
    is_dup = _wait_for_status(key_headers, [dup_id], "duplicate", timeout=60)
    check("duplicate image detected and not re-indexed", is_dup)

    # --- feedback ---
    st, fb = _req(
        "POST", f"{CATALOG}/v1/feedback", headers=key_headers,
        json_body={"item_id": item_ids["red"], "query_ref": "smoke-q", "relevant": True},
    )
    check("feedback recorded", st == 201 and fb.get("status") == "recorded")

    print(f"\nSMOKE PIPELINE PASSED ({_passed} checks)")


def _put(url: str, data: bytes, headers: dict):
    req = urllib.request.Request(url, data=data, headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _wait_for_status(headers, item_ids, target: str, timeout: int) -> bool:
    deadline = time.time() + timeout
    ids = set(item_ids)
    while time.time() < deadline:
        done = 0
        for iid in ids:
            _, body = _req("GET", f"{CATALOG}/v1/items/{iid}", headers=headers)
            if body.get("item", {}).get("status") == target:
                done += 1
        if done == len(ids):
            return True
        time.sleep(2)
    return False


if __name__ == "__main__":
    main()
