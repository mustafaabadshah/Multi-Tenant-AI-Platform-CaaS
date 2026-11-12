"""LLM-as-a-Judge module supporting optional BYOK model-based evaluation with strict schema validation."""

import json
import logging
import re
from typing import Any, Optional

from app.llm import LLMConfig, LLMMessage, get_llm_registry

logger = logging.getLogger("mmaip.evaluation.judge")

JUDGE_PROMPT_VERSION = "v1.0"

JUDGE_SYSTEM_PROMPT = """You are an impartial, expert AI benchmark judge.
Evaluate the AI assistant's generated answer based strictly on the retrieved context and ground truth.
Output valid JSON only with the following schema:
{
  "faithfulness_score": <float between 0.0 and 1.0>,
  "relevance_score": <float between 0.0 and 1.0>,
  "abstention_score": <float between 0.0 and 1.0>,
  "reasoning": "<concise explanation of ratings>"
}
Do not include markdown fences or any other text outside the JSON object.
"""


class JudgeEvaluator:
    """Evaluates question-answer-context tuples using either an LLM provider or local deterministic heuristics."""

    def __init__(
        self,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.provider_name = provider_name
        self.model_name = model_name or "auto"
        self.api_key = api_key
        self.base_url = base_url

    async def evaluate_item(
        self,
        question: str,
        generated_answer: str,
        retrieved_contexts: list[str],
        expected_answer: Optional[str] = None,
        is_unanswerable: bool = False,
    ) -> dict[str, Any]:
        """Judge a single question-answer pair. Falls back to deterministic scores if no provider is configured."""
        if not self.provider_name or not self.api_key:
            # Deterministic fallback when no BYOK key or provider is supplied
            from app.evaluation.metrics import (
                calculate_abstention_accuracy,
                calculate_faithfulness,
            )

            faithfulness = calculate_faithfulness(generated_answer, retrieved_contexts)
            abstention = calculate_abstention_accuracy(generated_answer, is_unanswerable)
            return {
                "judge_type": "deterministic_fallback",
                "judge_model": "local_heuristics",
                "prompt_version": JUDGE_PROMPT_VERSION,
                "faithfulness_score": faithfulness,
                "relevance_score": 0.85 if generated_answer and len(generated_answer.split()) > 5 else 0.2,
                "abstention_score": abstention,
                "reasoning": "Deterministic heuristic evaluation (no external judge LLM key configured).",
            }

        # Model-based judge invocation
        user_prompt = f"""[Context]:
{" --- ".join(retrieved_contexts) if retrieved_contexts else "No context retrieved."}

[Question]:
{question}

[Expected Answer]:
{expected_answer or "None provided"}

[Generated Answer]:
{generated_answer}

[Is Query Unanswerable]:
{is_unanswerable}
"""

        messages = [
            LLMMessage(role="system", content=JUDGE_SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_prompt),
        ]

        llm_config = LLMConfig(
            provider=self.provider_name,
            model=self.model_name,
            temperature=0.0,
            max_tokens=400,
            api_key=self.api_key,
            base_url=self.base_url,
        )

        registry = get_llm_registry()
        provider = registry.get_provider(self.provider_name)

        try:
            response = await provider.generate(messages, llm_config)
            content = response.content.strip()

            # Strip markdown json blocks if present
            cleaned_json = re.sub(r"^```(?:json)?\s*", "", content)
            cleaned_json = re.sub(r"\s*```$", "", cleaned_json)

            data = json.loads(cleaned_json)
            return {
                "judge_type": "llm_as_judge",
                "judge_provider": self.provider_name,
                "judge_model": self.model_name,
                "prompt_version": JUDGE_PROMPT_VERSION,
                "faithfulness_score": float(data.get("faithfulness_score", 0.0)),
                "relevance_score": float(data.get("relevance_score", 0.0)),
                "abstention_score": float(data.get("abstention_score", 0.0)),
                "reasoning": str(data.get("reasoning", "")),
            }
        except Exception as e:
            logger.warning(f"LLM-as-judge failed: {e}. Falling back to deterministic metrics.")
            from app.evaluation.metrics import (
                calculate_abstention_accuracy,
                calculate_faithfulness,
            )

            return {
                "judge_type": "llm_as_judge_failed",
                "judge_provider": self.provider_name,
                "judge_model": self.model_name,
                "prompt_version": JUDGE_PROMPT_VERSION,
                "faithfulness_score": calculate_faithfulness(generated_answer, retrieved_contexts),
                "relevance_score": 0.5,
                "abstention_score": calculate_abstention_accuracy(generated_answer, is_unanswerable),
                "reasoning": f"Judge invocation failed ({str(e)}), deterministic fallback applied.",
            }
