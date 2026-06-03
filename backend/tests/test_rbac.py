import pytest
from fastapi import HTTPException
from app.core.rbac import require_role, require_approved
from app.schemas.auth import CurrentUser

def cu(**kw):
    base = dict(id="u", role="wholesaler", status="approved")
    base.update(kw)
    return CurrentUser(**base)

def test_require_role_pass():
    require_role("wholesaler", "admin")(cu(role="wholesaler"))  # no raise

def test_require_role_block():
    with pytest.raises(HTTPException) as e:
        require_role("admin")(cu(role="wholesaler"))
    assert e.value.status_code == 403

def test_require_approved_blocks_pending():
    with pytest.raises(HTTPException):
        require_approved(cu(status="pending"))
