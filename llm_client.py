#!/usr/bin/env python3
"""
Flexible LLM client that auto-detects available API providers.
Supports: Anthropic, Qwen, MiniMax

Usage:
    from llm_client import LLMClient
    client = LLMClient()
    response = client.generate(system_prompt, user_prompt, max_tokens=1800)
"""

import os
import json
import requests
from dotenv import load_dotenv

# Load .env file if it exists (for API keys)
load_dotenv()


class LLMClient:
    """Auto-detects and uses the best available LLM provider."""
    
    def __init__(self):
        self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        self.qwen_key = os.environ.get("QWEN_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
        self.minimax_key = os.environ.get("MINIMAX_API_KEY")
        self.model = None
        self.provider = None
        self._detect_provider()
    
    def _detect_provider(self):
        """Detect available provider in priority order: Qwen > Anthropic > MiniMax.
        Validates key format before selecting."""
        
        # Qwen first (user's current preference) - key format: sk-xxxxx (40+ chars)
        if self.qwen_key and self.qwen_key.strip().startswith("sk-") and len(self.qwen_key.strip()) >= 40:
            self.provider = "qwen"
            self.model = "qwen-plus"
            print(f"[LLM] Using Qwen ({self.model})")
            return
        
        # Anthropic - key format: sk-ant-xxx (100+ chars)
        if self.anthropic_key and self.anthropic_key.strip().startswith("sk-ant-") and len(self.anthropic_key.strip()) >= 100:
            self.provider = "anthropic"
            self.model = "claude-sonnet-4-20240514"
            print(f"[LLM] Using Anthropic ({self.model})")
            return
        
        # MiniMax
        if self.minimax_key and self.minimax_key.strip():
            self.provider = "minimax"
            self.model = "MiniMax-Text-01"
            print(f"[LLM] Using MiniMax ({self.model})")
            return
        
        raise RuntimeError(
            "No valid LLM API key found. "
            f"QWEN: {len(self.qwen_key or '')} chars (need 40+), "
            f"ANTHROPIC: {len(self.anthropic_key or '')} chars (need 100+), "
            f"MINIMAX: {'set' if self.minimax_key else 'not set'}"
        )
    
    def generate(self, system_prompt, user_prompt, max_tokens=1800):
        """Generate text using the detected provider. Falls back to next provider on failure."""
        try:
            if self.provider == "qwen":
                return self._call_qwen(system_prompt, user_prompt, max_tokens)
            elif self.provider == "anthropic":
                return self._call_anthropic(system_prompt, user_prompt, max_tokens)
            elif self.provider == "minimax":
                return self._call_minimax(system_prompt, user_prompt, max_tokens)
            else:
                raise RuntimeError(f"Unknown provider: {self.provider}")
        except Exception as e:
            print(f"[LLM] {self.provider} failed: {e}")
            # Try fallback providers
            return self._try_fallback(system_prompt, user_prompt, max_tokens)
    
    def _try_fallback(self, system_prompt, user_prompt, max_tokens):
        """Try alternative providers when primary fails."""
        fallbacks = []
        
        # Build fallback list based on current provider
        if self.provider != "anthropic" and self.anthropic_key and self.anthropic_key.strip().startswith("sk-ant-"):
            fallbacks.append(("anthropic", "claude-sonnet-4-20240514"))
        if self.provider != "minimax" and self.minimax_key and self.minimax_key.strip():
            fallbacks.append(("minimax", "MiniMax-Text-01"))
        if self.provider != "qwen" and self.qwen_key and self.qwen_key.strip().startswith("sk-"):
            fallbacks.append(("qwen", "qwen-plus"))
        
        for provider, model in fallbacks:
            print(f"[LLM] Trying fallback: {provider} ({model})")
            try:
                if provider == "anthropic":
                    return self._call_anthropic(system_prompt, user_prompt, max_tokens)
                elif provider == "minimax":
                    return self._call_minimax(system_prompt, user_prompt, max_tokens)
                elif provider == "qwen":
                    return self._call_qwen(system_prompt, user_prompt, max_tokens)
            except Exception as e:
                print(f"[LLM] {provider} failed: {e}")
                continue
        
        raise RuntimeError("All LLM providers failed")
    
    def _call_qwen(self, system_prompt, user_prompt, max_tokens):
        """Call Qwen API (DashScope/Alibaba Cloud)."""
        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        headers = {
            "Authorization": f"Bearer {self.qwen_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            },
            "parameters": {
                "max_tokens": max_tokens,
                "temperature": 0.7,
            }
        }
        r = requests.post(url, headers=headers, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        
        # Parse usage stats
        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        print(f"     Tokens: {input_tokens} in / {output_tokens} out")
        
        content = data["output"]["choices"][0]["message"]["content"]
        return content.strip()
    
    def _call_anthropic(self, system_prompt, user_prompt, max_tokens):
        """Call Anthropic Messages API."""
        import anthropic
        claude = anthropic.Anthropic()
        msg = claude.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        u = msg.usage
        cache_read = getattr(u, "cache_read_input_tokens", 0) or 0
        cache_written = getattr(u, "cache_creation_input_tokens", 0) or 0
        cache_note = (f" | cache read {cache_read}" if cache_read else "") + \
                     (f" | cache write {cache_written}" if cache_written else "")
        print(f"     Tokens: {u.input_tokens} in / {u.output_tokens} out{cache_note}")
        return msg.content[0].text.strip()
    
    def _call_minimax(self, system_prompt, user_prompt, max_tokens):
        """Call MiniMax API."""
        url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
        headers = {
            "Authorization": f"Bearer {self.minimax_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }
        r = requests.post(url, headers=headers, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        print(f"     Tokens: {input_tokens} in / {output_tokens} out")
        
        content = data["choices"][0]["message"]["content"]
        return content.strip()


# Convenience function for quick usage
def generate(system_prompt, user_prompt, max_tokens=1800):
    """Quick one-liner: content = generate(system, user)"""
    client = LLMClient()
    return client.generate(system_prompt, user_prompt, max_tokens)


if __name__ == "__main__":
    # Test the client
    client = LLMClient()
    print(f"Provider: {client.provider}, Model: {client.model}")
    
    test_system = "You are a helpful assistant. Respond in 1-2 sentences."
    test_user = "What is luxury fashion?"
    
    response = client.generate(test_system, test_user, max_tokens=100)
    print(f"\nResponse: {response}")
