"""Model Capability Registry defining supported models and verified feature parity."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelCapability:
    provider: str
    model_id: str
    display_name: str
    context_window: int
    max_output_tokens: int
    supports_streaming: bool = True
    supports_tools: bool = False
    supports_vision: bool = False
    supports_audio: bool = False
    supports_json_mode: bool = True
    description: str = ""


# Verified model catalog mapping current generation production models
_VERIFIED_MODELS: list[ModelCapability] = [
    # -------------------------------------------------------------------------
    # Groq (High-throughput Llama 3 & Mixtral)
    # -------------------------------------------------------------------------
    ModelCapability(
        provider="groq",
        model_id="llama-3.3-70b-versatile",
        display_name="Llama 3.3 70B Versatile",
        context_window=128000,
        max_output_tokens=32768,
        supports_streaming=True,
        supports_tools=True,
        supports_vision=False,
        supports_json_mode=True,
        description="State-of-the-art open weights model with ultra-fast inference on Groq LPUs.",
    ),
    ModelCapability(
        provider="groq",
        model_id="llama-3.1-8b-instant",
        display_name="Llama 3.1 8B Instant",
        context_window=128000,
        max_output_tokens=8192,
        supports_streaming=True,
        supports_tools=True,
        supports_vision=False,
        supports_json_mode=True,
        description="Extremely low-latency model for rapid Q&A, revision drills, and summarization.",
    ),
    ModelCapability(
        provider="groq",
        model_id="mixtral-8x7b-32768",
        display_name="Mixtral 8x7B (32k)",
        context_window=32768,
        max_output_tokens=4096,
        supports_streaming=True,
        supports_tools=False,
        supports_vision=False,
        supports_json_mode=False,
        description="MoE model balancing speed and long context recall.",
    ),
    # -------------------------------------------------------------------------
    # Anthropic (Claude 3.5 Series)
    # -------------------------------------------------------------------------
    ModelCapability(
        provider="anthropic",
        model_id="claude-3-5-sonnet-20241022",
        display_name="Claude 3.5 Sonnet",
        context_window=200000,
        max_output_tokens=8192,
        supports_streaming=True,
        supports_tools=True,
        supports_vision=True,
        supports_json_mode=True,
        description="Anthropic's flagship intelligence model with superior reasoning and document analysis.",
    ),
    ModelCapability(
        provider="anthropic",
        model_id="claude-3-5-haiku-20241022",
        display_name="Claude 3.5 Haiku",
        context_window=200000,
        max_output_tokens=8192,
        supports_streaming=True,
        supports_tools=True,
        supports_vision=False,
        supports_json_mode=True,
        description="Fastest Claude model for responsive customer support and high-velocity workflows.",
    ),
    ModelCapability(
        provider="anthropic",
        model_id="claude-3-opus-20240229",
        display_name="Claude 3 Opus",
        context_window=200000,
        max_output_tokens=4096,
        supports_streaming=True,
        supports_tools=True,
        supports_vision=True,
        supports_json_mode=True,
        description="Deep contextual understanding for complex research synthesis and policy analysis.",
    ),
    # -------------------------------------------------------------------------
    # Google Gemini (1.5 and 2.0 Flash/Pro)
    # -------------------------------------------------------------------------
    ModelCapability(
        provider="gemini",
        model_id="gemini-1.5-pro",
        display_name="Gemini 1.5 Pro",
        context_window=2000000,
        max_output_tokens=8192,
        supports_streaming=True,
        supports_tools=True,
        supports_vision=True,
        supports_audio=True,
        supports_json_mode=True,
        description="Massive 2M token context window ideal for entire textbooks, video, and audio archives.",
    ),
    ModelCapability(
        provider="gemini",
        model_id="gemini-1.5-flash",
        display_name="Gemini 1.5 Flash",
        context_window=1000000,
        max_output_tokens=8192,
        supports_streaming=True,
        supports_tools=True,
        supports_vision=True,
        supports_audio=False,
        supports_json_mode=True,
        description="Cost-effective, multimodal workhorse for high-frequency knowledge retrieval.",
    ),
    ModelCapability(
        provider="gemini",
        model_id="gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        context_window=1000000,
        max_output_tokens=8192,
        supports_streaming=True,
        supports_tools=True,
        supports_vision=True,
        supports_audio=False,
        supports_json_mode=True,
        description="Next-generation Gemini model built for fast agentic workflows and tool use.",
    ),
    # -------------------------------------------------------------------------
    # OpenAI (GPT-4o & Reasoning Series)
    # -------------------------------------------------------------------------
    ModelCapability(
        provider="openai",
        model_id="gpt-4o",
        display_name="GPT-4o Omnimodal",
        context_window=128000,
        max_output_tokens=4096,
        supports_streaming=True,
        supports_tools=True,
        supports_vision=True,
        supports_json_mode=True,
        description="OpenAI's high-intelligence multimodal model for enterprise applications.",
    ),
    ModelCapability(
        provider="openai",
        model_id="gpt-4o-mini",
        display_name="GPT-4o Mini",
        context_window=128000,
        max_output_tokens=4096,
        supports_streaming=True,
        supports_tools=True,
        supports_vision=True,
        supports_json_mode=True,
        description="Affordable and fast small model suitable for lightweight RAG queries.",
    ),
    ModelCapability(
        provider="openai",
        model_id="o3-mini",
        display_name="o3-mini (Reasoning)",
        context_window=200000,
        max_output_tokens=100000,
        supports_streaming=True,
        supports_tools=True,
        supports_vision=False,
        supports_json_mode=True,
        description="Specialized STEM and coding reasoning model with chain-of-thought processing.",
    ),
    # -------------------------------------------------------------------------
    # OmniRoute (Local AI Gateway)
    # -------------------------------------------------------------------------
    ModelCapability(
        provider="omniroute",
        model_id="auto",
        display_name="OmniRoute Auto Router",
        context_window=128000,
        max_output_tokens=4096,
        supports_streaming=True,
        supports_tools=True,
        supports_vision=False,
        supports_json_mode=True,
        description="Dynamically routes requests to the best available local or configured upstream provider.",
    ),
    # -------------------------------------------------------------------------
    # Mock (Deterministic Offline Testing)
    # -------------------------------------------------------------------------
    ModelCapability(
        provider="mock",
        model_id="mock-model",
        display_name="Deterministic Offline Mock",
        context_window=16384,
        max_output_tokens=2048,
        supports_streaming=True,
        supports_tools=True,
        supports_vision=False,
        supports_json_mode=True,
        description="Zero-network local mock engine for CI/CD test suites and local sandboxing.",
    ),
]


class ModelCapabilityRegistry:
    """Registry providing model lookup and capability filtering."""

    def __init__(self):
        self._models = list(_VERIFIED_MODELS)

    def get_all(self) -> list[ModelCapability]:
        return list(self._models)

    def get_by_provider(self, provider: str) -> list[ModelCapability]:
        p = provider.lower()
        return [m for m in self._models if m.provider.lower() == p]

    def get_model(self, provider: str, model_id: str) -> Optional[ModelCapability]:
        p = provider.lower()
        m_id = model_id.lower()
        for m in self._models:
            if m.provider.lower() == p and m.model_id.lower() == m_id:
                return m
        return None

    def filter_by_capability(
        self,
        streaming: Optional[bool] = None,
        vision: Optional[bool] = None,
        tools: Optional[bool] = None,
    ) -> list[ModelCapability]:
        results = self._models
        if streaming is not None:
            results = [m for m in results if m.supports_streaming == streaming]
        if vision is not None:
            results = [m for m in results if m.supports_vision == vision]
        if tools is not None:
            results = [m for m in results if m.supports_tools == tools]
        return results


_registry_instance: Optional[ModelCapabilityRegistry] = None


def get_model_capability_registry() -> ModelCapabilityRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ModelCapabilityRegistry()
    return _registry_instance


def get_model_capability(model_id: str, provider: Optional[str] = None) -> Optional[ModelCapability]:
    reg = get_model_capability_registry()
    if provider:
        return reg.get_model(provider, model_id)
    m_id = model_id.lower()
    for m in reg.get_all():
        if m.model_id.lower() == m_id:
            return m
    return None


def get_provider_models(provider: str) -> list[ModelCapability]:
    return get_model_capability_registry().get_by_provider(provider)
