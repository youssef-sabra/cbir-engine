# sdks/

Client SDKs for the CBIR Engine (Milestone 11).

| SDK | Status | Notes |
|---|---|---|
| `python-sdk` (`cbir`) | ✅ Implemented | Thin typed wrapper over the public REST API: ingest + image/text/compositional search + feedback. Unit-tested with `httpx.MockTransport` (no live stack needed). |
| `js-sdk` | Reserved | TypeScript/JS client — the second primary-language SDK (post-MVP per the PRD). |

See `python-sdk/README.md` for usage. The SDK deliberately contains no business logic — only convenience
(auth header attachment, the register→upload→confirm handshake, typed results) over the already
well-designed API.
