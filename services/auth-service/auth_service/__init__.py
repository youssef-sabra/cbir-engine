"""auth-service — tenant identity, API key lifecycle, token issuance, rate limiting.

Milestone 2. Internally follows the Clean Architecture layering documented in
docs/CLEAN_ARCHITECTURE.md Section 3: domain -> application -> interface_adapters
-> infrastructure, wired together only in entrypoint/composition_root.
"""
