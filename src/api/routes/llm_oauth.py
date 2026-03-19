"""
LLM Provider OAuth Routes
Handles OAuth flow and provider configuration
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from pydantic import BaseModel
from typing import Optional, List
import secrets
import httpx
import os
from datetime import datetime
from psycopg2.extras import RealDictCursor

from ..middleware.auth import get_db, get_current_user
from ...services.llm_provider import LLMProviderManager, PROVIDERS

router = APIRouter(prefix="/v1/llm", tags=["LLM Providers"])

# ============================================
# Models
# ============================================

class ConfigureProviderRequest(BaseModel):
    provider: str
    api_key: str
    model: Optional[str] = None
    base_url: Optional[str] = None  # For custom providers

# ============================================
# Endpoints
# ============================================

@router.get("/providers")
async def list_providers():
    """List all available LLM providers + their models"""
    return {"providers": LLMProviderManager.list_providers()}


@router.post("/configure")
async def configure_provider(
    config: ConfigureProviderRequest,
    current_user: dict = Depends(get_current_user)
):
    """Configure LLM provider with API key (manual method)"""
    company_id = str(current_user["company_id"])
    
    # Validate provider
    if config.provider not in PROVIDERS:
        raise HTTPException(400, f"Unknown provider: {config.provider}")
    
    provider_info = PROVIDERS[config.provider]
    
    # Build config
    provider_config = {
        "auth_method": "api_key",
        "api_key": config.api_key,
        "model": config.model or provider_info["default_model"],
    }
    
    if config.provider == "custom" and config.base_url:
        provider_config["base_url"] = config.base_url
    
    # Test connection
    manager = LLMProviderManager(get_db)
    try:
        provider = manager.get_provider(config.provider, provider_config)
        test_result = provider.test_connection()
        
        if not test_result.get("success"):
            raise HTTPException(400, f"Connection test failed: {test_result.get('error', 'Unknown error')}")
    except Exception as e:
        raise HTTPException(400, f"Failed to initialize provider: {str(e)}")
    
    # Save to database
    manager.save_company_provider(company_id, config.provider, provider_config)
    
    return {
        "success": True,
        "provider": config.provider,
        "model": provider_config["model"],
        "test_result": test_result
    }


@router.post("/test")
async def test_connection(current_user: dict = Depends(get_current_user)):
    """Test current LLM connection"""
    company_id = str(current_user["company_id"])
    
    manager = LLMProviderManager(get_db)
    
    try:
        provider = manager.get_company_provider(company_id)
        test_result = provider.test_connection()
        return test_result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/status")
async def get_status(current_user: dict = Depends(get_current_user)):
    """Get current provider status for company"""
    company_id = str(current_user["company_id"])
    
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT metadata FROM companies WHERE id = %s", (company_id,))
            row = cur.fetchone()
            
            if not row or not row.get("metadata"):
                # Using default
                return {
                    "configured": False,
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-20250514",
                    "auth_method": "env_var",
                    "note": "Using default ANTHROPIC_API_KEY from environment"
                }
            
            llm_config = row["metadata"].get("llm_provider", {})
            if not llm_config:
                return {
                    "configured": False,
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-20250514",
                    "auth_method": "env_var"
                }
            
            return {
                "configured": True,
                "provider": llm_config.get("provider", "anthropic"),
                "model": llm_config.get("model", "claude-sonnet-4-20250514"),
                "auth_method": llm_config.get("auth_method", "api_key"),
                "base_url": llm_config.get("base_url") if llm_config.get("provider") == "custom" else None
            }


@router.get("/models")
async def list_models(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    current_user: dict = Depends(get_current_user)
):
    """List models for current or specified provider"""
    company_id = str(current_user["company_id"])
    
    if not provider:
        # Get current provider
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT metadata FROM companies WHERE id = %s", (company_id,))
                row = cur.fetchone()
                
                if row and row.get("metadata"):
                    llm_config = row["metadata"].get("llm_provider", {})
                    provider = llm_config.get("provider", "anthropic")
                else:
                    provider = "anthropic"
    
    if provider not in PROVIDERS:
        raise HTTPException(400, f"Unknown provider: {provider}")
    
    provider_info = PROVIDERS[provider]
    
    # Get models from provider class
    try:
        if provider == "anthropic":
            from ...services.llm_provider import AnthropicProvider
            models = AnthropicProvider(api_key="dummy").get_models()
        elif provider == "openai":
            from ...services.llm_provider import OpenAIProvider
            models = OpenAIProvider(api_key="dummy").get_models()
        elif provider == "gemini":
            from ...services.llm_provider import GeminiProvider
            models = GeminiProvider(api_key="dummy").get_models()
        elif provider == "custom":
            from ...services.llm_provider import CustomProvider
            models = CustomProvider().get_models()
        else:
            models = []
    except:
        models = []
    
    return {
        "provider": provider,
        "models": models
    }


@router.post("/model")
async def set_model(
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    """Set model for company"""
    company_id = str(current_user["company_id"])
    model = request.get("model")
    
    if not model:
        raise HTTPException(400, "Model is required")
    
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT metadata FROM companies WHERE id = %s", (company_id,))
            row = cur.fetchone()
            
            if not row:
                raise HTTPException(404, "Company not found")
            
            metadata = row.get("metadata") or {}
            llm_config = metadata.get("llm_provider", {})
            
            if not llm_config:
                raise HTTPException(400, "No LLM provider configured. Configure a provider first.")
            
            llm_config["model"] = model
            metadata["llm_provider"] = llm_config
            
            cur.execute(
                "UPDATE companies SET metadata = %s WHERE id = %s",
                (metadata, company_id)
            )
            conn.commit()
    
    return {
        "success": True,
        "model": model,
        "provider": llm_config.get("provider", "anthropic")
    }


# ============================================
# OAuth Flow
# ============================================

@router.get("/oauth/{provider}/authorize")
async def oauth_authorize(
    provider: str,
    current_user: dict = Depends(get_current_user)
):
    """Start OAuth flow (redirect to provider)"""
    company_id = str(current_user["company_id"])
    
    if provider not in PROVIDERS:
        raise HTTPException(400, f"Unknown provider: {provider}")
    
    provider_info = PROVIDERS[provider]
    oauth_info = provider_info.get("oauth", {})
    
    if not oauth_info.get("enabled"):
        raise HTTPException(400, f"OAuth not supported for {provider}")
    
    # Generate state token
    state_token = secrets.token_urlsafe(32)
    redirect_uri = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8080/v1/llm/oauth/callback")
    
    # Save state to database
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO oauth_states (company_id, provider, state_token, redirect_uri, expires_at)
                VALUES (%s, %s, %s, %s, NOW() + INTERVAL '10 minutes')
            """, (company_id, provider, state_token, redirect_uri))
            conn.commit()
    
    # Build authorization URL
    client_id = os.getenv(f"{provider.upper()}_CLIENT_ID")
    if not client_id:
        raise HTTPException(500, f"{provider.upper()}_CLIENT_ID not configured")
    
    scopes = " ".join(oauth_info["scopes"])
    auth_url = f"{oauth_info['authorize_url']}?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={scopes}&state={state_token}"
    
    return {
        "authorization_url": auth_url,
        "state": state_token,
        "provider": provider
    }


@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None)
):
    """OAuth callback (receive tokens)"""
    if error:
        raise HTTPException(400, f"OAuth error: {error}")
    
    # Verify state token
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT company_id, provider, redirect_uri
                FROM oauth_states
                WHERE state_token = %s AND expires_at > NOW()
            """, (state,))
            state_row = cur.fetchone()
            
            if not state_row:
                raise HTTPException(400, "Invalid or expired state token")
            
            company_id = state_row["company_id"]
            provider = state_row["provider"]
            redirect_uri = state_row["redirect_uri"]
            
            # Exchange code for access token
            provider_info = PROVIDERS[provider]
            oauth_info = provider_info["oauth"]
            
            client_id = os.getenv(f"{provider.upper()}_CLIENT_ID")
            client_secret = os.getenv(f"{provider.upper()}_CLIENT_SECRET")
            
            if not client_id or not client_secret:
                raise HTTPException(500, f"OAuth credentials not configured for {provider}")
            
            token_data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret
            }
            
            async with httpx.AsyncClient() as client:
                resp = await client.post(oauth_info["token_url"], data=token_data)
                
                if resp.status_code != 200:
                    raise HTTPException(400, f"Token exchange failed: {resp.text}")
                
                tokens = resp.json()
                access_token = tokens.get("access_token")
                refresh_token = tokens.get("refresh_token")
                
                if not access_token:
                    raise HTTPException(400, "No access token received")
            
            # Save tokens to company config
            provider_config = {
                "auth_method": "oauth",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "model": provider_info["default_model"],
                "oauth_connected_at": str(datetime.now())
            }
            
            manager = LLMProviderManager(get_db)
            manager.save_company_provider(company_id, provider, provider_config)
            
            # Delete state token
            cur.execute("DELETE FROM oauth_states WHERE state_token = %s", (state,))
            conn.commit()
    
    return {
        "success": True,
        "provider": provider,
        "message": f"Successfully connected {provider_info['name']}",
        "redirect": "/dashboard/settings/llm"
    }


@router.post("/oauth/{provider}/refresh")
async def oauth_refresh(
    provider: str,
    current_user: dict = Depends(get_current_user)
):
    """Refresh OAuth token"""
    company_id = str(current_user["company_id"])
    
    if provider not in PROVIDERS:
        raise HTTPException(400, f"Unknown provider: {provider}")
    
    provider_info = PROVIDERS[provider]
    oauth_info = provider_info.get("oauth", {})
    
    if not oauth_info.get("enabled"):
        raise HTTPException(400, f"OAuth not supported for {provider}")
    
    # Get current config
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT metadata FROM companies WHERE id = %s", (company_id,))
            row = cur.fetchone()
            
            if not row or not row.get("metadata"):
                raise HTTPException(400, "No LLM provider configured")
            
            llm_config = row["metadata"].get("llm_provider", {})
            
            if not llm_config or llm_config.get("provider") != provider:
                raise HTTPException(400, f"{provider} not configured")
            
            if llm_config.get("auth_method") != "oauth":
                raise HTTPException(400, "Not using OAuth authentication")
            
            refresh_token = llm_config.get("refresh_token")
            if not refresh_token:
                raise HTTPException(400, "No refresh token available")
            
            # Decrypt refresh token
            from ...services.llm_provider import decrypt_key
            if llm_config.get("token_encrypted"):
                refresh_token = decrypt_key(refresh_token)
            
            # Refresh token request
            client_id = os.getenv(f"{provider.upper()}_CLIENT_ID")
            client_secret = os.getenv(f"{provider.upper()}_CLIENT_SECRET")
            
            token_data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret
            }
            
            async with httpx.AsyncClient() as client:
                resp = await client.post(oauth_info["token_url"], data=token_data)
                
                if resp.status_code != 200:
                    raise HTTPException(400, f"Token refresh failed: {resp.text}")
                
                tokens = resp.json()
                new_access_token = tokens.get("access_token")
                new_refresh_token = tokens.get("refresh_token", refresh_token)
                
                if not new_access_token:
                    raise HTTPException(400, "No access token received")
            
            # Update config
            llm_config["access_token"] = new_access_token
            llm_config["refresh_token"] = new_refresh_token
            llm_config["oauth_refreshed_at"] = str(datetime.now())
            
            manager = LLMProviderManager(get_db)
            manager.save_company_provider(company_id, provider, llm_config)
    
    return {
        "success": True,
        "provider": provider,
        "message": "Token refreshed successfully"
    }
