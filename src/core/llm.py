# Runtime LLM/RAG logic (clients, chains)
import os
import json
from typing import List, Dict, Any, Optional
import anthropic
import requests

# Local Ollama model configuration
# Use detected local tag if present; fallback to generic name
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:latest")

# Use a recent stable model. 
# Sonnet 3.5 is excellent for this type of complex reasoning + formatting task.
DEFAULT_MODEL = "claude-3-5-sonnet-20240620"

def get_llm_client(model: str = DEFAULT_MODEL) -> anthropic.Anthropic:
    """
    Factory function to return an authenticated Anthropic client.
    Reads ANTHROPIC_API_KEY from environment variables by default.
    """
    try:
        # The client automatically looks for "ANTHROPIC_API_KEY" in env
        return anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
        )
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Anthropic client: {e}")


def call_ollama_json(prompt: str, *, model: str = DEFAULT_OLLAMA_MODEL, system: Optional[str] = None, timeout: int = 6000) -> str:
    """Call local Ollama chat endpoint and return raw text response.

    Expects Ollama running at http://localhost:11434. Uses the /api/chat endpoint
    for better instruction adherence. Ensures streaming disabled for simpler parsing.

    Parameters:
        prompt: User content to send.
        model: Ollama model name/tag (configurable via OLLAMA_MODEL env var).
        system: Optional system instruction string.
        timeout: Request timeout seconds.

    Returns:
        The assistant message content (string).
    """
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    # Normalize any accidental newlines/spaces
    base_url = base_url.strip()
    # Prefer /api/chat; fallback to /api/generate if chat not supported by local version
    chat_url = f"{base_url.rstrip('/')}/api/chat"
    generate_url = f"{base_url.rstrip('/')}/api/generate"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        # Provide a simple JSON biasing instruction if system missing
        # (Some models follow this better when repeated)
        "options": {
            "temperature": 0.0
        }
    }
    try:
        resp = requests.post(chat_url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        message = data.get("message", {})
        content = message.get("content")
        if content:
            return content
    except requests.RequestException:
        # Fallback if /api/chat not available (older Ollama or network issue)
        gen_payload = {
            "model": model,
            "prompt": f"{system or ''}\n\n{prompt}",
            "stream": False,
            "options": {"temperature": 0.0}
        }
        try:
            resp2 = requests.post(generate_url, json=gen_payload, timeout=timeout)
            resp2.raise_for_status()
            data2 = resp2.json()
            return data2.get("response", "")
        except requests.RequestException as e2:
            raise RuntimeError(f"Ollama request failed for both /api/chat and /api/generate: {e2}")
    return ""


def extract_program_matches(raw_text: str) -> List[str]:
    """Extract program ID list from raw model output.

    Accepts two formats:
      1. Pure JSON list: ["prog-1", "prog-2"]
      2. Object with key 'matches': {"matches": ["prog-1", ...]}

    Fallback: attempt bracket slice for list; return [] on failure.
    """
    raw_text = raw_text.strip()
    try:
        # Prefer object parsing first
        if raw_text.startswith('{'):
            obj = json.loads(raw_text)
            if isinstance(obj, dict):
                matches = obj.get("matches")
                if isinstance(matches, list):
                    return [m for m in matches if isinstance(m, str)]
        # Try direct list
        if raw_text.startswith('['):
            lst = json.loads(raw_text)
            if isinstance(lst, list):
                return [m for m in lst if isinstance(m, str)]
        # Bracket slice fallback
        start = raw_text.find('[')
        end = raw_text.rfind(']')
        if start != -1 and end != -1 and end > start:
            fragment = raw_text[start:end+1]
            lst = json.loads(fragment)
            if isinstance(lst, list):
                return [m for m in lst if isinstance(m, str)]
    except Exception:
        pass
    return []

