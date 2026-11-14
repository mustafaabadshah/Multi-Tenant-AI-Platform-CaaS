import json
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.observability.policy import (
    categorize_error,
    sanitize_preview,
    sanitize_value,
)
from app.observability.pricing import estimate_request_cost

logger = logging.getLogger("mmaip.observability")


@dataclass
class Span:
    """Individual execution unit in an assistant request lifecycle."""

    span_id: str
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "RUNNING"  # RUNNING, COMPLETED, FAILED, CANCELLED
    attributes: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def finish(self, status: str = "COMPLETED", error: Optional[str] = None):
        self.end_time = time.perf_counter()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.status = status
        if error:
            self.error = sanitize_value(error)

    def set_attribute(self, key: str, value: Any):
        self.attributes[key] = sanitize_value(value)


@dataclass
class AssistantTrace:
    """Complete trace capturing the lifecycle of an assistant inference request."""

    trace_id: str
    tenant_id: str
    assistant_id: str
    assistant_name: str
    conversation_id: Optional[str] = None
    traffic_type: str = "internal"  # internal, public, embed, developer
    status: str = "RUNNING"  # RUNNING, COMPLETED, FAILED, CANCELLED
    error_category: Optional[str] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    start_time: float = field(default_factory=time.perf_counter)
    end_time: Optional[float] = None
    total_duration_ms: Optional[float] = None
    ttft_ms: Optional[float] = None  # Time To First Token in ms
    provider: Optional[str] = None
    model: Optional[str] = None
    credential_source: str = "byok"
    retrieval_mode: Optional[str] = None
    retrieved_chunk_count: int = 0
    citation_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    is_token_estimated: bool = True
    estimated_cost_usd: Optional[float] = None
    pricing_status: str = "unknown"
    retrieval_metadata: Optional[dict[str, Any]] = None
    input_preview: Optional[str] = None
    output_preview: Optional[str] = None
    has_preview: bool = False
    spans: list[Span] = field(default_factory=list)

    def start_span(self, name: str) -> Span:
        span = Span(
            span_id=uuid.uuid4().hex[:12],
            name=name,
            start_time=time.perf_counter(),
        )
        self.spans.append(span)
        return span

    def mark_first_token(self):
        if self.ttft_ms is None:
            self.ttft_ms = round((time.perf_counter() - self.start_time) * 1000, 2)

    def set_previews(
        self,
        user_input: Optional[str] = None,
        output_text: Optional[str] = None,
        max_length: int = 250,
    ):
        """Sanitize and set input/output previews if permitted by policy."""
        if user_input:
            self.input_preview = sanitize_preview(user_input, max_length=max_length)
        if output_text:
            self.output_preview = sanitize_preview(output_text, max_length=max_length)
        self.has_preview = bool(self.input_preview or self.output_preview)

    def finish(self, status: str = "COMPLETED", error: Optional[Any] = None):
        """Finalize the trace with accurate timing, status, cost, and error categorization."""
        self.end_time = time.perf_counter()
        self.total_duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.status = status

        if error:
            cat, summary = categorize_error(error)
            self.error_category = cat
            self.error = summary
            if status == "COMPLETED":
                self.status = "FAILED"

        # Calculate estimated cost if provider/model are present
        cost, p_status = estimate_request_cost(
            provider=self.provider,
            model=self.model,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )
        self.estimated_cost_usd = cost
        self.pricing_status = p_status

        # Update in-memory tracer
        try:
            if _global_tracer:
                _global_tracer.save_state()
        except Exception:
            pass

    def to_dict(self, mask_previews: bool = False) -> dict[str, Any]:
        """Serialize trace for API responses, respecting preview masking."""
        data = {
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "assistant_id": self.assistant_id,
            "assistant_name": self.assistant_name,
            "conversation_id": self.conversation_id,
            "traffic_type": self.traffic_type,
            "status": self.status,
            "error_category": self.error_category,
            "error": self.error,
            "created_at": self.created_at,
            "total_duration_ms": self.total_duration_ms,
            "ttft_ms": self.ttft_ms,
            "provider": self.provider,
            "model": self.model,
            "credential_source": self.credential_source,
            "retrieval_mode": self.retrieval_mode,
            "retrieved_chunk_count": self.retrieved_chunk_count,
            "citation_count": self.citation_count,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "is_token_estimated": self.is_token_estimated,
            "estimated_cost_usd": self.estimated_cost_usd,
            "pricing_status": self.pricing_status,
            "retrieval_metadata": self.retrieval_metadata,
            "input_preview": None if mask_previews else self.input_preview,
            "output_preview": None if mask_previews else self.output_preview,
            "has_preview": self.has_preview and not mask_previews,
            "span_count": len(self.spans),
            "spans": [
                {
                    "span_id": s.span_id,
                    "name": s.name,
                    "duration_ms": s.duration_ms,
                    "status": s.status,
                    "attributes": s.attributes,
                    "error": s.error,
                }
                for s in self.spans
            ],
        }
        return data


class ObservabilityTracer:
    """Thread-safe, multi-tenant trace collector maintaining in-memory ring buffers and backing durable DB storage."""

    def __init__(self, max_traces_per_tenant: int = 500):
        self._max_traces = max_traces_per_tenant
        self._lock = threading.Lock()
        self._tenant_traces: dict[str, deque[AssistantTrace]] = {}
        self._trace_lookup: dict[str, AssistantTrace] = {}
        self._load_from_disk()

    def _get_storage_path(self) -> Path:
        for candidate in [Path("backend/data"), Path("data"), Path(".")]:
            if candidate.exists() and (candidate / "mmaip_dev.db").exists():
                return candidate / "observability_traces.json"
        p = Path("backend/data")
        p.mkdir(parents=True, exist_ok=True)
        return p / "observability_traces.json"

    def _load_from_disk(self):
        try:
            path = self._get_storage_path()
            if not path.exists():
                return
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return
            for d in data:
                tr = AssistantTrace(
                    trace_id=d["trace_id"],
                    tenant_id=d["tenant_id"],
                    assistant_id=d["assistant_id"],
                    assistant_name=d.get("assistant_name", "Assistant"),
                    conversation_id=d.get("conversation_id"),
                    traffic_type=d.get("traffic_type", "internal"),
                )
                tr.status = d.get("status", "COMPLETED")
                tr.error_category = d.get("error_category")
                tr.created_at = d.get("created_at", "")
                tr.total_duration_ms = d.get("total_duration_ms")
                tr.ttft_ms = d.get("ttft_ms")
                tr.provider = d.get("provider")
                tr.model = d.get("model")
                tr.credential_source = d.get("credential_source", "byok")
                tr.retrieval_mode = d.get("retrieval_mode")
                tr.retrieved_chunk_count = d.get("retrieved_chunk_count", 0)
                tr.citation_count = d.get("citation_count", 0)
                tr.input_tokens = d.get("input_tokens", 0)
                tr.output_tokens = d.get("output_tokens", 0)
                tr.total_tokens = d.get("total_tokens", 0)
                tr.is_token_estimated = d.get("is_token_estimated", True)
                tr.estimated_cost_usd = d.get("estimated_cost_usd")
                tr.pricing_status = d.get("pricing_status", "unknown")
                tr.retrieval_metadata = d.get("retrieval_metadata")
                tr.input_preview = d.get("input_preview")
                tr.output_preview = d.get("output_preview")
                tr.has_preview = d.get("has_preview", False)
                tr.error = d.get("error")

                for s in d.get("spans", []):
                    span = Span(
                        span_id=s.get("span_id", ""),
                        name=s.get("name", ""),
                        start_time=0.0,
                    )
                    span.duration_ms = s.get("duration_ms")
                    span.status = s.get("status", "COMPLETED")
                    span.attributes = s.get("attributes", {})
                    span.error = s.get("error")
                    tr.spans.append(span)

                tid = str(tr.tenant_id)
                if tid not in self._tenant_traces:
                    self._tenant_traces[tid] = deque(maxlen=self._max_traces)
                self._tenant_traces[tid].append(tr)
                self._trace_lookup[tr.trace_id] = tr
        except Exception as e:
            logger.warning(f"Failed to load persisted observability traces: {e}")

    def save_state(self):
        """Serialize current traces to disk safely."""
        with self._lock:
            try:
                path = self._get_storage_path()
                path.parent.mkdir(parents=True, exist_ok=True)
                all_traces = []
                for tid, dq in self._tenant_traces.items():
                    for tr in dq:
                        all_traces.append(tr.to_dict())
                if len(all_traces) > 1000:
                    all_traces = all_traces[-1000:]
                tmp_path = path.with_suffix(".tmp")
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(all_traces, f, indent=2)
                tmp_path.replace(path)
            except Exception as e:
                logger.warning(f"Failed to persist observability traces to disk: {e}")

    def start_trace(
        self,
        tenant_id: str | uuid.UUID,
        assistant_id: str | uuid.UUID,
        assistant_name: str,
        conversation_id: Optional[str | uuid.UUID] = None,
        traffic_type: str = "internal",
    ) -> AssistantTrace:
        """Initialize and register a new AssistantTrace."""
        trace = AssistantTrace(
            trace_id=f"tr_{uuid.uuid4().hex[:16]}",
            tenant_id=str(tenant_id),
            assistant_id=str(assistant_id) if assistant_id else "",
            assistant_name=assistant_name,
            conversation_id=str(conversation_id) if conversation_id else None,
            traffic_type=traffic_type,
        )

        with self._lock:
            tid = str(tenant_id)
            if tid not in self._tenant_traces:
                self._tenant_traces[tid] = deque(maxlen=self._max_traces)

            if len(self._tenant_traces[tid]) == self._max_traces:
                oldest = self._tenant_traces[tid][0]
                self._trace_lookup.pop(oldest.trace_id, None)

            self._tenant_traces[tid].append(trace)
            self._trace_lookup[trace.trace_id] = trace

        return trace

    def get_trace(self, trace_id: str, tenant_id: str | uuid.UUID) -> Optional[AssistantTrace]:
        """Fetch a specific trace ensuring tenant isolation."""
        with self._lock:
            trace = self._trace_lookup.get(trace_id)
            if trace and trace.tenant_id == str(tenant_id):
                return trace
            return None

    def list_traces(
        self,
        tenant_id: str | uuid.UUID,
        assistant_id: Optional[str | uuid.UUID] = None,
        status: Optional[str] = None,
        traffic_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[AssistantTrace]:
        """List traces for a tenant in reverse chronological order from in-memory cache."""
        with self._lock:
            traces_deque = self._tenant_traces.get(str(tenant_id))
            if not traces_deque:
                return []

            results = []
            for tr in reversed(traces_deque):
                if assistant_id and tr.assistant_id != str(assistant_id):
                    continue
                if status and tr.status != status:
                    continue
                if traffic_type and tr.traffic_type != traffic_type:
                    continue
                results.append(tr)
                if len(results) >= limit:
                    break

            return results

    def get_metrics_summary(self, tenant_id: str | uuid.UUID) -> dict[str, Any]:
        """Compute comprehensive observability metrics across recent traces."""
        with self._lock:
            traces = list(self._tenant_traces.get(str(tenant_id), []))

        total_requests = len(traces)
        if total_requests == 0:
            return {
                "total_requests": 0,
                "error_rate": 0.0,
                "avg_latency_ms": 0.0,
                "p50_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "p99_latency_ms": 0.0,
                "avg_ttft_ms": 0.0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
                "by_status": {},
                "by_traffic_type": {},
                "by_provider": {},
                "by_error_category": {},
            }

        completed_latencies = [t.total_duration_ms for t in traces if t.total_duration_ms is not None]
        ttfts = [t.ttft_ms for t in traces if t.ttft_ms is not None]
        errors = sum(1 for t in traces if t.status in ("FAILED", "CANCELLED"))
        tokens = sum(t.total_tokens for t in traces)
        total_cost = sum(t.estimated_cost_usd for t in traces if t.estimated_cost_usd is not None)

        completed_latencies.sort()
        n = len(completed_latencies)
        p50_val = completed_latencies[int(n * 0.50)] if n else 0.0
        p95_val = completed_latencies[min(int(n * 0.95), n - 1)] if n else 0.0
        p99_val = completed_latencies[min(int(n * 0.99), n - 1)] if n else 0.0

        by_status: dict[str, int] = {}
        by_traffic: dict[str, int] = {}
        by_provider: dict[str, int] = {}
        by_error_cat: dict[str, int] = {}

        for t in traces:
            by_status[t.status] = by_status.get(t.status, 0) + 1
            by_traffic[t.traffic_type] = by_traffic.get(t.traffic_type, 0) + 1
            prov = t.provider or "unknown"
            by_provider[prov] = by_provider.get(prov, 0) + 1
            if t.error_category:
                by_error_cat[t.error_category] = by_error_cat.get(t.error_category, 0) + 1

        return {
            "total_requests": total_requests,
            "error_rate": round(errors / total_requests, 4),
            "avg_latency_ms": round(sum(completed_latencies) / n, 2) if n else 0.0,
            "p50_latency_ms": round(p50_val, 2),
            "p95_latency_ms": round(p95_val, 2),
            "p99_latency_ms": round(p99_val, 2),
            "avg_ttft_ms": round(sum(ttfts) / len(ttfts), 2) if ttfts else 0.0,
            "total_tokens": tokens,
            "estimated_cost_usd": round(total_cost, 4),
            "by_status": by_status,
            "by_traffic_type": by_traffic,
            "by_provider": by_provider,
            "by_error_category": by_error_cat,
        }

    async def persist_to_database(self, trace: AssistantTrace, session: Optional[AsyncSession] = None):
        """Asynchronously persist an AssistantTrace to the request_traces table."""
        from app.database.session import async_session_maker
        from app.models.trace import RequestTrace

        async def _write(db: AsyncSession):
            asst_uuid = None
            if trace.assistant_id:
                try:
                    asst_uuid = uuid.UUID(trace.assistant_id)
                except ValueError:
                    pass

            conv_uuid = None
            if trace.conversation_id:
                try:
                    conv_uuid = uuid.UUID(trace.conversation_id)
                except ValueError:
                    pass

            completed_dt = None
            if trace.status in ("COMPLETED", "FAILED", "CANCELLED"):
                completed_dt = datetime.now(UTC)

            spans_json = [
                {
                    "span_id": s.span_id,
                    "name": s.name,
                    "duration_ms": s.duration_ms,
                    "status": s.status,
                    "attributes": s.attributes,
                    "error": s.error,
                }
                for s in trace.spans
            ]

            from sqlalchemy import select

            stmt = select(RequestTrace).where(RequestTrace.trace_id == trace.trace_id)
            existing = (await db.execute(stmt)).scalar_one_or_none()
            if existing:
                existing.status = trace.status
                existing.error_category = trace.error_category
                existing.error_message = trace.error
                existing.total_duration_ms = trace.total_duration_ms
                existing.ttft_ms = trace.ttft_ms
                existing.input_tokens = trace.input_tokens
                existing.output_tokens = trace.output_tokens
                existing.total_tokens = trace.total_tokens
                existing.is_token_estimated = trace.is_token_estimated
                existing.estimated_cost_usd = trace.estimated_cost_usd
                existing.pricing_status = trace.pricing_status
                existing.spans_data = spans_json
                existing.retrieval_metadata = trace.retrieval_metadata
                existing.input_preview = trace.input_preview
                existing.output_preview = trace.output_preview
                existing.has_preview = trace.has_preview
                existing.completed_at = completed_dt
            else:
                record = RequestTrace(
                    trace_id=trace.trace_id,
                    tenant_id=uuid.UUID(trace.tenant_id),
                    assistant_id=asst_uuid,
                    assistant_name=trace.assistant_name or "Assistant",
                    conversation_id=conv_uuid,
                    traffic_type=trace.traffic_type,
                    status=trace.status,
                    error_category=trace.error_category,
                    error_message=trace.error,
                    provider=trace.provider,
                    model=trace.model,
                    credential_source=trace.credential_source,
                    retrieval_mode=trace.retrieval_mode,
                    retrieved_chunk_count=trace.retrieved_chunk_count,
                    citation_count=trace.citation_count,
                    input_tokens=trace.input_tokens,
                    output_tokens=trace.output_tokens,
                    total_tokens=trace.total_tokens,
                    is_token_estimated=trace.is_token_estimated,
                    estimated_cost_usd=trace.estimated_cost_usd,
                    pricing_status=trace.pricing_status,
                    total_duration_ms=trace.total_duration_ms,
                    ttft_ms=trace.ttft_ms,
                    spans_data=spans_json,
                    retrieval_metadata=trace.retrieval_metadata,
                    input_preview=trace.input_preview,
                    output_preview=trace.output_preview,
                    has_preview=trace.has_preview,
                    completed_at=completed_dt,
                )
                db.add(record)
            await db.commit()

        try:
            if session:
                await _write(session)
            else:
                async with async_session_maker() as new_session:
                    await _write(new_session)
        except Exception as e:
            logger.error(f"Failed to persist request trace {trace.trace_id} to database: {e}")
            if session:
                try:
                    await session.rollback()
                except Exception:
                    pass


# Global singleton tracer
_global_tracer = ObservabilityTracer()


def get_tracer() -> ObservabilityTracer:
    """Access the platform observability tracer."""
    return _global_tracer
