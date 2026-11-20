"""Comprehensive acceptance test suite for M18 — RAG Quality, Citation Trust & Assistant Evaluation."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.evaluation.metrics import (
    calculate_abstention_accuracy,
    calculate_answer_completeness,
    calculate_citation_metrics,
    calculate_faithfulness,
    detect_unsupported_claims,
    hit_rate_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from app.models.assistant import Assistant
from app.services.evaluation_service import EvaluationService


def test_retrieval_ranking_mathematical_metrics():
    """Verify precision, recall, MRR, Hit Rate, and NDCG calculations across deterministic edge cases."""
    expected = ["chunk_1", "chunk_2"]

    # 1. Perfect top-2 retrieval
    retrieved_perfect = ["chunk_1", "chunk_2", "chunk_3", "chunk_4", "chunk_5"]
    assert recall_at_k(retrieved_perfect, expected, k=5) == 1.0
    assert precision_at_k(retrieved_perfect, expected, k=2) == 1.0
    assert precision_at_k(retrieved_perfect, expected, k=5) == 0.4  # 2 hits / 5 retrieved
    assert mean_reciprocal_rank(retrieved_perfect, expected) == 1.0  # 1st rank hit
    assert hit_rate_at_k(retrieved_perfect, expected, k=1) == 1.0
    assert ndcg_at_k(retrieved_perfect, expected, k=5) == 1.0

    # 2. Delayed hit (relevant chunk at rank 3)
    retrieved_delayed = ["chunk_noise_1", "chunk_noise_2", "chunk_1", "chunk_noise_3"]
    assert recall_at_k(retrieved_delayed, expected, k=5) == 0.5  # 1 out of 2 expected
    assert precision_at_k(retrieved_delayed, expected, k=5) == 0.25  # 1 hit / 4 items
    assert mean_reciprocal_rank(retrieved_delayed, expected) == round(1.0 / 3.0, 4) or abs(mean_reciprocal_rank(retrieved_delayed, expected) - (1.0 / 3.0)) < 1e-4
    assert hit_rate_at_k(retrieved_delayed, expected, k=2) == 0.0
    assert hit_rate_at_k(retrieved_delayed, expected, k=3) == 1.0

    # 3. Complete miss
    retrieved_miss = ["chunk_x", "chunk_y"]
    assert recall_at_k(retrieved_miss, expected, k=5) == 0.0
    assert precision_at_k(retrieved_miss, expected, k=2) == 0.0
    assert mean_reciprocal_rank(retrieved_miss, expected) == 0.0
    assert hit_rate_at_k(retrieved_miss, expected, k=5) == 0.0
    assert ndcg_at_k(retrieved_miss, expected, k=5) == 0.0


def test_citation_trust_and_unsupported_claim_detection():
    """Verify citation validity, snippet correctness, and groundedness hallucination detection."""
    context = [
        "Company laptops are eligible for replacement every 36 months under standard hardware policy.",
        "Employees traveling on business receive a per diem meal allowance of 75 dollars per day.",
    ]
    retrieved_chunks = [
        {"chunk_id": "cid_laptop", "content": context[0]},
        {"chunk_id": "cid_travel", "content": context[1]},
    ]
    retrieved_ids = ["cid_laptop", "cid_travel"]

    # 1. Grounded answer with valid citation snippet
    grounded_answer = "Laptops are replaced every 36 months. Traveling employees get 75 dollars per day for meals."
    citations_valid = [
        {"chunk_id": "cid_laptop", "document_name": "hardware.pdf", "snippet": "replacement every 36 months"},
        {"chunk_id": "cid_travel", "document_name": "travel.pdf", "snippet": "allowance of 75 dollars"},
    ]
    cit_metrics = calculate_citation_metrics(citations_valid, retrieved_ids, retrieved_chunks=retrieved_chunks)
    assert cit_metrics["citation_presence"] == 1.0
    assert cit_metrics["citation_validity"] == 1.0
    assert cit_metrics["citation_correctness"] == 1.0
    assert cit_metrics["citation_score"] == 1.0

    # Faithfulness of grounded answer should be high
    faithfulness = calculate_faithfulness(grounded_answer, context)
    assert faithfulness >= 0.8
    assert len(detect_unsupported_claims(grounded_answer, context)) == 0

    # 2. Fabricated citation pointing to non-retrieved chunk
    citations_fabricated = [
        {"chunk_id": "cid_phantom_99", "document_name": "ghost.pdf", "snippet": "phantom claim"},
    ]
    cit_metrics_bad = calculate_citation_metrics(citations_fabricated, retrieved_ids, retrieved_chunks=retrieved_chunks)
    assert cit_metrics_bad["citation_validity"] == 0.0
    assert cit_metrics_bad["citation_correctness"] == 0.0

    # 3. Hallucinated answer with unsupported claims
    hallucinated_answer = (
        "Laptops are replaced every 36 months. Furthermore, every employee receives a free Tesla electric vehicle "
        "and unlimited caviar flights to Paris every weekend."
    )
    unsupported = detect_unsupported_claims(hallucinated_answer, context)
    assert len(unsupported) >= 1
    assert any("Tesla" in s or "caviar" in s for s in unsupported)


def test_abstention_and_completeness_metrics():
    """Verify correct refusal on unanswerable and adversarial queries vs answering normal queries."""
    unanswerable_refusal = "I do not have enough information in the provided documentation to answer this question."
    unanswerable_hallucination = "The quantum encryption secret key is secret123."

    assert calculate_abstention_accuracy(unanswerable_refusal, is_unanswerable=True) == 1.0
    assert calculate_abstention_accuracy(unanswerable_hallucination, is_unanswerable=True) == 0.0

    # Answer completeness
    expected_ans = "The per diem is 75 dollars per day."
    full_ans = "According to policy, the per diem allowance is 75 dollars per day."
    incomplete_ans = "Hello, have a good day."

    assert calculate_answer_completeness(full_ans, expected_ans) >= 0.8
    assert calculate_answer_completeness(incomplete_ans, expected_ans) <= 0.2


@pytest.mark.asyncio
async def test_seed_benchmarks_and_tenant_isolation(seed_data: dict, db_session: AsyncSession):
    """Verify that starter benchmarks are seeded, include M18 master items, and enforce tenant isolation."""
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]
    eval_svc_a = EvaluationService(db_session, tenant_a.id, user_id=seed_data["user_a_owner"].id, is_admin=True)
    eval_svc_b = EvaluationService(db_session, tenant_b.id, user_id=seed_data["user_b_owner"].id, is_admin=True)

    # Seed starter benchmarks for Tenant A
    seeded = await eval_svc_a.seed_system_benchmarks()
    assert len(seeded) >= 3

    # Check RAG Quality Master Benchmark exists and has items
    master_ds = next((ds for ds in seeded if "RAG Quality Master" in ds.name), None)
    assert master_ds is not None
    assert len(master_ds.items) == 8

    # Tenant B cannot access Tenant A's private benchmark dataset
    tenant_a_private = await eval_svc_a.create_dataset(
        name="Tenant A Secret Benchmark",
        description="Confidential tests",
        items=[{"question": "What is the secret?", "expected_answer": "Top secret"}],
        is_system=False,
    )
    b_access = await eval_svc_b.get_dataset(tenant_a_private.id)
    assert b_access is None


@pytest.mark.asyncio
async def test_end_to_end_evaluation_run_and_comparison(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    """Verify triggering an evaluation run, collecting comprehensive metrics, and comparing run versions."""
    tenant_a = seed_data["tenant_a"]
    user_a = seed_data["user_a_owner"]
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    eval_svc = EvaluationService(db_session, tenant_a.id, user_id=user_a.id, is_admin=True)

    # 1. Create test assistant
    asst = Assistant(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="RAG Quality Test Bot",
        slug="rag-quality-test-bot",
        system_prompt="You are a helpful assistant.",
        llm_provider="omniroute",
        default_model="auto",
        retrieval_mode="hybrid",
        top_k=5,
    )
    db_session.add(asst)
    await db_session.commit()

    # 2. Seed starter benchmarks
    await eval_svc.seed_system_benchmarks()
    datasets = await eval_svc.list_datasets()
    target_ds = datasets[0]

    # 3. Trigger Evaluation Run 1
    run_resp_1 = await client.post(
        "/api/v1/evaluations/runs",
        json={"assistant_id": str(asst.id), "dataset_id": str(target_ds.id), "eval_type": "deterministic"},
        headers=headers,
    )
    assert run_resp_1.status_code == 201
    run_1_data = run_resp_1.json()
    assert run_1_data["status"] == "COMPLETED"
    summary_1 = run_1_data["metrics_summary"]
    assert "mean_recall_at_5" in summary_1
    assert "mean_faithfulness" in summary_1
    assert "mean_citation_score" in summary_1
    assert "assistant_config" in summary_1
    assert summary_1["assistant_config"]["model"] == "auto"

    # 4. Update Assistant config (e.g. top_k = 10, mode = semantic)
    asst.top_k = 10
    asst.retrieval_mode = "semantic"
    await db_session.commit()

    # 5. Trigger Evaluation Run 2
    run_resp_2 = await client.post(
        "/api/v1/evaluations/runs",
        json={"assistant_id": str(asst.id), "dataset_id": str(target_ds.id), "eval_type": "deterministic"},
        headers=headers,
    )
    assert run_resp_2.status_code == 201
    run_2_data = run_resp_2.json()

    # 6. Compare Run 1 and Run 2
    comp_resp = await client.get(
        f"/api/v1/evaluations/runs/{run_1_data['id']}/compare/{run_2_data['id']}",
        headers=headers,
    )
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()
    assert "metrics_delta" in comp_data
    assert "recall_delta" in comp_data["metrics_delta"]
    assert "assistant_a_config" in comp_data
    assert "assistant_b_config" in comp_data
    assert comp_data["assistant_b_config"]["top_k"] == 10
    assert comp_data["assistant_b_config"]["retrieval_mode"] == "semantic"
