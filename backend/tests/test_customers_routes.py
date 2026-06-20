"""고객관리 라우터 가드 — 접근 권한(admin/승인된 도매)만 통과. 순수 가드 함수 직접 검증."""
import pytest
from fastapi import HTTPException

from app.routers.customers import require_customers_access
from app.schemas.auth import CurrentUser


def _u(role, status="approved"):
    return CurrentUser(id="u1", role=role, status=status, manager_id="m-lalas")


def test_admin_allowed():
    require_customers_access(_u("admin"))  # 예외 없으면 통과


def test_approved_wholesaler_allowed():
    require_customers_access(_u("wholesaler", "approved"))


def test_pending_wholesaler_denied():
    with pytest.raises(HTTPException) as e:
        require_customers_access(_u("wholesaler", "pending"))
    assert e.value.status_code == 403


def test_retail_seller_denied():
    with pytest.raises(HTTPException) as e:
        require_customers_access(_u("retail_seller"))
    assert e.value.status_code == 403


def test_agency_denied():
    with pytest.raises(HTTPException) as e:
        require_customers_access(_u("agency"))
    assert e.value.status_code == 403
