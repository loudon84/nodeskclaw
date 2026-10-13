"""Casdoor subject binding and the desktop login transaction."""

import base64
import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.identity_binding import IdentityBinding
from app.models.oauth_login_transaction import OAuthLoginTransaction
from app.models.user import User
from app.services import auth_service
from app.services.identity.casdoor_client import CasdoorClient, CasdoorUnavailable, jwt_payload

logger = logging.getLogger(__name__)

PROVIDER = "casdoor"
EMAIL_MISSING = "email_missing"
EMAIL_UNVERIFIED = "email_unverified"
MEMBER_NOT_FOUND = "member_not_found"
BINDING_CONFLICT = "binding_conflict"
ORG_MISSING = "org_missing"
ACCOUNT_DISABLED = "account_disabled"
DOMAIN_NOT_ALLOWED = "domain_not_allowed"
LOGIN_EXPIRED = "login_expired"
IDP_FAILED = "idp_failed"


class InvalidReturnTo(Exception):
    pass


class NotConfigured(Exception):
    pass


class LoginExpired(Exception):
    pass


class PasswordRequired(Exception):
    pass


@dataclass(frozen=True)
class CallbackResult:
    location: str | None


def valid_return_to(value: str) -> bool:
    parts = urlsplit(value)
    if parts.scheme != "http":
        return False
    host = parts.netloc.rsplit("@", 1)[-1]
    if host.startswith("["):
        return False
    host_name, separator, port_text = host.rpartition(":")
    if not separator or host_name not in {"127.0.0.1", "localhost"}:
        return False
    if not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
        return False
    if parts.path != "/callback":
        return False
    if parts.username or parts.password or parts.query or parts.fragment:
        return False
    return True


async def start_login(db: AsyncSession, return_to: str, client: CasdoorClient) -> str:
    if not valid_return_to(return_to):
        raise InvalidReturnTo
    if not client.configured():
        raise NotConfigured
    try:
        discovered = await client.discover()
    except CasdoorUnavailable as exc:
        raise LoginExpired from exc
    verifier = secrets.token_urlsafe(64)
    state = secrets.token_urlsafe(32)
    now = _now()
    db.add(
        OAuthLoginTransaction(
            state=state,
            code_verifier=verifier,
            return_to=return_to,
            expires_at=now + timedelta(minutes=10),
        )
    )
    await db.commit()
    query = urlencode(
        {
            "response_type": "code",
            "client_id": settings.CASDOOR_CLIENT_ID,
            "redirect_uri": settings.CASDOOR_REDIRECT_URI,
            "scope": "openid profile email",
            "state": state,
            "code_challenge": _code_challenge(verifier),
            "code_challenge_method": "S256",
        }
    )
    return f"{discovered['authorization_endpoint']}?{query}"


# @lat: [[architecture/backend#Casdoor Desktop Login]]
async def finish_callback(
    db: AsyncSession,
    *,
    state: str | None,
    code: str | None,
    error: str | None,
    client: CasdoorClient,
) -> CallbackResult:
    if not state:
        return CallbackResult(location=None)
    row = await _find_transaction(db, state)
    if row is None:
        return CallbackResult(location=None)
    now = _now()
    if _aware(row.expires_at) <= now:
        if row.used_at is None:
            await _mark_state_used(db, row.id, now)
            await db.commit()
        return CallbackResult(location=_error_location(row.return_to, LOGIN_EXPIRED))
    if row.used_at is not None:
        return CallbackResult(location=_error_location(row.return_to, LOGIN_EXPIRED))
    if not await _mark_state_used(db, row.id, now):
        await db.commit()
        return CallbackResult(location=_error_location(row.return_to, LOGIN_EXPIRED))
    await db.commit()
    await db.refresh(row)
    return_to = row.return_to
    if error or not code:
        await _clear_verifier(db, row)
        return CallbackResult(location=_error_location(return_to, IDP_FAILED))
    if not client.configured():
        await _clear_verifier(db, row)
        return CallbackResult(location=_error_location(return_to, IDP_FAILED))
    verifier = row.code_verifier
    try:
        discovered = await client.discover()
        access_token = await client.exchange_code(discovered["token_endpoint"], code, verifier)
        profile = await client.userinfo(discovered["userinfo_endpoint"], access_token)
        _fill_profile_from_access_token(profile, access_token)
    except CasdoorUnavailable:
        await _clear_verifier(db, row)
        return CallbackResult(location=_error_location(return_to, IDP_FAILED))
    await _clear_verifier(db, row)
    machine_code = await _bind(db, row, profile)
    if machine_code is not None:
        return CallbackResult(location=_error_location(return_to, machine_code))
    raw_code = secrets.token_urlsafe(32)
    row.exchange_code_hash = hashlib.sha256(raw_code.encode()).hexdigest()
    row.exchange_expires_at = now + timedelta(seconds=60)
    await db.commit()
    return CallbackResult(location=f"{return_to}?code={raw_code}")


async def exchange_code(db: AsyncSession, code: str, client: CasdoorClient):
    if not client.configured():
        raise NotConfigured
    digest = hashlib.sha256(code.encode()).hexdigest()
    result = await db.execute(
        select(OAuthLoginTransaction).where(
            OAuthLoginTransaction.exchange_code_hash == digest,
            OAuthLoginTransaction.deleted_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    now = _now()
    if row is None or row.used_at is None or row.member_user_id is None:
        raise LoginExpired
    if row.exchange_used_at is not None:
        raise LoginExpired
    if _aware(row.expires_at) <= now or row.exchange_expires_at is None or _aware(row.exchange_expires_at) <= now:
        raise LoginExpired
    user = await _load_user(db, row.member_user_id)
    binding = await _binding_for_member(db, row.member_user_id)
    if user is None or not user.is_active or binding is None or not user.email or not auth_service.is_email_domain_allowed(user.email):
        raise LoginExpired
    consumed = await db.execute(
        update(OAuthLoginTransaction)
        .where(
            OAuthLoginTransaction.id == row.id,
            OAuthLoginTransaction.exchange_used_at.is_(None),
        )
        .values(exchange_used_at=now)
    )
    if consumed.rowcount != 1:
        await db.commit()
        raise LoginExpired
    user.last_login_at = now
    binding.last_login_at = now
    await db.commit()
    return await auth_service.issue_login_response(user, db)


async def unbind(db: AsyncSession, user: User) -> None:
    if not user.password_hash:
        raise PasswordRequired
    binding = await _binding_for_member(db, user.id)
    if binding is None:
        return
    binding.soft_delete()
    await db.commit()


async def _bind(
    db: AsyncSession,
    row: OAuthLoginTransaction,
    profile: dict,
) -> str | None:
    org = _owner_text(profile)
    if not org:
        return ORG_MISSING
    subject = profile.get("sub")
    subject = subject.strip() if isinstance(subject, str) else ""
    if not subject or "/" in subject:
        return IDP_FAILED
    existing = await _binding_for_subject(db, org, subject)
    if existing is not None:
        user = await _load_user(db, existing.member_user_id)
        if user is None or not user.is_active:
            return ACCOUNT_DISABLED
        if not user.email or not auth_service.is_email_domain_allowed(user.email):
            return DOMAIN_NOT_ALLOWED
        existing.email = _snapshot_email(profile)
        row.member_user_id = user.id
        return None
    email = profile.get("email")
    email = email.strip() if isinstance(email, str) else ""
    if not email:
        return EMAIL_MISSING
    if _verified_flag(profile) is False:
        return EMAIL_UNVERIFIED
    user = await _match_user(db, email.strip().lower())
    if user is None:
        return MEMBER_NOT_FOUND
    if await _binding_for_member(db, user.id) is not None:
        return BINDING_CONFLICT
    if not user.email or not auth_service.is_email_domain_allowed(user.email):
        return DOMAIN_NOT_ALLOWED
    db.add(
        IdentityBinding(
            member_user_id=user.id,
            provider=PROVIDER,
            provider_org=org,
            provider_user_id=subject,
            email=_snapshot_email(profile),
        )
    )
    row.member_user_id = user.id
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        logger.info("casdoor binding conflict")
        return BINDING_CONFLICT
    return None


def _fill_profile_from_access_token(profile: dict, access_token: str) -> None:
    claims = jwt_payload(access_token)
    if not _owner_text(profile):
        owner = _owner_text(claims)
        if owner:
            profile["owner"] = owner
    profile_flag = _verified_flag(profile)
    claims_flag = _verified_flag(claims)
    if profile_flag is True or claims_flag is True:
        profile["email_verified"] = True
        return
    if profile_flag is False or claims_flag is False:
        profile["email_verified"] = "true"


_VERIFIED_KEYS = ("email_verified", "emailVerified", "EmailVerified", "isVerified")


def _verified_flag(data: dict) -> bool | None:
    invalid = False
    for key in _VERIFIED_KEYS:
        if key not in data:
            continue
        if data[key] is True:
            return True
        if data[key] is not False:
            invalid = True
    if invalid:
        return False
    return None


def _owner_text(data: dict) -> str:
    for key in ("owner", "Owner"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _snapshot_email(profile: dict) -> str:
    email = profile.get("email")
    if not isinstance(email, str):
        return ""
    return email.strip().lower()[:256]


async def _match_user(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(
            func.lower(User.email) == email,
            User.deleted_at.is_(None),
            User.is_active.is_(True),
            User.email.is_not(None),
            User.email != "",
        )
    )
    return result.scalar_one_or_none()


async def _load_user(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def _binding_for_subject(db: AsyncSession, org: str, subject: str) -> IdentityBinding | None:
    result = await db.execute(
        select(IdentityBinding).where(
            IdentityBinding.provider == PROVIDER,
            IdentityBinding.provider_org == org,
            IdentityBinding.provider_user_id == subject,
            IdentityBinding.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def _binding_for_member(db: AsyncSession, member_user_id: str) -> IdentityBinding | None:
    result = await db.execute(
        select(IdentityBinding).where(
            IdentityBinding.provider == PROVIDER,
            IdentityBinding.member_user_id == member_user_id,
            IdentityBinding.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def _find_transaction(db: AsyncSession, state: str) -> OAuthLoginTransaction | None:
    result = await db.execute(
        select(OAuthLoginTransaction).where(
            OAuthLoginTransaction.state == state,
            OAuthLoginTransaction.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def _mark_state_used(db: AsyncSession, transaction_id: str, now: datetime) -> bool:
    result = await db.execute(
        update(OAuthLoginTransaction)
        .where(
            OAuthLoginTransaction.id == transaction_id,
            OAuthLoginTransaction.used_at.is_(None),
        )
        .values(used_at=now)
    )
    return result.rowcount == 1


async def _clear_verifier(db: AsyncSession, row: OAuthLoginTransaction) -> None:
    row.code_verifier = ""
    await db.commit()


def _error_location(return_to: str, machine_code: str) -> str:
    return f"{return_to}?error={machine_code}"


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
