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
import sys
import anthropic
from openai import OpenAI

# ── Cost tracking (backend only — printed to stderr, never reaches frontend) ──

_COST_PER_MILLION = {
    # Anthropic
    "claude-sonnet-4-6":        {"in": 3.00,   "out": 15.00},
    "claude-haiku-4-5-20251001":{"in": 0.25,   "out": 1.25},
    "claude-opus-4-7":          {"in": 15.00,  "out": 75.00},
    # OpenRouter — open-source
    "qwen/qwen-2.5-72b-instruct":     {"in": 0.36, "out": 0.36},
    "qwen/qwen2.5-vl-72b-instruct":   {"in": 0.25, "out": 0.25},
    "meta-llama/llama-3.3-70b-instruct": {"in": 0.10, "out": 0.10},
    "deepseek/deepseek-chat":          {"in": 0.14, "out": 0.28},
    "mistralai/mistral-large":         {"in": 2.00, "out": 6.00},
    "google/gemma-3-27b-it":           {"in": 0.10, "out": 0.20},
}

_session_cost = {"usd": 0.0, "calls": 0}


def _log_cost(model, tokens_in, tokens_out):
    pricing = _COST_PER_MILLION.get(model, {"in": 0.0, "out": 0.0})
    cost = (tokens_in * pricing["in"] + tokens_out * pricing["out"]) / 1_000_000
    _session_cost["usd"] += cost
    _session_cost["calls"] += 1
    print(f"     Cost: ${cost:.5f}  (session total: ${_session_cost['usd']:.4f}, {_session_cost['calls']} calls)", file=sys.stderr)


def session_cost():
    """Return current session cost dict."""
    return dict(_session_cost)

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
        _log_cost(model, u.input_tokens, u.output_tokens)
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
        _log_cost(model, u.prompt_tokens, u.completion_tokens)
        return resp.choices[0].message.content.strip()


def call_vision(system, user_text, image_urls, max_tokens, model=DEFAULT_MODEL):
    """
    Call a vision-capable model with text + images.
    image_urls: list of publicly accessible image URL strings.
    Only supported on OpenRouter vision models (e.g. qwen2.5-vl-72b-instruct).
    """
    model = resolve(model)

    content = [{"type": "text", "text": user_text}]
    for url in image_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})

    if model.startswith("claude-"):
        # Anthropic multimodal format
        blocks = [{"type": "text", "text": user_text}]
        for url in image_urls:
            blocks.append({
                "type": "image",
                "source": {"type": "url", "url": url},
            })
        msg = _anthropic().messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": blocks}],
        )
        u = msg.usage
        print(f"     Tokens: {u.input_tokens} in / {u.output_tokens} out  [{model}]  [{len(image_urls)} images]")
        _log_cost(model, u.input_tokens, u.output_tokens)
        return msg.content[0].text.strip()

    else:
        import time
        for attempt in range(3):
            try:
                resp = _openrouter().chat.completions.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user",   "content": content},
                    ],
                )
                u = resp.usage
                print(f"     Tokens: {u.prompt_tokens} in / {u.completion_tokens} out  [{model}]  [{len(image_urls)} images]")
                _log_cost(model, u.prompt_tokens, u.completion_tokens)
                return resp.choices[0].message.content.strip()
            except Exception as e:
                if attempt < 2:
                    print(f"     [retry {attempt+1}] vision call error: {e}")
                    time.sleep(3)
                else:
                    print(f"     [fail] vision call failed after 3 attempts: {e}")
                    return ""
