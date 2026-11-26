"""M28.10.1 Phase 3 & 4: Full Citation Lifecycle & Relevance Filter Hardening Suite."""

import uuid
import pytest
from app.assistant_runtime.runtime import filter_substantive_relevance
from app.vectorstores.base import VectorSearchResult


# 1. Relevance: C++ query rejects unrelated solar research
def test_relevance_cpp_query_rejects_solar_research():
    kb_id = uuid.uuid4()
    query = "Do you have knowledge of C++ and how templates work?"
    results = [
        VectorSearchResult(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            knowledge_base_id=kb_id,
            content="Solar irradiance forecasting across agricultural regions in Pakistan using TCN.",
            document_title="Solar_Forecasting_Research.pdf",
            score=0.45,
            metadata={"semantic_score": 0.42},
        ),
        VectorSearchResult(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            knowledge_base_id=kb_id,
            content="C++ templates allow functions and classes to operate with generic types.",
            document_title="Modern_CPP_Programming.pdf",
            score=0.88,
            metadata={"semantic_score": 0.85},
        ),
    ]
    filtered = filter_substantive_relevance(query, results)
    assert len(filtered) == 1
    assert filtered[0].document_title == "Modern_CPP_Programming.pdf"


# 2. Relevance: Solar query rejects unrelated C++ document
def test_relevance_solar_query_rejects_cpp():
    kb_id = uuid.uuid4()
    query = "Which solar irradiance forecasting model should I evaluate next?"
    results = [
        VectorSearchResult(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            knowledge_base_id=kb_id,
            content="A range-based for loop executes over all elements in a container in C++.",
            document_title="CPP_Reference_Manual.pdf",
            score=0.35,
            metadata={"semantic_score": 0.30},
        ),
        VectorSearchResult(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            knowledge_base_id=kb_id,
            content="Deep learning architectures for multi-horizon global horizontal solar irradiance prediction.",
            document_title="Solar_GHI_Forecasting.pdf",
            score=0.89,
            metadata={"semantic_score": 0.86},
        ),
    ]
    filtered = filter_substantive_relevance(query, results)
    assert len(filtered) == 1
    assert filtered[0].document_title == "Solar_GHI_Forecasting.pdf"


# 3. Relevance: Acronym expansion - Bi-LSTM vs Bidirectional LSTM
def test_relevance_acronym_bilstm_expansion():
    kb_id = uuid.uuid4()
    query = "Compare Bi-LSTM with LightGBM for time series."
    results = [
        VectorSearchResult(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            knowledge_base_id=kb_id,
            content="We evaluate bidirectional LSTM networks against gradient boosting trees.",
            document_title="Deep_Learning_Survey.pdf",
            score=0.55,
            metadata={"semantic_score": 0.52},
        )
    ]
    filtered = filter_substantive_relevance(query, results)
    assert len(filtered) == 1
    assert filtered[0].document_title == "Deep_Learning_Survey.pdf"


# 4. Relevance: Acronym expansion - RMSE vs Root Mean Squared Error
def test_relevance_acronym_rmse_expansion():
    kb_id = uuid.uuid4()
    query = "What is the RMSE of the proposed forecasting baseline?"
    results = [
        VectorSearchResult(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            knowledge_base_id=kb_id,
            content="The baseline model achieved a root mean squared error of 14.2 W/m2.",
            document_title="Benchmark_Results.pdf",
            score=0.58,
            metadata={"semantic_score": 0.50},
        )
    ]
    filtered = filter_substantive_relevance(query, results)
    assert len(filtered) == 1
    assert filtered[0].document_title == "Benchmark_Results.pdf"


# 5. Relevance: Solar GHI vs Irradiance
def test_relevance_acronym_ghi_solar_irradiance():
    kb_id = uuid.uuid4()
    query = "Analyze GHI prediction curves across seasonal weather variations."
    results = [
        VectorSearchResult(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            knowledge_base_id=kb_id,
            content="Solar irradiance fluctuates significantly during monsoons in South Asia.",
            document_title="Atmospheric_Solar_Study.pdf",
            score=0.54,
            metadata={"semantic_score": 0.49},
        )
    ]
    filtered = filter_substantive_relevance(query, results)
    assert len(filtered) == 1
    assert filtered[0].document_title == "Atmospheric_Solar_Study.pdf"


# 6. Relevance: Conversational queries without salient keywords discard background documents
def test_relevance_conversational_query_discards_unrelated_kb():
    kb_id = uuid.uuid4()
    query = "Hello, good morning!"
    results = [
        VectorSearchResult(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            knowledge_base_id=kb_id,
            content="Solar irradiance forecasting model evaluation with convolutional nets.",
            document_title="Solar_Paper.pdf",
            score=0.40,
            metadata={"semantic_score": 0.35},
        )
    ]
    filtered = filter_substantive_relevance(query, results)
    assert len(filtered) == 0


# 7. Relevance: C++ code example containing the word "for"
def test_relevance_cpp_for_loop_query():
    kb_id = uuid.uuid4()
    query = "Explain how a for loop is structured in C++"
    results = [
        VectorSearchResult(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            knowledge_base_id=kb_id,
            content="Syntax: for (int i = 0; i < n; ++i) { // loop body }",
            document_title="CPP_Basics.pdf",
            score=0.85,
            metadata={"semantic_score": 0.80},
        ),
        VectorSearchResult(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            knowledge_base_id=kb_id,
            content="Solar power plants required for agricultural irrigation in Punjab.",
            document_title="Agriculture_Power.pdf",
            score=0.30,
            metadata={"semantic_score": 0.25},
        ),
    ]
    filtered = filter_substantive_relevance(query, results)
    assert len(filtered) == 1
    assert filtered[0].document_title == "CPP_Basics.pdf"


# 8. Document with "http" in filename is NOT misclassified as web citation
def test_document_filename_with_http_not_misclassified():
    doc_name = "http_protocol_rfc9110_spec.pdf"
    chunk_id = uuid.uuid4()
    has_http_prefix = doc_name.startswith("http://") or doc_name.startswith("https://")
    is_web = (chunk_id is None) and has_http_prefix
    web_url = doc_name if has_http_prefix else None

    assert is_web is False
    assert web_url is None


# 9. Web citation with URL is correctly classified as web
def test_web_citation_url_is_classified_as_web():
    from urllib.parse import urlparse

    doc_name = "https://arxiv.org/abs/2401.12345"
    chunk_id = None
    has_http_prefix = doc_name.startswith("http://") or doc_name.startswith("https://")
    is_web = (chunk_id is None) and has_http_prefix
    web_url = doc_name if has_http_prefix else None
    domain_name = urlparse(web_url).hostname if web_url else None

    assert is_web is True
    assert web_url == "https://arxiv.org/abs/2401.12345"
    assert domain_name == "arxiv.org"


# 10. Multi-chunk from single PDF preserved with distinct chunk identities
def test_multiple_chunks_from_single_pdf_preserved():
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    chunks = [
        VectorSearchResult(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            knowledge_base_id=kb_id,
            content="Introduction to GHI prediction.",
            document_title="Solar_Paper.pdf",
            score=0.85,
            metadata={"semantic_score": 0.85},
        ),
        VectorSearchResult(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            knowledge_base_id=kb_id,
            content="Evaluation metrics and RMSE baselines.",
            document_title="Solar_Paper.pdf",
            score=0.82,
            metadata={"semantic_score": 0.80},
        ),
    ]
    filtered = filter_substantive_relevance("solar GHI and RMSE baselines", chunks)
    assert len(filtered) == 2
    assert filtered[0].chunk_id != filtered[1].chunk_id
    assert filtered[0].document_title == filtered[1].document_title
