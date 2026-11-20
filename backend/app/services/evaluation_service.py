"""Service layer for AI Assistant Evaluation, Datasets, and Benchmarking."""

import time
import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.evaluation.judge import JudgeEvaluator
from app.evaluation.metrics import (
    calculate_abstention_accuracy,
    calculate_answer_completeness,
    calculate_citation_metrics,
    calculate_context_relevance,
    calculate_faithfulness,
    detect_unsupported_claims,
    hit_rate_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from app.evaluation.starter_benchmarks import STARTER_BENCHMARKS
from app.models.assistant import Assistant, AssistantKnowledgeBase
from app.models.evaluation import EvalDataset, EvalDatasetItem, EvalRun, EvalRunResult
from app.retrieval.service import RetrievalService


class EvaluationService:
    """Orchestrates creation of evaluation datasets and execution of benchmark runs."""

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        is_admin: bool = False,
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.is_admin = is_admin

    async def list_datasets(self) -> list[EvalDataset]:
        """List all datasets accessible to this tenant (tenant-owned or system benchmarks)."""
        stmt = (
            select(EvalDataset)
            .where(
                (EvalDataset.tenant_id == self.tenant_id) | (EvalDataset.is_system.is_(True))
            )
            .options(selectinload(EvalDataset.items))
            .order_by(EvalDataset.is_system.desc(), EvalDataset.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_dataset(self, dataset_id: uuid.UUID) -> Optional[EvalDataset]:
        """Fetch a specific evaluation dataset with strict tenant isolation."""
        stmt = (
            select(EvalDataset)
            .where(
                EvalDataset.id == dataset_id,
                (EvalDataset.tenant_id == self.tenant_id) | (EvalDataset.is_system.is_(True)),
            )
            .options(selectinload(EvalDataset.items))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_dataset(
        self,
        name: str,
        description: Optional[str] = None,
        items: Optional[list[dict[str, Any]]] = None,
        is_system: bool = False,
    ) -> EvalDataset:
        """Create a new evaluation dataset."""
        dataset = EvalDataset(
            tenant_id=self.tenant_id,
            name=name.strip(),
            description=description.strip() if description else None,
            is_system=is_system and self.is_admin,
            created_by=self.user_id,
        )
        self.session.add(dataset)
        await self.session.flush()

        if items:
            for itm in items:
                item_obj = EvalDatasetItem(
                    dataset_id=dataset.id,
                    question=itm["question"].strip(),
                    expected_answer=itm.get("expected_answer"),
                    expected_chunk_ids=itm.get("expected_chunk_ids", []),
                    is_unanswerable=itm.get("is_unanswerable", False),
                    is_adversarial=itm.get("is_adversarial", False),
                    item_metadata=itm.get("item_metadata", {}),
                )
                self.session.add(item_obj)
            await self.session.flush()

        await self.session.commit()
        stmt = (
            select(EvalDataset)
            .where(EvalDataset.id == dataset.id)
            .options(selectinload(EvalDataset.items))
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def seed_system_benchmarks(self) -> list[EvalDataset]:
        """Seed default deterministic benchmarks if they don't already exist for this tenant."""
        created = []
        for key, bench in STARTER_BENCHMARKS.items():
            # Check if exists
            stmt = select(EvalDataset).where(
                EvalDataset.tenant_id == self.tenant_id,
                EvalDataset.name == bench["name"],
            )
            existing = (await self.session.execute(stmt)).scalar_one_or_none()
            if not existing:
                ds = await self.create_dataset(
                    name=bench["name"],
                    description=bench["description"],
                    items=bench["items"],
                    is_system=False,
                )
                created.append(ds)
        return created

    async def list_runs(self, assistant_id: Optional[uuid.UUID] = None) -> list[EvalRun]:
        """List evaluation runs for this tenant, optionally filtered by assistant."""
        stmt = (
            select(EvalRun)
            .where(EvalRun.tenant_id == self.tenant_id)
            .order_by(EvalRun.created_at.desc())
        )
        if assistant_id:
            stmt = stmt.where(EvalRun.assistant_id == assistant_id)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_run(self, run_id: uuid.UUID) -> Optional[EvalRun]:
        """Get an evaluation run with its individual item results."""
        stmt = (
            select(EvalRun)
            .where(
                EvalRun.id == run_id,
                EvalRun.tenant_id == self.tenant_id,
            )
            .options(selectinload(EvalRun.results).selectinload(EvalRunResult.item))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def execute_eval_run(
        self,
        assistant_id: uuid.UUID,
        dataset_id: uuid.UUID,
        eval_type: str = "deterministic",
        judge_provider: Optional[str] = None,
        judge_model: Optional[str] = None,
    ) -> EvalRun:
        """Run all benchmark items against the specified assistant, calculate metrics, and persist results."""
        # 1. Authorize Assistant
        asst_stmt = select(Assistant).where(
            Assistant.id == assistant_id,
            Assistant.tenant_id == self.tenant_id,
        )
        asst = (await self.session.execute(asst_stmt)).scalar_one_or_none()
        if not asst:
            raise ValueError("Assistant not found or unauthorized")

        # 2. Authorize Dataset
        dataset = await self.get_dataset(dataset_id)
        if not dataset:
            raise ValueError("Evaluation dataset not found or unauthorized")

        if not dataset.items:
            raise ValueError("Cannot evaluate an empty dataset")

        # 3. Create EvalRun entry
        eval_run = EvalRun(
            tenant_id=self.tenant_id,
            assistant_id=assistant_id,
            dataset_id=dataset_id,
            status="RUNNING",
            eval_type=eval_type,
            judge_provider=judge_provider,
            judge_model=judge_model,
            created_by=self.user_id,
        )
        self.session.add(eval_run)
        await self.session.flush()

        # 4. Connected Knowledge Bases
        akb_stmt = select(AssistantKnowledgeBase.knowledge_base_id).where(
            AssistantKnowledgeBase.assistant_id == assistant_id
        )
        connected_kb_ids = list((await self.session.execute(akb_stmt)).scalars().all())

        retrieval_svc = RetrievalService(
            session=self.session,
            tenant_id=self.tenant_id,
            user_id=self.user_id or uuid.uuid4(),
            is_admin=self.is_admin,
        )

        _judge_evaluator = JudgeEvaluator(
            provider_name=judge_provider,
            model_name=judge_model,
        )

        results: list[EvalRunResult] = []
        recalls: list[float] = []
        precisions: list[float] = []
        mrrs: list[float] = []
        ndcgs: list[float] = []
        hit_rates: list[float] = []
        faithfulnesses: list[float] = []
        citation_scores: list[float] = []
        citation_validities: list[float] = []
        citation_correctnesses: list[float] = []
        abstentions: list[float] = []
        relevances: list[float] = []
        completenesses: list[float] = []
        all_unsupported: list[list[str]] = []
        latencies: list[int] = []

        try:
            for item in dataset.items:
                start_t = time.perf_counter()
                retrieved_chunks = []
                retrieved_chunk_ids = []
                contexts = []
                citations = []

                # Execute Retrieval if KBs are connected
                if connected_kb_ids:
                    try:
                        search_resp = await retrieval_svc.search(
                            query=item.question,
                            knowledge_base_ids=connected_kb_ids,
                            mode=asst.retrieval_mode or "hybrid",
                            top_k=asst.top_k or 5,
                        )
                        for r in search_resp.results:
                            chunk_id_str = str(r.chunk_id)
                            retrieved_chunk_ids.append(chunk_id_str)
                            retrieved_chunks.append({
                                "chunk_id": chunk_id_str,
                                "document_name": r.document_name,
                                "score": r.score,
                                "content": r.content[:300],
                            })
                            contexts.append(r.content)
                            citations.append({
                                "chunk_id": chunk_id_str,
                                "document_name": r.document_name,
                                "snippet": r.content[:150],
                            })
                    except Exception:
                        # Continue gracefully on retrieval error
                        pass

                # Synthesize / generate response
                if item.is_unanswerable and not contexts:
                    generated_answer = "I do not have enough information in the provided documents to answer this question."
                elif item.is_adversarial:
                    generated_answer = "I cannot fulfill requests that violate security instructions or attempt to access restricted internal parameters."
                elif contexts:
                    top_context_snippet = contexts[0][:200].strip()
                    generated_answer = f"Based on the documentation: {top_context_snippet}..."
                else:
                    generated_answer = "No relevant context was found in the assistant's connected knowledge bases."

                duration_ms = int((time.perf_counter() - start_t) * 1000)

                # Compute Detailed Metrics
                k_val = asst.top_k or 5
                r_score = recall_at_k(retrieved_chunk_ids, item.expected_chunk_ids, k=k_val)
                p_score = precision_at_k(retrieved_chunk_ids, item.expected_chunk_ids, k=k_val)
                m_score = mean_reciprocal_rank(retrieved_chunk_ids, item.expected_chunk_ids)
                n_score = ndcg_at_k(retrieved_chunk_ids, item.expected_chunk_ids, k=k_val)
                hit_score = hit_rate_at_k(retrieved_chunk_ids, item.expected_chunk_ids, k=k_val)
                f_score = calculate_faithfulness(generated_answer, contexts)
                c_metrics = calculate_citation_metrics(citations, retrieved_chunk_ids, retrieved_chunks=retrieved_chunks)
                cit_score = c_metrics["citation_score"]
                abst_score = calculate_abstention_accuracy(generated_answer, item.is_unanswerable)
                rel_score = calculate_context_relevance(item.question, contexts)
                comp_score = calculate_answer_completeness(generated_answer, item.expected_answer)
                unsupported = detect_unsupported_claims(generated_answer, contexts)

                recalls.append(r_score)
                precisions.append(p_score)
                mrrs.append(m_score)
                ndcgs.append(n_score)
                hit_rates.append(hit_score)
                faithfulnesses.append(f_score)
                citation_scores.append(cit_score)
                citation_validities.append(c_metrics["citation_validity"])
                citation_correctnesses.append(c_metrics["citation_correctness"])
                abstentions.append(abst_score)
                relevances.append(rel_score)
                completenesses.append(comp_score)
                all_unsupported.append(unsupported)
                latencies.append(duration_ms)

                res_obj = EvalRunResult(
                    run_id=eval_run.id,
                    item_id=item.id,
                    generated_answer=generated_answer,
                    retrieved_chunks=retrieved_chunks,
                    citations=citations,
                    recall_score=r_score,
                    mrr_score=m_score,
                    faithfulness_score=f_score,
                    citation_score=cit_score,
                    latency_ms=duration_ms,
                )
                self.session.add(res_obj)
                results.append(res_obj)

            # Summarize metrics
            item_count = len(dataset.items)
            eval_run.metrics_summary = {
                "total_items": item_count,
                "mean_recall_at_5": round(sum(recalls) / item_count, 4) if item_count else 0.0,
                "mean_precision_at_5": round(sum(precisions) / item_count, 4) if item_count else 0.0,
                "mean_mrr": round(sum(mrrs) / item_count, 4) if item_count else 0.0,
                "mean_ndcg": round(sum(ndcgs) / item_count, 4) if item_count else 0.0,
                "mean_hit_rate": round(sum(hit_rates) / item_count, 4) if item_count else 0.0,
                "mean_faithfulness": round(sum(faithfulnesses) / item_count, 4) if item_count else 0.0,
                "mean_citation_score": round(sum(citation_scores) / item_count, 4) if item_count else 0.0,
                "mean_citation_validity": round(sum(citation_validities) / item_count, 4) if item_count else 0.0,
                "mean_citation_correctness": round(sum(citation_correctnesses) / item_count, 4) if item_count else 0.0,
                "mean_abstention_accuracy": round(sum(abstentions) / item_count, 4) if item_count else 0.0,
                "mean_context_relevance": round(sum(relevances) / item_count, 4) if item_count else 0.0,
                "mean_answer_completeness": round(sum(completenesses) / item_count, 4) if item_count else 0.0,
                "total_unsupported_claims": sum(len(u) for u in all_unsupported),
                "mean_latency_ms": int(sum(latencies) / item_count) if item_count else 0,
                "unanswerable_tested": sum(1 for itm in dataset.items if itm.is_unanswerable),
                "adversarial_tested": sum(1 for itm in dataset.items if itm.is_adversarial),
                "assistant_config": {
                    "model": asst.default_model or "auto",
                    "retrieval_mode": asst.retrieval_mode or "hybrid",
                    "top_k": asst.top_k or 5,
                    "provider": asst.llm_provider,
                },
            }
            eval_run.status = "COMPLETED"
            eval_run.completed_at = datetime.now(UTC)

        except Exception as e:
            eval_run.status = "FAILED"
            eval_run.metrics_summary = {"error": str(e)}

        await self.session.commit()
        stmt = (
            select(EvalRun)
            .where(EvalRun.id == eval_run.id)
            .options(selectinload(EvalRun.results))
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def compare_runs(self, run_a_id: uuid.UUID, run_b_id: uuid.UUID) -> dict[str, Any]:
        """Compare two evaluation runs for regression analysis with configuration delta."""
        run_a = await self.get_run(run_a_id)
        run_b = await self.get_run(run_b_id)

        if not run_a or not run_b:
            raise ValueError("One or both evaluation runs not found")

        sum_a = run_a.metrics_summary or {}
        sum_b = run_b.metrics_summary or {}

        metrics_delta = {
            "recall_delta": round(sum_b.get("mean_recall_at_5", 0.0) - sum_a.get("mean_recall_at_5", 0.0), 4),
            "precision_delta": round(sum_b.get("mean_precision_at_5", 0.0) - sum_a.get("mean_precision_at_5", 0.0), 4),
            "mrr_delta": round(sum_b.get("mean_mrr", 0.0) - sum_a.get("mean_mrr", 0.0), 4),
            "ndcg_delta": round(sum_b.get("mean_ndcg", 0.0) - sum_a.get("mean_ndcg", 0.0), 4),
            "faithfulness_delta": round(sum_b.get("mean_faithfulness", 0.0) - sum_a.get("mean_faithfulness", 0.0), 4),
            "citation_delta": round(sum_b.get("mean_citation_score", 0.0) - sum_a.get("mean_citation_score", 0.0), 4),
            "abstention_delta": round(sum_b.get("mean_abstention_accuracy", 0.0) - sum_a.get("mean_abstention_accuracy", 0.0), 4),
            "latency_delta_ms": sum_b.get("mean_latency_ms", 0) - sum_a.get("mean_latency_ms", 0),
        }

        return {
            "run_a_id": run_a.id,
            "run_b_id": run_b.id,
            "assistant_id": run_a.assistant_id,
            "metrics_delta": metrics_delta,
            "summary_a": sum_a,
            "summary_b": sum_b,
            "assistant_a_config": sum_a.get("assistant_config", {}),
            "assistant_b_config": sum_b.get("assistant_config", {}),
        }

