import pytest

from auth_service.domain import domain_services
from auth_service.domain.domain_services import MalformedApiKeyError
from auth_service.domain.value_objects import PlanTier, UnknownScopeError, validate_scopes


def test_issued_key_round_trips_through_parse_and_verify():
    issued = domain_services.issue_secret()
    key_id, secret = domain_services.parse_full_key(issued.full_key)
    assert key_id == issued.key_id
    assert domain_services.verify_secret(secret, issued.secret_hash)
    assert not domain_services.verify_secret("wrong-secret", issued.secret_hash)


def test_full_key_never_contains_the_stored_hash():
    issued = domain_services.issue_secret()
    assert issued.secret_hash not in issued.full_key


@pytest.mark.parametrize(
    "bad_key",
    ["", "cbir", "cbir_notahexid_secret", "other_aaaa_bbbb", "cbir_1234_", "cbir__secret"],
)
def test_parse_rejects_malformed_keys(bad_key):
    with pytest.raises(MalformedApiKeyError):
        domain_services.parse_full_key(bad_key)


def test_validate_scopes_rejects_unknown_and_empty():
    with pytest.raises(UnknownScopeError):
        validate_scopes(("catalog:read", "not-a-scope"))
    with pytest.raises(UnknownScopeError):
        validate_scopes(())


def test_validate_scopes_deduplicates():
    assert validate_scopes(("catalog:read", "catalog:read")) == ("catalog:read",)


def test_plan_tiers_have_rate_limit_defaults():
    assert PlanTier.FREE.default_rate_limit_per_minute < (
        PlanTier.ENTERPRISE.default_rate_limit_per_minute
    )
