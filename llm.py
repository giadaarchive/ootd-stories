"""
Unified LLM client — routes to Anthropic or OpenRouter based on model name.

Usage:
    from llm import call, MODEL_ALIASES, DEFAULT_MODEL

    text = call(system="...", user="...", max_tokens=1800)
    text = call(system="...", user="...", max_tokens=1800, model="llama")
    text = call(system="...", user="...", max_tokens=1800, model="meta-llama/llama-3.3-70b-instruct")

Routing:
    - Models starting with "claude-" → Anthropic API
    - Everything else             → OpenRouter (OpenAI-compatible)

Environment variables required:
    ANTHROPIC_API_KEY   — always needed
    OPENROUTER_API_KEY  — needed only when using non-Claude models
"""

import os
import anthropic
from openai import OpenAI

# ── Clients (lazy-init to avoid KeyError if key not set) ────────────────────

_anthropic_client = None
_openrouter_client = None


def _anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


def _openrouter():
    global _openrouter_client
    if _openrouter_client is None:
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise EnvironmentError(
                "OPENROUTER_API_KEY not set. Add it to your .env file.\n"
                "Get one at: https://openrouter.ai/keys"
            )
        _openrouter_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=key,
        )
    return _openrouter_client


# ── Model aliases ────────────────────────────────────────────────────────────

DEFAULT_MODEL = "claude-sonnet-4-6"

MODEL_ALIASES = {
    # Anthropic
    "sonnet":    "claude-sonnet-4-6",
    "haiku":     "claude-haiku-4-5-20251001",
    "opus":      "claude-opus-4-7",
    # OpenRouter — open-source
    "llama":     "meta-llama/llama-3.3-70b-instruct",
    "llama70":   "meta-llama/llama-3.3-70b-instruct",
    "llama8":    "meta-llama/llama-3.1-8b-instruct",
    "gemma":     "google/gemma-3-27b-it",
    "mistral":   "mistralai/mistral-large",
    "qwen":      "qwen/qwen-2.5-72b-instruct",
    "deepseek":  "deepseek/deepseek-chat",
}


def resolve(model):
    """Expand short alias to full model ID."""
    return MODEL_ALIASES.get(model, model)


# ── Unified call ─────────────────────────────────────────────────────────────

def call(system, user, max_tokens, model=DEFAULT_MODEL):
    """
    Call the model and return the raw text response.
    Prints token usage. Raises on API error.
    """
    model = resolve(model)

    if model.startswith("claude-"):
        msg = _anthropic().messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        u = msg.usage
        print(f"     Tokens: {u.input_tokens} in / {u.output_tokens} out  [{model}]")
        return msg.content[0].text.strip()

    else:
        resp = _openrouter().chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        )
        u = resp.usage
        print(f"     Tokens: {u.prompt_tokens} in / {u.completion_tokens} out  [{model}]")
        return resp.choices[0].message.content.strip()
