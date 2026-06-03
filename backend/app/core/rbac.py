from fastapi import HTTPException
from app.schemas.auth import CurrentUser


def require_approved(user: CurrentUser) -> CurrentUser:
    if user.status != "approved":
        raise HTTPException(403, "account not approved")
    return user


def require_role(*roles: str):
    def _dep(user: CurrentUser) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(403, f"requires role in {roles}")
        return user
    return _dep
