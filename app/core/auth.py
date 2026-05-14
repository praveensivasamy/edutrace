import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

from fastapi import HTTPException, Request, status

ROLE_ADMIN = "EduTrace.Admin"
ROLE_VIEWER = "EduTrace.Viewer"
ALLOWED_ROLES = {ROLE_ADMIN, ROLE_VIEWER}
ROLE_CLAIM_TYPES = {
    "roles",
    "role",
    "http://schemas.microsoft.com/ws/2008/06/identity/claims/role",
}
LOCAL_ENV_PATH = Path(__file__).resolve().parents[2] / "local.env"


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    user_name: str
    roles: frozenset[str]

    @property
    def is_admin(self) -> bool:
        return ROLE_ADMIN in self.roles

    @property
    def is_viewer(self) -> bool:
        return ROLE_VIEWER in self.roles


def _decode_client_principal(header_value: str) -> dict:
    try:
        decoded = base64.b64decode(header_value).decode("utf-8")
        payload = json.loads(decoded)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-MS-CLIENT-PRINCIPAL header.",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-MS-CLIENT-PRINCIPAL payload.",
        )
    return payload


def _extract_roles(payload: dict) -> set[str]:
    roles: set[str] = set()
    claims = payload.get("claims") or []
    if isinstance(claims, list):
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            claim_type = str(claim.get("typ", "")).strip().lower()
            if claim_type in ROLE_CLAIM_TYPES:
                value = claim.get("val")
                if isinstance(value, str) and value.strip():
                    roles.add(value.strip())
    direct_roles = payload.get("roles")
    if isinstance(direct_roles, list):
        for role in direct_roles:
            if isinstance(role, str) and role.strip():
                roles.add(role.strip())
    elif isinstance(direct_roles, str) and direct_roles.strip():
        roles.add(direct_roles.strip())
    return roles


def _claim_value(payload: dict, claim_types: set[str]) -> str:
    claims = payload.get("claims") or []
    if not isinstance(claims, list):
        return ""
    normalized_types = {value.lower() for value in claim_types}
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        claim_type = str(claim.get("typ", "")).strip().lower()
        if claim_type in normalized_types:
            value = claim.get("val")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _extract_identity(payload: dict) -> tuple[str, str]:
    user_id = (
        str(payload.get("userId", "")).strip()
        or _claim_value(
            payload,
            {
                "http://schemas.microsoft.com/identity/claims/objectidentifier",
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier",
                "oid",
                "sub",
            },
        )
    )
    user_name = (
        str(payload.get("userDetails", "")).strip()
        or _claim_value(
            payload,
            {
                "name",
                "preferred_username",
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
            },
        )
    )
    return user_id, user_name


def _local_roles() -> set[str]:
    app_env = os.getenv("APP_ENV", "").strip().lower()
    if app_env != "local":
        return set()
    local_role = ""
    if LOCAL_ENV_PATH.exists():
        local_role = str(dotenv_values(LOCAL_ENV_PATH).get("LOCAL_DEV_ROLE", "")).strip()
    if not local_role:
        local_role = os.getenv("LOCAL_DEV_ROLE", "").strip()
    return {local_role} if local_role else set()


def get_current_user(request: Request) -> CurrentUser:
    header_value = request.headers.get("x-ms-client-principal")
    roles = set()
    user_id = ""
    user_name = ""
    if header_value:
        payload = _decode_client_principal(header_value)
        roles = _extract_roles(payload)
        user_id, user_name = _extract_identity(payload)
    else:
        roles = _local_roles()
        if roles:
            user_id = "local-dev-user"
            user_name = "Local Developer"

    allowed_roles = frozenset(role for role in roles if role in ALLOWED_ROLES)
    if not allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have an allowed EduTrace role.",
        )
    return CurrentUser(user_id=user_id, user_name=user_name, roles=allowed_roles)


def require_admin(request: Request) -> CurrentUser:
    user = get_current_user(request)
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required.",
        )
    return user
