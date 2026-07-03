#!/usr/bin/env python3
"""Manual tenant provisioning (Milestone 2 pre-self-serve tooling).

Creates a tenant and issues its first API key via auth-service's admin API,
printing the full key ONCE (it is unrecoverable afterward). Uses only the
standard library so it runs with no extra dependencies.

    python scripts/provision_tenant.py --name acme
    python scripts/provision_tenant.py --name acme --plan standard

Environment:
    AUTH_SERVICE_URL   default http://localhost:8001
    AUTH_ADMIN_TOKEN   default local-dev-admin-token
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://localhost:8001")
ADMIN_TOKEN = os.environ.get("AUTH_ADMIN_TOKEN", "local-dev-admin-token")


def _post(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        f"{AUTH_SERVICE_URL}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Admin-Token": ADMIN_TOKEN},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        sys.exit(f"error {exc.code} calling {path}: {exc.read().decode()}")
    except urllib.error.URLError as exc:
        sys.exit(f"could not reach auth-service at {AUTH_SERVICE_URL}: {exc.reason}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision a tenant and its first API key.")
    parser.add_argument("--name", required=True, help="tenant name (unique)")
    parser.add_argument("--plan", default="free", choices=["free", "standard", "enterprise"])
    parser.add_argument("--key-name", default="default", help="label for the issued API key")
    args = parser.parse_args()

    tenant = _post("/admin/tenants", {"name": args.name, "plan_tier": args.plan})
    issued = _post(
        f"/admin/tenants/{tenant['id']}/api-keys", {"name": args.key_name}
    )

    print(f"Tenant created:  {tenant['name']}  (id={tenant['id']}, plan={tenant['plan_tier']})")
    print(f"API key id:      {issued['metadata']['id']}")
    print(f"Scopes:          {', '.join(issued['metadata']['scopes'])}")
    print(f"Rate limit:      {issued['metadata']['rate_limit_per_minute']} req/min")
    print()
    print("API KEY (shown once — store it now):")
    print(f"  {issued['api_key']}")


if __name__ == "__main__":
    main()
