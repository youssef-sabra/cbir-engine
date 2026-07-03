"""Exchange a valid API key for a short-lived signed access token."""

from __future__ import annotations

from auth_service.application.dto import AccessTokenOutput
from auth_service.application.ports import TokenClaims, TokenSignerPort
from auth_service.application.use_cases.credentials import ValidateApiKeyCredential


class IssueAccessToken:
    def __init__(
        self,
        validate_api_key: ValidateApiKeyCredential,
        signer: TokenSignerPort,
        ttl_seconds: int,
    ) -> None:
        self._validate_api_key = validate_api_key
        self._signer = signer
        self._ttl_seconds = ttl_seconds

    def execute(self, presented_key: str) -> AccessTokenOutput:
        context = self._validate_api_key.execute(presented_key)
        token = self._signer.sign(
            TokenClaims(
                tenant_id=context.tenant_id,
                api_key_id=context.api_key_id,
                scopes=context.scopes,
                plan_tier=context.plan_tier,
                rate_limit_per_minute=context.rate_limit.limit_per_minute,
            ),
            ttl_seconds=self._ttl_seconds,
        )
        return AccessTokenOutput(
            access_token=token, token_type="bearer", expires_in=self._ttl_seconds
        )
