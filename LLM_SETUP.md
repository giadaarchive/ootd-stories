# LLM Client Setup

The heritage scripts now use a flexible LLM client that supports multiple providers.

## Provider Priority

1. **Qwen** (qwen-plus) - Preferred
2. **Anthropic** (claude-sonnet-4-20240514)
3. **MiniMax** (MiniMax-Text-01)

The client auto-detects which API key is available and valid, then uses that provider. If the primary provider fails, it falls back to the next available one.

## Setup Options

### Option 1: Qwen (Recommended)

Get a Qwen API key from Alibaba Cloud DashScope:
https://dashscope.console.aliyun.com/

Add to `.env`:
```
QWEN_API_KEY=sk-your-key-here
```

### Option 2: Anthropic

Add credits to your Anthropic account:
https://console.anthropic.com/settings/plans

Your current key in `.env` is valid but has low credits.

### Option 3: MiniMax

Get a MiniMax API key and add to `.env`:
```
MINIMAX_API_KEY=your-key-here
```

## Testing

```bash
cd /Users/lisa/lookbook-stories
python3 llm_client.py
```

Expected output:
```
[LLM] Using Qwen (qwen-plus)
Provider: qwen, Model: qwen-plus
     Tokens: X in / Y out
Response: ...
```

## Running Heritage Scripts

Once an API key is configured:

```bash
# Process 1 item as test
python3 heritage.py --recent 1

# Process in batches of 50 (auto-resumes)
python3 heritage.py --limit 50

# Run audit after heritage notes are written
python3 heritage_audit.py --recent 50
```
