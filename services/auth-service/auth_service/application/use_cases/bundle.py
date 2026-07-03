"""Aggregate of all wired use cases handed to controllers per unit of work."""

from __future__ import annotations

from dataclasses import dataclass

from auth_service.application.use_cases.api_keys import (
    IssueApiKey,
    ListApiKeys,
    RevokeApiKey,
    RotateApiKey,
)
from auth_service.application.use_cases.credentials import (
    ValidateAccessTokenCredential,
    ValidateApiKeyCredential,
)
from auth_service.application.use_cases.tenants import CreateTenant, GetTenant, ListTenants
from auth_service.application.use_cases.tokens import IssueAccessToken


@dataclass(frozen=True)
class UseCaseBundle:
    create_tenant: CreateTenant
    get_tenant: GetTenant
    list_tenants: ListTenants
    issue_api_key: IssueApiKey
    list_api_keys: ListApiKeys
    rotate_api_key: RotateApiKey
    revoke_api_key: RevokeApiKey
    validate_api_key: ValidateApiKeyCredential
    validate_access_token: ValidateAccessTokenCredential
    issue_access_token: IssueAccessToken
