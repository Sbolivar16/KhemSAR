"""Multi-provider LLM client: Ollama (local), Gemini (Google), OpenAI, Anthropic, and deterministic offline."""

from __future__ import annotations

from typing import Any

import httpx

from khemsar.core.config import AISettings


async def list_ollama_models(ollama_url: str = "http://localhost:11434") -> list[str]:
    """Query locally installed Ollama models if the Ollama daemon is running."""
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(f"{ollama_url.rstrip('/')}/api/tags")
            if resp.status_code != 200:
                return []
            return [m.get("name", "") for m in resp.json().get("models", []) if m.get("name")]
    except Exception:
        return []


async def generate_llm_response(
    system_prompt: str,
    user_prompt: str,
    ai_settings: AISettings,
    temperature: float = 0.2,
) -> tuple[str, str]:
    """Return (response_text, provider_used). Falls back cleanly if external provider fails."""
    provider = (ai_settings.provider or "offline").lower()
    api_key = (ai_settings.api_key or "").strip()

    if provider == "ollama":
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(
                    f"{ai_settings.ollama_url.rstrip('/')}/api/chat",
                    json={
                        "model": ai_settings.model or "llama3.1",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "stream": False,
                        "options": {"temperature": temperature},
                    },
                )
                resp.raise_for_status()
                content = resp.json().get("message", {}).get("content", "")
                if content:
                    return content, f"ollama:{ai_settings.model}"
        except Exception:
            pass

    elif provider == "gemini" and api_key:
        try:
            model = ai_settings.model or "gemini-2.0-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(
                    url,
                    params={"key": api_key},
                    json={
                        "system_instruction": {"parts": [{"text": system_prompt}]},
                        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                        "generationConfig": {"temperature": temperature},
                    },
                )
                resp.raise_for_status()
                cands = resp.json().get("candidates", [])
                if cands:
                    parts = cands[0].get("content", {}).get("parts", [])
                    text = "".join(p.get("text", "") for p in parts)
                    if text:
                        return text, f"gemini:{model}"
        except Exception:
            pass

    elif provider == "openai" and api_key:
        try:
            model = ai_settings.model or "gpt-4o-mini"
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "temperature": temperature,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                )
                resp.raise_for_status()
                choices = resp.json().get("choices", [])
                if choices:
                    text = choices[0].get("message", {}).get("content", "")
                    if text:
                        return text, f"openai:{model}"
        except Exception:
            pass

    elif provider == "anthropic" and api_key:
        try:
            model = ai_settings.model or "claude-3-5-sonnet-latest"
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": model,
                        "max_tokens": 1200,
                        "temperature": temperature,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": user_prompt}],
                    },
                )
                resp.raise_for_status()
                blocks = resp.json().get("content", [])
                text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
                if text:
                    return text, f"anthropic:{model}"
        except Exception:
            pass

    return "", "offline"
