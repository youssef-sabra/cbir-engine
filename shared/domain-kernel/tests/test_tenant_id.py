import uuid

import pytest

from cbir_domain_kernel import InvalidTenantIdError, TenantId


def test_new_generates_distinct_ids():
    assert TenantId.new() != TenantId.new()


def test_parse_accepts_string_uuid_and_tenant_id():
    raw = uuid.uuid4()
    from_uuid = TenantId.parse(raw)
    from_str = TenantId.parse(str(raw))
    assert from_uuid == from_str
    assert TenantId.parse(from_str) is from_str


def test_parse_rejects_garbage():
    with pytest.raises(InvalidTenantIdError):
        TenantId.parse("not-a-uuid")


def test_str_round_trips():
    tenant_id = TenantId.new()
    assert TenantId.parse(str(tenant_id)) == tenant_id
