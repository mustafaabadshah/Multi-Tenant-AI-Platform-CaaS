# Provider Registry & Capability Architecture (M07)

## Overview
The LLM Provider Registry decouples inference from proprietary APIs. It supports pluggable adapters implementing a uniform interface (`LLMProvider`).

### Supported Providers & Models

| Provider | Adapter Class | Primary Models | Capabilities | Default Endpoint |
|---|---|---|---|---|
| **Groq** | `GroqLLMProvider` | `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `mixtral-8x7b-32768` | Streaming, Tool Calling, JSON Mode, Ultra-fast LPU | `https://api.groq.com/openai/v1` |
| **Anthropic** | `AnthropicLLMProvider` | `claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022`, `claude-3-opus-20240229` | Streaming, Tool Calling, Vision, System Prompt Separation | `https://api.anthropic.com/v1` |
| **Google Gemini** | `GeminiLLMProvider` | `gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-2.0-flash` | Streaming, Tool Calling, Vision, 2M Context Window | `https://generativelanguage.googleapis.com/v1beta` |
| **OpenAI** | `OpenAICompatibleLLMProvider` | `gpt-4o`, `gpt-4o-mini`, `o3-mini` | Streaming, Tool Calling, Vision, JSON Mode | `https://api.openai.com/v1` |
| **OmniRoute** | `OpenAICompatibleLLMProvider` | `auto`, dynamic provider routing | Local AI Gateway routing to best configured provider | `http://localhost:20128/v1` |
| **Mock** | `MockLLMProvider` | `mock-model` | Deterministic offline inference for unit testing & CI | Zero network |

### Capability Filtering
The `ModelCapabilityRegistry` maintains structured model definitions allowing the UI and assistant wizard to dynamically filter available models by:
- `supports_streaming: bool`
- `supports_vision: bool`
- `supports_tools: bool`
- `context_window: int`
