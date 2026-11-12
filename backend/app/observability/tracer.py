import json
import logging
import re
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("mmaip.observability")


def sanitize_value(val: Any) -> Any:
    """Recursively redact sensitive tokens, passwords, and API keys from telemetry attributes."""
    if isinstance(val, str):
        val = re.sub(r"(sk-[a-zA-Z0-9_\-]{8,})", "[REDACTED_API_KEY]", val)
        val = re.sub(r"(mmaip_live_[a-zA-Z0-9_\-]{8,})", "[REDACTED_API_KEY]", val)
        val = re.sub(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{8,}", r"\1[REDACTED_TOKEN]", val, flags=re.IGNORECASE)
        val = re.sub(r"(password|pwd|secret|api_key|token)\s*=\s*['\"]?[^'\"\s]+['\"]?", r"\1=[REDACTED]", val, flags=re.IGNORECASE)
        return val
    elif isinstance(val, dict):
        return {
            k: sanitize_value(v)
            for k, v in val.items()
            if not any(s in k.lower() for s in ["password", "secret", "token", "auth_header", "private_key", "api_key"])
        }
    elif isinstance(val, list):
        return [sanitize_value(item) for item in val]
    return val


@dataclass
class Span:
    """Individual execution unit in an assistant request lifecycle."""

    span_id: str
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "RUNNING"  # RUNNING, COMPLETED, FAILED
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
    conversation_id: str
    traffic_type: str  # internal, public, embed, developer
    status: str = "RUNNING"  # RUNNING, COMPLETED, FAILED
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    start_time: float = field(default_factory=time.perf_counter)
    end_time: Optional[float] = None
    total_duration_ms: Optional[float] = None
    ttft_ms: Optional[float] = None  # Time To First Token
    provider: Optional[str] = None
    model: Optional[str] = None
    credential_source: str = "byok"
    retrieval_mode: Optional[str] = None
    retrieved_chunk_count: int = 0
    citation_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    error: Optional[str] = None
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

    def finish(self, status: str = "COMPLETED", error: Optional[str] = None):
        self.end_time = time.perf_counter()
        self.total_duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.status = status
        if error:
            self.error = sanitize_value(error)
        try:
            if _global_tracer:
                _global_tracer.save_state()
        except Exception:
            pass

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "assistant_id": self.assistant_id,
            "assistant_name": self.assistant_name,
            "conversation_id": self.conversation_id,
            "traffic_type": self.traffic_type,
            "status": self.status,
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
            "error": self.error,
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


class ObservabilityTracer:
    """Thread-safe, multi-tenant trace collector maintaining a bounded ring buffer of recent traces with disk persistence."""

    def __init__(self, max_traces_per_tenant: int = 500):
        self._max_traces = max_traces_per_tenant
        self._lock = threading.Lock()
        # Mapping: tenant_id -> deque of AssistantTrace
        self._tenant_traces: dict[str, deque[AssistantTrace]] = {}
        # Mapping: trace_id -> AssistantTrace (fast lookup)
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
                    conversation_id=d.get("conversation_id", ""),
                    traffic_type=d.get("traffic_type", "internal"),
                )
                tr.status = d.get("status", "COMPLETED")
                tr.created_at = d.get("created_at", "")
                tr.total_duration_ms = d.get("total_duration_ms")
                tr.ttft_ms = d.get("ttft_ms")
                tr.provider = d.get("provider")
                tr.model = d.get("model")
                tr.credential_source = d.get("credential_source")
                tr.retrieval_mode = d.get("retrieval_mode")
                tr.retrieved_chunk_count = d.get("retrieved_chunk_count", 0)
                tr.citation_count = d.get("citation_count", 0)
                tr.input_tokens = d.get("input_tokens", 0)
                tr.output_tokens = d.get("output_tokens", 0)
                tr.total_tokens = d.get("total_tokens", 0)
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
        """Serialize current traces to disk asynchronously-safe."""
        with self._lock:
            try:
                path = self._get_storage_path()
                path.parent.mkdir(parents=True, exist_ok=True)
                all_traces = []
                for tid, dq in self._tenant_traces.items():
                    for tr in dq:
                        all_traces.append(tr.to_dict())
                # Keep latest 1000 traces max on disk
                if len(all_traces) > 1000:
                    all_traces = all_traces[-1000:]
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(all_traces, f, indent=2)
            except Exception as e:
                logger.warning(f"Failed to persist observability traces: {e}")

    def start_trace(
        self,
        tenant_id: str | uuid.UUID,
        assistant_id: str | uuid.UUID,
        assistant_name: str,
        conversation_id: str | uuid.UUID,
        traffic_type: str = "internal",
    ) -> AssistantTrace:
        """Initialize and register a new AssistantTrace."""
        trace = AssistantTrace(
            trace_id=f"tr_{uuid.uuid4().hex[:16]}",
            tenant_id=str(tenant_id),
            assistant_id=str(assistant_id),
            assistant_name=assistant_name,
            conversation_id=str(conversation_id),
            traffic_type=traffic_type,
        )

        with self._lock:
            tid = str(tenant_id)
            if tid not in self._tenant_traces:
                self._tenant_traces[tid] = deque(maxlen=self._max_traces)

            # Check if deque is full to remove old trace from lookup
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
        """List traces for a tenant in reverse chronological order."""
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
        """Compute aggregated observability metrics across recent traces for a tenant."""
        with self._lock:
            traces = list(self._tenant_traces.get(str(tenant_id), []))

        total_requests = len(traces)
        if total_requests == 0:
            return {
                "total_requests": 0,
                "error_rate": 0.0,
                "avg_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "avg_ttft_ms": 0.0,
                "total_tokens": 0,
                "by_status": {},
                "by_traffic_type": {},
                "by_provider": {},
            }

        completed_latencies = [t.total_duration_ms for t in traces if t.total_duration_ms is not None]
        ttfts = [t.ttft_ms for t in traces if t.ttft_ms is not None]
        errors = sum(1 for t in traces if t.status == "FAILED")
        tokens = sum(t.total_tokens for t in traces)

        completed_latencies.sort()
        p95_idx = int(len(completed_latencies) * 0.95) if completed_latencies else 0
        p95_val = completed_latencies[min(p95_idx, len(completed_latencies) - 1)] if completed_latencies else 0.0

        by_status: dict[str, int] = {}
        by_traffic: dict[str, int] = {}
        by_provider: dict[str, int] = {}

        for t in traces:
            by_status[t.status] = by_status.get(t.status, 0) + 1
            by_traffic[t.traffic_type] = by_traffic.get(t.traffic_type, 0) + 1
            prov = t.provider or "unknown"
            by_provider[prov] = by_provider.get(prov, 0) + 1

        return {
            "total_requests": total_requests,
            "error_rate": round(errors / total_requests, 4),
            "avg_latency_ms": round(sum(completed_latencies) / len(completed_latencies), 2) if completed_latencies else 0.0,
            "p95_latency_ms": round(p95_val, 2),
            "avg_ttft_ms": round(sum(ttfts) / len(ttfts), 2) if ttfts else 0.0,
            "total_tokens": tokens,
            "by_status": by_status,
            "by_traffic_type": by_traffic,
            "by_provider": by_provider,
        }


# Global singleton tracer
_global_tracer = ObservabilityTracer()


def get_tracer() -> ObservabilityTracer:
    """Access the platform observability tracer."""
    return _global_tracer
