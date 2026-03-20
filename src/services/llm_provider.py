"""
Multi-LLM Provider Service
Supports: Anthropic Claude, OpenAI GPT, Google Gemini, Custom/Local
Connection: API Key or OAuth
"""
import os
import json
import logging
import httpx
from typing import Dict, List, Optional, AsyncGenerator
from abc import ABC, abstractmethod
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# Encryption key for storing API keys
ENCRYPTION_KEY = os.getenv("LLM_ENCRYPTION_KEY", Fernet.generate_key().decode())
cipher = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

def encrypt_key(api_key: str) -> str:
    """Encrypt API key for storage."""
    return cipher.encrypt(api_key.encode()).decode()

def decrypt_key(encrypted: str) -> str:
    """Decrypt stored API key."""
    return cipher.decrypt(encrypted.encode()).decode()


class LLMProvider(ABC):
    """Base class for LLM providers."""
    
    @abstractmethod
    async def chat(self, messages: list, system: str = "", max_tokens: int = 4096, tools: list = None) -> dict:
        """Send chat request to LLM."""
        pass
    
    @abstractmethod
    async def chat_stream(self, messages: list, system: str = "", max_tokens: int = 4096, tools: list = None) -> AsyncGenerator:
        """Stream chat response from LLM."""
        pass
    
    @abstractmethod
    def test_connection(self) -> dict:
        """Test if the connection/API key works."""
        pass
    
    @abstractmethod
    def get_models(self) -> list:
        """List available models."""
        pass


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""
    
    MODELS = [
        {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "context": 200000},
        {"id": "claude-opus-4-20250514", "name": "Claude Opus 4", "context": 200000},
        {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "context": 200000},
    ]
    
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        from anthropic import Anthropic
        self.is_oauth = api_key.startswith("sk-ant-oat")
        if self.is_oauth:
            # OAuth workspace token — mimic Claude Code CLI headers
            self.client = Anthropic(
                api_key=None,
                auth_token=api_key,
                default_headers={
                    "anthropic-beta": "claude-code-20250219,oauth-2025-04-20,interleaved-thinking-2025-05-14",
                    "user-agent": "claude-cli/2.1.62",
                    "x-app": "cli",
                    "anthropic-dangerous-direct-browser-access": "true",
                }
            )
        else:
            # Standard API key
            self.client = Anthropic(api_key=api_key)
        self.model = model
    
    async def chat(self, messages, system="", max_tokens=4096, tools=None):
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if self.is_oauth:
            # OAuth requires Claude Code identity
            oauth_system = "You are Claude Code, Anthropic's official CLI for Claude."
            if system:
                kwargs["system"] = f"{oauth_system}\n\n{system}"
            else:
                kwargs["system"] = oauth_system
        elif system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        
        response = self.client.messages.create(**kwargs)
        return {
            "content": response.content,
            "model": response.model,
            "usage": {"input": response.usage.input_tokens, "output": response.usage.output_tokens},
            "stop_reason": response.stop_reason,
        }
    
    async def chat_stream(self, messages, system="", max_tokens=4096, tools=None):
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if self.is_oauth:
            # OAuth requires Claude Code identity
            oauth_system = "You are Claude Code, Anthropic's official CLI for Claude."
            if system:
                kwargs["system"] = f"{oauth_system}\n\n{system}"
            else:
                kwargs["system"] = oauth_system
        elif system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        
        with self.client.messages.stream(**kwargs) as stream:
            for event in stream:
                yield event
    
    def test_connection(self):
        try:
            kwargs = {
                "model": self.model,
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Hi"}]
            }
            if self.is_oauth:
                kwargs["system"] = "You are Claude Code, Anthropic's official CLI for Claude."
            response = self.client.messages.create(**kwargs)
            return {"success": True, "model": response.model, "provider": "anthropic"}
        except Exception as e:
            return {"success": False, "error": str(e), "provider": "anthropic"}
    
    def get_models(self):
        return self.MODELS


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider."""
    
    MODELS = [
        {"id": "gpt-4o", "name": "GPT-4o", "context": 128000},
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "context": 128000},
        {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "context": 128000},
        {"id": "o1", "name": "O1", "context": 200000},
        {"id": "o1-mini", "name": "O1 Mini", "context": 128000},
    ]
    
    def __init__(self, api_key: str, model: str = "gpt-4o", base_url: str = None):
        from openai import OpenAI
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model = model
    
    async def chat(self, messages, system="", max_tokens=4096, tools=None):
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        
        # Convert Anthropic-style messages to OpenAI format
        for msg in messages:
            if isinstance(msg.get("content"), list):
                # Handle tool_result and multi-content
                text_parts = []
                for block in msg["content"]:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block["text"])
                        elif block.get("type") == "tool_result":
                            text_parts.append(str(block.get("content", "")))
                    else:
                        text_parts.append(str(block))
                msgs.append({"role": msg["role"], "content": "\n".join(text_parts)})
            else:
                msgs.append(msg)
        
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": msgs,
        }
        
        # Convert Anthropic tools to OpenAI function format
        if tools:
            openai_tools = []
            for tool in tools:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {})
                    }
                })
            kwargs["tools"] = openai_tools
        
        response = self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        
        # Convert OpenAI response to Anthropic-like format
        content = []
        if choice.message.content:
            content.append({"type": "text", "text": choice.message.content})
        
        # Handle tool calls
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                content.append({
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": json.loads(tc.function.arguments)
                })
        
        stop_reason = "end_turn"
        if choice.finish_reason == "tool_calls":
            stop_reason = "tool_use"
        
        return {
            "content": content,
            "model": response.model,
            "usage": {"input": response.usage.prompt_tokens, "output": response.usage.completion_tokens},
            "stop_reason": stop_reason,
        }
    
    async def chat_stream(self, messages, system="", max_tokens=4096, tools=None):
        # Simplified streaming
        result = await self.chat(messages, system, max_tokens, tools)
        yield result
    
    def test_connection(self):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}]
            )
            return {"success": True, "model": response.model, "provider": "openai"}
        except Exception as e:
            return {"success": False, "error": str(e), "provider": "openai"}
    
    def get_models(self):
        return self.MODELS


class GeminiProvider(LLMProvider):
    """Google Gemini provider."""
    
    MODELS = [
        {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "context": 1000000},
        {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "context": 1000000},
        {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "context": 1000000},
    ]
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
    
    async def chat(self, messages, system="", max_tokens=4096, tools=None):
        # Convert to Gemini format
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            text = msg["content"] if isinstance(msg["content"], str) else str(msg["content"])
            contents.append({"role": role, "parts": [{"text": text}]})
        
        payload = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": max_tokens}
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}",
                json=payload,
                timeout=120
            )
            data = resp.json()
        
        if "error" in data:
            raise Exception(data["error"].get("message", "Gemini API error"))
        
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return {
            "content": [{"type": "text", "text": text}],
            "model": self.model,
            "usage": {"input": 0, "output": 0},  # Gemini doesn't always return token counts
            "stop_reason": "end_turn",
        }
    
    async def chat_stream(self, messages, system="", max_tokens=4096, tools=None):
        result = await self.chat(messages, system, max_tokens, tools)
        yield result
    
    def test_connection(self):
        import httpx
        try:
            resp = httpx.post(
                f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}",
                json={"contents": [{"parts": [{"text": "Hi"}]}], "generationConfig": {"maxOutputTokens": 10}},
                timeout=30
            )
            data = resp.json()
            if "error" in data:
                return {"success": False, "error": data["error"]["message"], "provider": "gemini"}
            return {"success": True, "model": self.model, "provider": "gemini"}
        except Exception as e:
            return {"success": False, "error": str(e), "provider": "gemini"}
    
    def get_models(self):
        return self.MODELS


class CustomProvider(LLMProvider):
    """Custom/Local LLM provider (OpenAI-compatible API)."""
    
    def __init__(self, api_key: str = "", base_url: str = "http://localhost:11434/v1", model: str = "llama3"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key or "not-needed", base_url=base_url)
        self.model = model
        self.base_url = base_url
    
    async def chat(self, messages, system="", max_tokens=4096, tools=None):
        # Same as OpenAI provider but for local models
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        for msg in messages:
            if isinstance(msg.get("content"), str):
                msgs.append(msg)
            else:
                msgs.append({"role": msg["role"], "content": str(msg["content"])})
        
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=msgs,
        )
        
        text = response.choices[0].message.content or ""
        return {
            "content": [{"type": "text", "text": text}],
            "model": self.model,
            "usage": {"input": getattr(response.usage, 'prompt_tokens', 0), "output": getattr(response.usage, 'completion_tokens', 0)},
            "stop_reason": "end_turn",
        }
    
    async def chat_stream(self, messages, system="", max_tokens=4096, tools=None):
        result = await self.chat(messages, system, max_tokens, tools)
        yield result
    
    def test_connection(self):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}]
            )
            return {"success": True, "model": self.model, "provider": "custom", "base_url": self.base_url}
        except Exception as e:
            return {"success": False, "error": str(e), "provider": "custom"}
    
    def get_models(self):
        return [{"id": self.model, "name": self.model, "context": 0}]


# ============================================
# Provider Registry & Factory
# ============================================

PROVIDERS = {
    "anthropic": {
        "name": "Anthropic Claude",
        "class": AnthropicProvider,
        "auth_methods": ["api_key"],
        "default_model": "claude-sonnet-4-20250514",
        "website": "https://console.anthropic.com",
        "oauth": {
            "enabled": False,  # Anthropic doesn't have OAuth yet
        }
    },
    "openai": {
        "name": "OpenAI",
        "class": OpenAIProvider,
        "auth_methods": ["api_key", "oauth"],
        "default_model": "gpt-4o",
        "website": "https://platform.openai.com",
        "oauth": {
            "enabled": True,
            "authorize_url": "https://auth.openai.com/authorize",
            "token_url": "https://auth.openai.com/token",
            "scopes": ["model.request"],
        }
    },
    "gemini": {
        "name": "Google Gemini",
        "class": GeminiProvider,
        "auth_methods": ["api_key", "oauth"],
        "default_model": "gemini-2.5-flash",
        "website": "https://aistudio.google.com",
        "oauth": {
            "enabled": True,
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "scopes": ["https://www.googleapis.com/auth/generative-language"],
        }
    },
    "custom": {
        "name": "Custom / Local (Ollama, vLLM, etc.)",
        "class": CustomProvider,
        "auth_methods": ["api_key"],
        "default_model": "llama3",
        "website": "",
        "oauth": {"enabled": False}
    }
}


class LLMProviderManager:
    """Manages LLM provider connections for companies."""
    
    def __init__(self, db_connection=None):
        self.db = db_connection
    
    def get_provider(self, provider_name: str, config: dict) -> LLMProvider:
        """Create a provider instance from config."""
        provider_info = PROVIDERS.get(provider_name)
        if not provider_info:
            raise ValueError(f"Unknown provider: {provider_name}. Available: {list(PROVIDERS.keys())}")
        
        provider_class = provider_info["class"]
        
        # Decrypt API key if stored encrypted
        api_key = config.get("api_key", "")
        if config.get("encrypted") and api_key:
            api_key = decrypt_key(api_key)
        
        # For OAuth, use the access token as API key
        if config.get("auth_method") == "oauth" and config.get("access_token"):
            api_key = config["access_token"]
            if config.get("token_encrypted"):
                api_key = decrypt_key(api_key)
        
        model = config.get("model", provider_info["default_model"])
        
        kwargs = {"api_key": api_key, "model": model}
        if provider_name == "custom":
            kwargs["base_url"] = config.get("base_url", "http://localhost:11434/v1")
        elif provider_name == "openai" and config.get("base_url"):
            kwargs["base_url"] = config.get("base_url")
        
        return provider_class(**kwargs)
    
    def get_company_provider(self, company_id: str) -> LLMProvider:
        """Get the configured LLM provider for a company."""
        if not self.db:
            # Fallback to default Anthropic with env var
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("No LLM provider configured and ANTHROPIC_API_KEY not set")
            return AnthropicProvider(api_key=api_key)
        
        # Query company's LLM config from database
        from psycopg2.extras import RealDictCursor
        with self.db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT metadata FROM companies WHERE id = %s",
                    (company_id,)
                )
                row = cur.fetchone()
                if not row or not row.get("metadata"):
                    # Fallback to default
                    api_key = os.getenv("ANTHROPIC_API_KEY")
                    return AnthropicProvider(api_key=api_key)
                
                llm_config = row["metadata"].get("llm_provider", {})
                if not llm_config:
                    api_key = os.getenv("ANTHROPIC_API_KEY")
                    return AnthropicProvider(api_key=api_key)
                
                provider_name = llm_config.get("provider", "anthropic")
                return self.get_provider(provider_name, llm_config)
    
    def save_company_provider(self, company_id: str, provider_name: str, config: dict):
        """Save LLM provider config for a company."""
        # Encrypt API key before storing
        if config.get("api_key"):
            config["api_key"] = encrypt_key(config["api_key"])
            config["encrypted"] = True
        
        if config.get("access_token"):
            config["access_token"] = encrypt_key(config["access_token"])
            config["token_encrypted"] = True
        
        config["provider"] = provider_name
        
        if self.db:
            with self.db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE companies 
                           SET metadata = jsonb_set(
                               COALESCE(metadata, '{}'::jsonb), 
                               '{llm_provider}', 
                               %s::jsonb
                           )
                           WHERE id = %s""",
                        (json.dumps(config), company_id)
                    )
                    conn.commit()
    
    @staticmethod
    def list_providers() -> list:
        """List all available providers."""
        result = []
        for pid, pinfo in PROVIDERS.items():
            # Get models from a dummy instance
            try:
                if pid == "anthropic":
                    models = AnthropicProvider(api_key="dummy").get_models()
                elif pid == "openai":
                    models = OpenAIProvider(api_key="dummy").get_models()
                elif pid == "gemini":
                    models = GeminiProvider(api_key="dummy").get_models()
                elif pid == "custom":
                    models = CustomProvider().get_models()
                else:
                    models = []
            except:
                models = []
            
            result.append({
                "id": pid,
                "name": pinfo["name"],
                "auth_methods": pinfo["auth_methods"],
                "models": models,
                "oauth_enabled": pinfo["oauth"].get("enabled", False),
                "website": pinfo["website"],
            })
        return result
