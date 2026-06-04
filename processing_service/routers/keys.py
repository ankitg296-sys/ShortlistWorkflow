import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..config import get_settings
from ..db import get_supabase
from ..dependencies import CurrentUser, get_current_user
from ..vault.crypto import decrypt, encrypt
from ..vault.provider import test_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/keys", tags=["keys"])

_SUPPORTED_PROVIDERS = {"anthropic"}


# ── Request / response models ─────────────────────────────────────────────────


class AddKeyRequest(BaseModel):
    provider: str
    api_key: str  # plaintext — encrypted immediately, never stored or logged as-is
    model_options: dict = {}  # stored as model_config in DB; "model_config" is reserved by Pydantic


class KeyOut(BaseModel):
    id: str
    provider: str
    key_hint: str | None
    model_options: dict
    is_active: bool
    validated_at: str | None
    created_at: str
    # encrypted_key is intentionally absent from this model


class TestKeyResult(BaseModel):
    ok: bool


# ── Helper ────────────────────────────────────────────────────────────────────


def _to_key_out(row: dict) -> KeyOut:
    return KeyOut(
        id=row["id"],
        provider=row["provider"],
        key_hint=row.get("key_hint"),
        model_options=row.get("model_config") or {},
        is_active=row.get("is_active", True),
        validated_at=row.get("validated_at"),
        created_at=row["created_at"],
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/", response_model=KeyOut, status_code=status.HTTP_201_CREATED)
async def add_key(
    body: AddKeyRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> KeyOut:
    """
    Encrypt and store an org API key.
    Only the last-4-char hint and the ciphertext are persisted.
    The plaintext is never logged, returned, or stored.
    """
    if body.provider not in _SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider {body.provider!r}. Supported: {sorted(_SUPPORTED_PROVIDERS)}",
        )

    settings = get_settings()
    ciphertext = encrypt(body.api_key, settings.encryption_master_key)
    key_hint = body.api_key[-4:] if len(body.api_key) >= 4 else "****"

    supabase = get_supabase()
    row = (
        supabase
        .table("api_keys")
        .insert(
            {
                "org_id": current_user.org_id,
                "provider": body.provider,
                "encrypted_key": ciphertext,
                "key_hint": key_hint,
                "model_config": body.model_options,
            }
        )
        .execute()
        .data[0]
    )

    # Audit log key addition (never log the plaintext key)
    supabase.table("audit_log").insert({
        "org_id": current_user.org_id,
        "event_type": "key_added",
        "payload": {
            "key_id": row["id"],
            "key_hint": key_hint,
            "provider": body.provider,
            "added_by": current_user.id,
        },
    }).execute()

    logger.info("key %s added for org %s by %s", row["id"], current_user.org_id, current_user.id)
    return _to_key_out(row)


@router.get("/", response_model=list[KeyOut])
async def list_keys(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[KeyOut]:
    """List active API keys for the org. Never returns ciphertexts."""
    rows = (
        get_supabase()
        .table("api_keys")
        # Select specific columns — encrypted_key is intentionally excluded
        .select("id, provider, key_hint, model_config, is_active, validated_at, created_at")
        .eq("org_id", current_user.org_id)  # tenant isolation (service role bypasses RLS)
        .eq("is_active", True)
        .execute()
        .data
    )
    return [_to_key_out(row) for row in rows]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(
    key_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> None:
    """Permanently delete an API key. Filtered by both id AND org_id for tenant safety."""
    supabase = get_supabase()

    # Verify key belongs to org
    key_row = (
        supabase.table("api_keys")
        .select("id, key_hint")
        .eq("id", key_id)
        .eq("org_id", current_user.org_id)
        .maybe_single()
        .execute()
    )
    if key_row.data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")

    result = (
        supabase
        .table("api_keys")
        .delete()
        .eq("id", key_id)
        .eq("org_id", current_user.org_id)
        .execute()
    )

    # Audit log key deletion
    supabase.table("audit_log").insert({
        "org_id": current_user.org_id,
        "event_type": "key_deleted",
        "payload": {
            "key_id": key_id,
            "key_hint": key_row.data["key_hint"],
            "deleted_by": current_user.id,
        },
    }).execute()

    logger.info("key %s deleted for org %s by %s", key_id, current_user.org_id, current_user.id)


@router.post("/{key_id}/test", response_model=TestKeyResult)
async def test_key(
    key_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> TestKeyResult:
    """
    Decrypt the key and make one live API call to confirm it works.
    Returns {"ok": true/false} only — the key is never in the response.
    """
    settings = get_settings()
    supabase = get_supabase()

    row = (
        supabase.table("api_keys")
        .select("id, provider, encrypted_key, model_config")
        .eq("id", key_id)
        .eq("org_id", current_user.org_id)  # tenant isolation
        .maybe_single()
        .execute()
    )
    if row.data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")

    plaintext = decrypt(row.data["encrypted_key"], settings.encryption_master_key)
    model = (row.data["model_config"] or {}).get("scoring_model") or settings.default_model

    ok = test_api_key(row.data["provider"], plaintext, model)

    # Audit log key test (pass/fail, no key details)
    supabase.table("audit_log").insert({
        "org_id": current_user.org_id,
        "event_type": "key_tested",
        "payload": {
            "key_id": key_id,
            "test_result": "pass" if ok else "fail",
            "tested_by": current_user.id,
        },
    }).execute()

    if ok:
        supabase.table("api_keys").update(
            {"validated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", key_id).eq("org_id", current_user.org_id).execute()

    logger.info("key %s test %s for org %s", key_id, "pass" if ok else "fail", current_user.org_id)
    return TestKeyResult(ok=ok)
