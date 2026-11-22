"""Profile, app settings and LLM settings."""
from __future__ import annotations

import logging

from fastapi import APIRouter

from core.config import (load_llm_settings, load_profile, load_settings, save_llm_settings,
                         save_profile, save_settings)
from core.profile_extraction import parse_resume_to_profile as extract_resume
from core.resume_upload import upload_resume
from models import LLMSettingsBody, OllamaModelsRequest, ProfileBody, SettingsBody

router = APIRouter()
_log = logging.getLogger("backend")


@router.get("/profile")
async def get_profile():
    return load_profile()


@router.put("/profile")
async def update_profile(profile: ProfileBody):
    save_profile(profile.model_dump())
    return {"success": True}


@router.get("/settings/llm")
async def get_llm():
    return load_llm_settings()


@router.put("/settings/llm")
async def update_llm(settings: LLMSettingsBody):
    save_llm_settings(settings.model_dump())
    return {"success": True}


@router.post("/llm/test")
async def test_llm(settings: LLMSettingsBody):
    """Test an LLM connection with the given (unsaved) settings."""
    try:
        from core.llm_factory import create_llm, test_connection
        llm = create_llm(settings.model_dump())
        result = await test_connection(llm)
        return {"success": True, "message": result}
    except Exception as e:
        msg = str(e)
        if "api_key" in msg.lower() or "unauthorized" in msg.lower() or "401" in msg:
            return {"success": False, "message": "Invalid API key or unauthorized. Check your credentials."}
        if "timeout" in msg.lower() or "connect" in msg.lower():
            return {"success": False, "message": "Connection failed. Check your network and provider settings (is your local LLM server running?)"}
        from browser_use.llm.exceptions import ModelProviderError
        if isinstance(e, ModelProviderError):
            return {"success": False, "message": f"LLM Provider Error: {msg}"}
        _log.error(f"LLM test failed: {e}", exc_info=True)
        return {"success": False, "message": f"LLM test failed: {msg}"}


@router.post("/llm/ollama-models")
async def list_ollama_models(body: OllamaModelsRequest):
    import httpx
    base_url = body.base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{base_url}/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            return {"success": True, "models": models}
    except Exception as e:
        return {"success": False, "models": [], "message": str(e)}


@router.get("/settings")
async def get_settings():
    return load_settings()


@router.put("/settings")
async def update_settings(settings: SettingsBody):
    # Merge over what is stored so a partial update never drops other keys
    merged = {**load_settings(), **settings.model_dump(exclude_unset=True)}
    if "sensitive_data" in settings.model_fields_set:
        merged["sensitive_data"] = settings.sensitive_data.model_dump()
    save_settings(merged)
    return {"success": True}


router.post("/resume/upload")(upload_resume)


@router.post("/profile/parse-resume")
async def parse_resume_to_profile():
    return await extract_resume(infer_country_code)


_COUNTRY_ALIASES = {"usa": "US", "united states of america": "US", "u.s.": "US", "u.s.a.": "US", "uk": "GB",
                    "england": "GB", "scotland": "GB", "great britain": "GB", "uae": "AE", "deutschland": "DE"}


def infer_country_code(parsed: dict) -> str | None:
    """Country code from a parsed resume's address (name, alias or ISO code)."""
    from core.country_config import COUNTRY_CONFIGS
    raw = str((parsed.get("address") or {}).get("country") or parsed.get("country") or "").strip()
    if not raw:
        return None
    low = raw.lower()
    if raw.upper() in COUNTRY_CONFIGS:
        return raw.upper()
    if low in _COUNTRY_ALIASES:
        return _COUNTRY_ALIASES[low]
    for code, cfg in COUNTRY_CONFIGS.items():
        if cfg.get("name", "").lower() == low:
            return code
    return None
