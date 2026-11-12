export function getApiBase(): string {
  // 1. Explicitly configured production / environment backend URL
  const explicitUrl = process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL;
  if (explicitUrl && explicitUrl.trim()) {
    return explicitUrl.trim().replace(/\/+$/, "");
  }

  // 2. Client-side browser execution (Local & LAN development fallback)
  if (typeof window !== "undefined" && window.location) {
    const { protocol, hostname } = window.location;
    const isLocalhost =
      hostname === "localhost" ||
      hostname === "127.0.0.1" ||
      hostname === "[::1]" ||
      hostname.startsWith("192.168.") ||
      hostname.startsWith("10.") ||
      hostname.startsWith("172.16.") ||
      hostname.endsWith(".local");

    // Preserve the current protocol (http/https) and map to backend port 8000 for local/LAN
    if (isLocalhost || process.env.NODE_ENV !== "production") {
      return `${protocol}//${hostname}:8000`;
    }

    // Fail closed in production with clear diagnostic rather than silently calling localhost
    throw new Error(
      "[Configuration Error] NEXT_PUBLIC_API_BASE_URL is not configured for production. " +
      "Please set NEXT_PUBLIC_API_BASE_URL to your deployed backend URL."
    );
  }

  // 3. Server-side rendering (SSR) fallback (safe for Next.js build prerendering)
  if (process.env.NODE_ENV === "production") {
    return "";
  }
  return "http://127.0.0.1:8000";
}

export const API_BASE = typeof window !== "undefined" ? getApiBase() : (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000");
export const API_V1 = `${API_BASE}/api/v1`;

export interface WorkspaceSummary {
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  tenant_type: "INDIVIDUAL" | "ORGANIZATION";
  role: string;
  is_active?: boolean;
}

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  status: string;
  is_superuser: boolean;
  is_verified: boolean;
  created_at: string;
  active_tenant_id: string | null;
  workspaces: WorkspaceSummary[];
}

export interface Department {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  member_count: number;
  created_at: string;
  updated_at: string;
}

export interface Member {
  id: string;
  tenant_id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  department_id: string | null;
  department_name: string | null;
  title: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface EmployeeGroup {
  id: string;
  tenant_id: string;
  department_id: string | null;
  name: string;
  description: string | null;
  member_count: number;
  created_at: string;
  updated_at: string;
}

export interface AssistantTemplate {
  id: string;
  name: string;
  description: string;
  category: "Education" | "Business" | "Personal" | "Domain";
  version: string;
  intended_audience: string;
  default_instructions: string;
  default_response_style: string;
  default_uncertainty_behavior: string;
  default_citation_style: string;
  suggested_knowledge: string[];
  suggested_starter_questions: string[];
  default_retrieval_mode: string;
  default_top_k: number;
  default_temperature: number;
  requires_knowledge: boolean;
}

export interface TemplateListResponse {
  templates: AssistantTemplate[];
  total: number;
  categories: string[];
}

export interface AssistantVersionItem {
  id: string;
  tenant_id: string;
  assistant_id: string;
  version_num: number;
  model_name: string;
  system_prompt: string | null;
  config_snapshot: Record<string, any>;
  actor_id: string | null;
  change_summary: string | null;
  created_at: string;
}

export interface AssistantItem {
  id: string;
  tenant_id: string;
  name: string;
  slug: string;
  description: string | null;
  template_id?: string | null;
  audience_level?: string;
  response_style?: string;
  uncertainty_behavior?: string;
  citation_style?: string;
  llm_provider: string;
  default_model: string;
  temperature: number;
  max_tokens: number;
  visibility: string;
  retrieval_mode: string;
  top_k: number;
  system_prompt: string | null;
  status: string;
  current_version_num?: number;
  connected_kb_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface ConversationItem {
  id: string;
  tenant_id: string;
  assistant_id: string;
  user_id: string;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface MessageCitationItem {
  id: string;
  citation_num: number;
  chunk_id: string | null;
  document_name: string;
  citation_text: string;
  page_number?: number | null;
  heading_path?: string | null;
  snippet?: string | null;
  score?: number | null;
  bounding_box?: {
    page: number;
    x: number;
    y: number;
    width: number;
    height: number;
  } | null;
}

export type CitationItem = MessageCitationItem;

export interface MessageItem {
  id: string;
  conversation_id: string;
  sender_type: "user" | "assistant" | "system";
  content: string;
  token_count: number;
  citations: MessageCitationItem[];
  created_at: string;
}


export interface KnowledgeBaseItem {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  status: string;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface AuditLogItem {
  id: string;
  tenant_id: string;
  actor_id: string | null;
  actor_name: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  ip_address: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export interface DocumentItem {
  id: string;
  tenant_id: string;
  knowledge_base_id: string;
  filename: string;
  safe_filename: string;
  file_size: number;
  mime_type: string;
  file_hash: string | null;
  status: string;
  current_version_num: number;
  total_pages: number;
  total_chunks: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentVersionItem {
  id: string;
  document_id: string;
  version_num: number;
  file_size: number;
  file_hash: string | null;
  parser_name: string | null;
  parser_version: string | null;
  ocr_applied: boolean;
  ocr_provider: string | null;
  ocr_language: string | null;
  extraction_stats: Record<string, unknown>;
  created_at: string;
}

export interface DocumentContentItem {
  document_id: string;
  version_num: number;
  filename: string;
  mime_type: string;
  total_pages: number;
  extracted_text: string | null;
  structured_data: Record<string, unknown>;
  extraction_stats: Record<string, unknown>;
}

export interface IngestionEventItem {
  id: string;
  job_id: string;
  event_type: string;
  stage: string;
  level: string;
  message: string;
  event_metadata: Record<string, unknown>;
  created_at: string;
}

export interface DocumentChunkItem {
  id: string;
  knowledge_base_id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  character_count: number;
  token_count: number;
  page_number: number | null;
  heading_path: string | null;
  chunking_strategy: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AssistantPublication {
  id: string;
  tenant_id: string;
  assistant_id: string;
  public_id: string;
  visibility: "PRIVATE" | "WORKSPACE" | "PUBLIC";
  is_active: boolean;
  allowed_domains: string[];
  custom_greeting: string | null;
  brand_color: string;
  published_version_id: string | null;
  created_by: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AssistantPublicationCreate {
  visibility: "PRIVATE" | "WORKSPACE" | "PUBLIC";
  allowed_domains?: string[];
  custom_greeting?: string | null;
  brand_color?: string;
  published_version_id?: string | null;
}

export interface APIKeyItem {
  id: string;
  tenant_id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  expires_at: string | null;
  last_used_at: string | null;
  is_active: boolean;
  created_at: string;
}

export interface APIKeyCreatedResponse extends APIKeyItem {
  raw_key: string;
}

export interface APIKeyCreateRequest {
  name: string;
  scopes: string[];
  expires_days?: number | null;
}

export interface PublicAssistantMetadata {
  public_id: string;
  name: string;
  description: string | null;
  custom_greeting: string | null;
  brand_color: string;
  citation_style: string;
  is_active: boolean;
}

export interface PublicEmbedConfig {
  public_id: string;
  name: string;
  brand_color: string;
  custom_greeting: string | null;
  embed_url: string;
  script_url: string;
}

export interface IngestionJobItem {
  id: string;
  tenant_id: string;
  knowledge_base_id: string;
  document_id: string;
  status: string;
  stage: string;
  progress_pct: number;
  retry_count: number;
  max_retries: number;
  error_category: string | null;
  error_message: string | null;
  duration_ms: number | null;
  job_metadata: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface IngestionEventItem {
  id: string;
  job_id: string;
  document_id: string;
  stage: string;
  status: string;
  message: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface IngestionConfigItem {
  knowledge_base_id: string;
  chunking_strategy: string;
  chunk_size: number;
  chunk_overlap: number;
  ocr_enabled: boolean;
  ocr_provider: string;
  ocr_language: string;
  max_file_size_mb: number;
  settings_json?: Record<string, unknown>;
}

export interface DocumentContentItem {
  document_id: string;
  version_num: number;
  filename: string;
  mime_type: string;
  total_pages: number;
  extracted_text: string | null;
  structured_data: Record<string, unknown>;
  extraction_stats: Record<string, unknown>;
}

export interface DocumentUploadResult {
  document: DocumentItem;
  job: IngestionJobItem;
  is_duplicate: boolean;
}

export interface RoleItem {
  id: string;
  name: string;
  display_name: string;
  description: string | null;
  is_system: boolean;
}

export interface RetrievalConfigItem {
  id: string;
  knowledge_base_id: string;
  retrieval_mode: "lexical" | "semantic" | "hybrid";
  vector_store: "fts" | "pgvector" | "qdrant";
  embedding_provider: "omniroute" | "openai" | "local" | "mock";
  embedding_model: string;
  embedding_dimensions: number;
  embedding_version: number;
  top_k: number;
  similarity_threshold?: number | null;
  similarity_metric: string;
  rrf_k: number;
  reranking_enabled: boolean;
  reranker_model?: string | null;
  hybrid_lexical_weight: number;
  hybrid_semantic_weight: number;
  qdrant_url?: string | null;
  qdrant_collection?: string | null;
  has_api_key?: boolean;
  api_key_masked?: string | null;
  has_qdrant_key?: boolean;
  qdrant_key_masked?: string | null;
  created_at: string;
  updated_at: string;
}

export interface EmbeddingProviderItem {
  name: string;
  display_name: string;
  description: string;
  default_model: string;
  supported_models: string[];
  default_dimensions: number;
  is_local: boolean;
  requires_api_key: boolean;
}

export interface VectorStoreItem {
  name: string;
  display_name: string;
  description: string;
  requires_embeddings: boolean;
  supports_hybrid: boolean;
  is_configured: boolean;
}

export interface ProviderModelInfo {
  model_id: string;
  display_name: string;
  context_window: number;
  max_output_tokens: number;
  supports_streaming: boolean;
  supports_tools: boolean;
  supports_vision: boolean;
  supports_audio: boolean;
  description: string;
}

export interface ProviderDirectoryItem {
  name: string;
  display_name: string;
  description: string;
  requires_api_key: boolean;
  default_base_url: string | null;
  models: ProviderModelInfo[];
}

export interface ProviderCredential {
  id: string;
  tenant_id: string;
  provider_name: string;
  display_name: string;
  api_key_masked: string;
  base_url: string | null;
  is_active: boolean;
  is_default: boolean;
  status: "HEALTHY" | "UNHEALTHY" | "REVOKED";
  error_message: string | null;
  last_tested_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProviderUsageSummary {
  monthly_tokens_used: number;
  monthly_tokens_limit: number;
  monthly_prompt_tokens: number;
  monthly_completion_tokens: number;
  percentage_used: number;
  today_requests: number;
  daily_request_limit: number;
  by_provider: Array<{
    provider: string;
    total_tokens: number;
    prompt_tokens: number;
    completion_tokens: number;
    requests: number;
  }>;
}

export interface DocumentChunk {
  id: string;
  knowledge_base_id: string;
  document_id: string;
  document_version_id?: string | null;
  chunk_index: number;
  content: string;
  character_count: number;
  token_count: number;
  page_number?: number | null;
  heading_path?: string | null;
  chunk_hash?: string | null;
  chunking_strategy: string;
  metadata_json?: Record<string, any>;
  created_at: string;
}

export interface PlaygroundChunkResult {
  chunk_id: string;
  document_id: string;
  document_title: string;
  rank: number;
  sparse_score?: number | null;
  dense_score?: number | null;
  score: number;
  retrieval_source: string;
  content: string;
  page_number?: number | null;
  heading_path?: string | null;
}

export interface PlaygroundSearchResponse {
  query: string;
  knowledge_base_id: string;
  retrieval_mode: string;
  vector_store: string;
  latency_ms: number;
  total_results: number;
  results: PlaygroundChunkResult[];
}

export interface SearchCitationItem {
  citation_id: string;
  document_id: string;
  document_name: string;
  chunk_id: string;
  page_number?: number | null;
  heading_path?: string | null;
  source_snippet: string;
  score: number;
  retrieval_mode: string;
}

export interface SearchCandidateItem {
  chunk_id: string;
  document_id: string;
  document_version_id: string;
  document_name?: string | null;
  content: string;
  score: number;
  lexical_score?: number | null;
  semantic_score?: number | null;
  lexical_rank?: number | null;
  semantic_rank?: number | null;
  fused_rank?: number | null;
  retrieval_mode: string;
  page_number?: number | null;
  heading_path?: string | null;
  chunk_index?: number | null;
}

export interface SearchResponse {
  query: string;
  retrieval_mode: string;
  vector_store: string;
  total_candidates: number;
  returned_candidates: number;
  took_ms: number;
  candidates: SearchCandidateItem[];
  citations: SearchCitationItem[];
}

export interface IndexStatusItem {
  knowledge_base_id: string;
  total_documents: number;
  total_chunks: number;
  indexed_embeddings: number;
  pending_embeddings: number;
  failed_embeddings: number;
  active_embedding_version: number;
  retrieval_mode: string;
  vector_store: string;
  vector_store_healthy: boolean;
  last_indexed_at?: string | null;
}

export interface EmbeddingJobItem {
  id: string;
  tenant_id: string;
  knowledge_base_id: string;
  document_id?: string | null;
  status: string;
  provider: string;
  model: string;
  dimensions: number;
  version: number;
  total_chunks: number;
  processed_chunks: number;
  failed_chunks: number;
  error_message?: string | null;
  created_at: string;
  completed_at?: string | null;
}

export interface EvalDatasetItem {
  id: string;
  dataset_id: string;
  question: string;
  expected_answer?: string | null;
  expected_chunk_ids: string[];
  is_unanswerable: boolean;
  is_adversarial: boolean;
  item_metadata: Record<string, any>;
  created_at: string;
}

export interface EvalDataset {
  id: string;
  tenant_id: string;
  name: string;
  description?: string | null;
  version: number;
  is_system: boolean;
  item_count: number;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
  items?: EvalDatasetItem[];
}

export interface EvalRunResult {
  id: string;
  run_id: string;
  item_id: string;
  question?: string | null;
  expected_answer?: string | null;
  generated_answer?: string | null;
  retrieved_chunks: Array<{ chunk_id: string; document_name: string; score: number; content: string }>;
  citations: Array<{ chunk_id: string; document_name: string }>;
  recall_score: number;
  mrr_score: number;
  faithfulness_score: number;
  citation_score: number;
  latency_ms: number;
  error_message?: string | null;
  created_at: string;
}

export interface EvalRun {
  id: string;
  tenant_id: string;
  assistant_id: string;
  dataset_id: string;
  status: string;
  eval_type: string;
  judge_provider?: string | null;
  judge_model?: string | null;
  metrics_summary: {
    total_items?: number;
    mean_recall_at_5?: number;
    mean_mrr?: number;
    mean_faithfulness?: number;
    mean_citation_score?: number;
    mean_latency_ms?: number;
    unanswerable_tested?: number;
    adversarial_tested?: number;
    error?: string;
    [key: string]: any;
  };
  created_by?: string | null;
  created_at: string;
  completed_at?: string | null;
  result_count: number;
  results?: EvalRunResult[];
}

export interface EvalRunComparison {
  run_a_id: string;
  run_b_id: string;
  assistant_id: string;
  metrics_delta: {
    recall_delta: number;
    mrr_delta: number;
    faithfulness_delta: number;
    citation_delta: number;
    latency_delta_ms: number;
  };
  summary_a: Record<string, any>;
  summary_b: Record<string, any>;
}

export interface TraceSpanItem {
  span_id: string;
  name: string;
  duration_ms?: number | null;
  status: string;
  attributes: Record<string, any>;
  error?: string | null;
}

export interface AssistantTraceItem {
  trace_id: string;
  tenant_id: string;
  assistant_id: string;
  assistant_name: string;
  conversation_id: string;
  traffic_type: string;
  status: string;
  created_at: string;
  total_duration_ms?: number | null;
  ttft_ms?: number | null;
  provider?: string | null;
  model?: string | null;
  credential_source: string;
  retrieval_mode?: string | null;
  retrieved_chunk_count: number;
  citation_count: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  error?: string | null;
  span_count: number;
  spans?: TraceSpanItem[];
}

export interface ObservabilityMetrics {
  total_requests: number;
  error_rate: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  avg_ttft_ms: number;
  total_tokens: number;
  by_status: Record<string, number>;
  by_traffic_type: Record<string, number>;
  by_provider: Record<string, number>;
}

class ApiClient {
  public getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("mmaip_token") || localStorage.getItem("token");
  }

  public getActiveTenantId(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("mmaip_active_tenant_id");
  }

  public getApiBase(): string {
    return getApiBase();
  }

  public getApiV1(): string {
    return `${this.getApiBase()}/api/v1`;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    requireTenant: boolean = true
  ): Promise<T> {
    const token = this.getToken();
    const tenantId = this.getActiveTenantId();

    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };

    if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    if (requireTenant && tenantId) {
      headers["X-Tenant-ID"] = tenantId;
    }

    const response = await fetch(`${this.getApiV1()}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 204) {
      return {} as T;
    }

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const errorMsg = data?.detail || data?.message || `HTTP error ${response.status}`;
      throw new Error(errorMsg);
    }

    return data as T;
  }

  // Auth Endpoints
  async register(payload: { email: string; password: string; full_name: string; organization_name?: string }) {
    const res = await this.request<{ access_token: string; refresh_token: string }>(
      "/auth/register",
      { method: "POST", body: JSON.stringify(payload) },
      false
    );
    if (typeof window !== "undefined") {
      localStorage.setItem("mmaip_token", res.access_token);
    }
    return res;
  }

  async login(payload: { email: string; password: string }) {
    const res = await this.request<{ access_token: string; refresh_token: string }>(
      "/auth/login",
      { method: "POST", body: JSON.stringify(payload) },
      false
    );
    if (typeof window !== "undefined") {
      localStorage.setItem("mmaip_token", res.access_token);
    }
    return res;
  }

  async getMe(): Promise<UserProfile> {
    return this.request<UserProfile>("/auth/me", { method: "GET" }, false);
  }

  async logout(): Promise<void> {
    if (typeof window !== "undefined") {
      localStorage.removeItem("mmaip_token");
      localStorage.removeItem("mmaip_active_tenant_id");
    }
  }

  // Tenant / Workspace Endpoints
  async listWorkspaces(): Promise<WorkspaceSummary[]> {
    return this.request<WorkspaceSummary[]>("/tenants", { method: "GET" }, false);
  }

  async createWorkspace(payload: { name: string; type: "INDIVIDUAL" | "ORGANIZATION"; legal_name?: string; domain?: string }) {
    return this.request<{ id: string; name: string; slug: string; type: string }>(
      "/tenants",
      { method: "POST", body: JSON.stringify(payload) },
      false
    );
  }

  async switchWorkspace(tenantId: string) {
    const res = await this.request<{ access_token: string }>(
      `/tenants/${tenantId}/switch`,
      { method: "POST" },
      false
    );
    if (typeof window !== "undefined") {
      localStorage.setItem("mmaip_token", res.access_token);
      localStorage.setItem("mmaip_active_tenant_id", tenantId);
    }
    return res;
  }

  // Department Endpoints
  async listDepartments(): Promise<Department[]> {
    return this.request<Department[]>("/departments", { method: "GET" }, true);
  }

  async createDepartment(payload: { name: string; description?: string }): Promise<Department> {
    return this.request<Department>("/departments", { method: "POST", body: JSON.stringify(payload) }, true);
  }

  async deleteDepartment(id: string): Promise<void> {
    return this.request<void>(`/departments/${id}`, { method: "DELETE" }, true);
  }

  // Member Endpoints
  async listMembers(): Promise<Member[]> {
    return this.request<Member[]>("/members", { method: "GET" }, true);
  }

  async inviteMember(payload: { email: string; role: string; department_id?: string; title?: string }): Promise<Member> {
    return this.request<Member>("/members/invite", { method: "POST", body: JSON.stringify(payload) }, true);
  }

  async removeMember(id: string): Promise<void> {
    return this.request<void>(`/members/${id}`, { method: "DELETE" }, true);
  }

  // Group Endpoints
  async listGroups(): Promise<EmployeeGroup[]> {
    return this.request<EmployeeGroup[]>("/groups", { method: "GET" }, true);
  }

  async createGroup(payload: { name: string; description?: string; department_id?: string }): Promise<EmployeeGroup> {
    return this.request<EmployeeGroup>("/groups", { method: "POST", body: JSON.stringify(payload) }, true);
  }

  async deleteGroup(id: string): Promise<void> {
    return this.request<void>(`/groups/${id}`, { method: "DELETE" }, true);
  }

  // Knowledge Endpoints

  async listKnowledgeBases(): Promise<KnowledgeBaseItem[]> {
    return this.request<KnowledgeBaseItem[]>("/knowledge", { method: "GET" }, true);
  }

  async createKnowledgeBase(payload: { name: string; description?: string }): Promise<KnowledgeBaseItem> {
    return this.request<KnowledgeBaseItem>("/knowledge", { method: "POST", body: JSON.stringify(payload) }, true);
  }

  async getKnowledgeBase(id: string): Promise<KnowledgeBaseItem> {
    return this.request<KnowledgeBaseItem>(`/knowledge/${id}`, { method: "GET" }, true);
  }

  async updateKnowledgeBase(
    id: string,
    payload: { name?: string; description?: string; status?: string }
  ): Promise<KnowledgeBaseItem> {
    return this.request<KnowledgeBaseItem>(`/knowledge/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }, true);
  }

  async deleteKnowledgeBase(id: string): Promise<void> {
    return this.request<void>(`/knowledge/${id}`, { method: "DELETE" }, true);
  }

  // Document Endpoints (Milestone 02)
  async uploadDocuments(kbId: string, files: File[]): Promise<DocumentUploadResult[]> {
    const formData = new FormData();
    files.forEach((f) => formData.append("files", f));
    return this.request<DocumentUploadResult[]>(`/knowledge/${kbId}/documents`, {
      method: "POST",
      body: formData,
    }, true);
  }

  async listDocuments(kbId: string): Promise<DocumentItem[]> {
    return this.request<DocumentItem[]>(`/knowledge/${kbId}/documents`, { method: "GET" }, true);
  }

  async getDocument(docId: string): Promise<DocumentItem> {
    return this.request<DocumentItem>(`/documents/${docId}`, { method: "GET" }, true);
  }

  async deleteDocument(docId: string): Promise<void> {
    return this.request<void>(`/documents/${docId}`, { method: "DELETE" }, true);
  }

  async listDocumentVersions(docId: string): Promise<DocumentVersionItem[]> {
    return this.request<DocumentVersionItem[]>(`/documents/${docId}/versions`, { method: "GET" }, true);
  }

  async reprocessDocument(docId: string): Promise<IngestionJobItem> {
    return this.request<IngestionJobItem>(`/documents/${docId}/reprocess`, { method: "POST" }, true);
  }

  async getDocumentContent(docId: string): Promise<DocumentContentItem> {
    return this.request<DocumentContentItem>(`/documents/${docId}/content`, { method: "GET" }, true);
  }

  async getDocumentChunks(docId: string): Promise<DocumentChunkItem[]> {
    return this.request<DocumentChunkItem[]>(`/documents/${docId}/chunks`, { method: "GET" }, true);
  }

  async getDocumentHistory(docId: string): Promise<IngestionEventItem[]> {
    return this.request<IngestionEventItem[]>(`/documents/${docId}/processing-history`, { method: "GET" }, true);
  }

  async getIngestionConfig(kbId: string): Promise<IngestionConfigItem> {
    return this.request<IngestionConfigItem>(`/knowledge/${kbId}/ingestion-config`, { method: "GET" }, true);
  }

  async updateIngestionConfig(kbId: string, payload: Partial<IngestionConfigItem>): Promise<IngestionConfigItem> {
    return this.request<IngestionConfigItem>(`/knowledge/${kbId}/ingestion-config`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }, true);
  }

  async getIngestionJob(jobId: string): Promise<IngestionJobItem> {
    return this.request<IngestionJobItem>(`/ingestion/jobs/${jobId}`, { method: "GET" }, true);
  }

  async retryIngestionJob(jobId: string): Promise<IngestionJobItem> {
    return this.request<IngestionJobItem>(`/ingestion/jobs/${jobId}/retry`, { method: "POST" }, true);
  }

  async cancelIngestionJob(jobId: string): Promise<IngestionJobItem> {
    return this.request<IngestionJobItem>(`/ingestion/jobs/${jobId}/cancel`, { method: "POST" }, true);
  }

  // Audit Endpoints
  async listAuditLogs(): Promise<AuditLogItem[]> {
    return this.request<AuditLogItem[]>("/audit", { method: "GET" }, true);
  }

  // Roles Endpoints
  async listRoles(): Promise<RoleItem[]> {
    return this.request<RoleItem[]>("/roles", { method: "GET" }, false);
  }

  // Retrieval & Vector Configuration Endpoints (Milestone 03)
  async getRetrievalConfig(kbId: string): Promise<RetrievalConfigItem> {
    return this.request<RetrievalConfigItem>(`/knowledge/${kbId}/retrieval-config`, { method: "GET" }, true);
  }

  async updateRetrievalConfig(
    kbId: string,
    payload: Partial<RetrievalConfigItem> & { api_key?: string; qdrant_api_key?: string }
  ): Promise<RetrievalConfigItem> {
    return this.request<RetrievalConfigItem>(`/knowledge/${kbId}/retrieval-config`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }, true);
  }

  async getKBIndexStatus(kbId: string): Promise<IndexStatusItem> {
    return this.request<IndexStatusItem>(`/knowledge/${kbId}/index-status`, { method: "GET" }, true);
  }

  async reindexKB(kbId: string): Promise<{ message: string; knowledge_base_id: string; total_chunks: number }> {
    return this.request<{ message: string; knowledge_base_id: string; total_chunks: number }>(
      `/knowledge/${kbId}/reindex`,
      { method: "POST" },
      true
    );
  }

  async listKBEmbeddingJobs(kbId: string): Promise<EmbeddingJobItem[]> {
    return this.request<EmbeddingJobItem[]>(`/knowledge/${kbId}/embedding-jobs`, { method: "GET" }, true);
  }

  // Search & Preview Endpoints
  async searchKnowledge(payload: {
    query: string;
    knowledge_base_ids: string[];
    retrieval_mode?: "lexical" | "semantic" | "hybrid";
    top_k?: number;
    similarity_threshold?: number;
  }): Promise<SearchResponse> {
    return this.request<SearchResponse>("/retrieval/search", {
      method: "POST",
      body: JSON.stringify(payload),
    }, true);
  }

  async previewKnowledge(payload: {
    query: string;
    knowledge_base_ids: string[];
    retrieval_mode?: "lexical" | "semantic" | "hybrid";
    top_k?: number;
  }): Promise<SearchResponse> {
    return this.request<SearchResponse>("/retrieval/preview", {
      method: "POST",
      body: JSON.stringify(payload),
    }, true);
  }

  // Embedding Providers & Vector Stores Meta Endpoints
  async listEmbeddingProviders(): Promise<EmbeddingProviderItem[]> {
    return this.request<EmbeddingProviderItem[]>("/embedding-providers", { method: "GET" }, true);
  }

  async validateEmbeddingProvider(payload: {
    provider: string;
    model?: string;
    api_key?: string;
  }): Promise<{ valid: boolean; provider: string; model: string; dimensions?: number; message: string }> {
    return this.request<{ valid: boolean; provider: string; model: string; dimensions?: number; message: string }>(
      "/embedding-providers/validate",
      { method: "POST", body: JSON.stringify(payload) },
      true
    );
  }

  async listVectorStores(): Promise<VectorStoreItem[]> {
    return this.request<VectorStoreItem[]>("/vector-stores", { method: "GET" }, true);
  }

  async validateVectorStore(payload: {
    vector_store: string;
    qdrant_url?: string;
    qdrant_api_key?: string;
    qdrant_collection?: string;
  }): Promise<{ valid: boolean; vector_store: string; status: string; collection_exists?: boolean; message: string }> {
    return this.request<{ valid: boolean; vector_store: string; status: string; collection_exists?: boolean; message: string }>(
      "/vector-stores/validate",
      { method: "POST", body: JSON.stringify(payload) },
      true
    );
  }

  // =========================================================================
  // TEMPLATES API
  // =========================================================================

  async listTemplates(): Promise<TemplateListResponse> {
    return this.request<TemplateListResponse>("/templates", { method: "GET" }, false);
  }

  async getTemplate(templateId: string): Promise<AssistantTemplate> {
    return this.request<AssistantTemplate>(`/templates/${templateId}`, { method: "GET" }, false);
  }

  // =========================================================================
  // ASSISTANTS API
  // =========================================================================

  async listAssistants(): Promise<AssistantItem[]> {
    return this.request<AssistantItem[]>("/assistants", { method: "GET" }, true);
  }

  async getAssistant(assistantId: string): Promise<AssistantItem> {
    return this.request<AssistantItem>(`/assistants/${assistantId}`, { method: "GET" }, true);
  }

  async createAssistant(payload: {
    name: string;
    description?: string;
    template_id?: string;
    audience_level?: string;
    response_style?: string;
    uncertainty_behavior?: string;
    citation_style?: string;
    llm_provider?: string;
    default_model?: string;
    temperature?: number;
    max_tokens?: number;
    visibility?: string;
    retrieval_mode?: string;
    top_k?: number;
    system_prompt?: string;
    knowledge_base_ids?: string[];
  }): Promise<AssistantItem> {
    return this.request<AssistantItem>("/assistants", {
      method: "POST",
      body: JSON.stringify(payload),
    }, true);
  }

  async updateAssistant(
    assistantId: string,
    payload: {
      name?: string;
      description?: string;
      template_id?: string;
      audience_level?: string;
      response_style?: string;
      uncertainty_behavior?: string;
      citation_style?: string;
      llm_provider?: string;
      default_model?: string;
      temperature?: number;
      max_tokens?: number;
      visibility?: string;
      retrieval_mode?: string;
      top_k?: number;
      system_prompt?: string;
      status?: string;
      knowledge_base_ids?: string[];
      change_summary?: string;
    }
  ): Promise<AssistantItem> {
    return this.request<AssistantItem>(`/assistants/${assistantId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }, true);
  }

  async deleteAssistant(assistantId: string): Promise<void> {
    await this.request<void>(`/assistants/${assistantId}`, { method: "DELETE" }, true);
  }

  async listAssistantVersions(assistantId: string): Promise<AssistantVersionItem[]> {
    return this.request<AssistantVersionItem[]>(`/assistants/${assistantId}/versions`, { method: "GET" }, true);
  }

  async getAssistantVersion(assistantId: string, versionNum: number): Promise<AssistantVersionItem> {
    return this.request<AssistantVersionItem>(`/assistants/${assistantId}/versions/${versionNum}`, { method: "GET" }, true);
  }

  async rollbackAssistantVersion(
    assistantId: string,
    targetVersionNum: number,
    changeSummary?: string
  ): Promise<AssistantItem> {
    return this.request<AssistantItem>(`/assistants/${assistantId}/rollback`, {
      method: "POST",
      body: JSON.stringify({
        target_version_num: targetVersionNum,
        change_summary: changeSummary,
      }),
    }, true);
  }

  async streamPreviewTest(
    payload: {
      message: string;
      system_prompt?: string;
      llm_provider?: string;
      default_model?: string;
      temperature?: number;
      max_tokens?: number;
      retrieval_mode?: string;
      top_k?: number;
      knowledge_base_ids?: string[];
    },
    onEvent: (event: string, data: any) => void,
    signal?: AbortSignal
  ): Promise<void> {
    const token = this.getToken();
    const tenantId = this.getActiveTenantId();

    const res = await fetch(`${this.getApiV1()}/assistants/preview-test`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(tenantId ? { "X-Tenant-ID": tenantId } : {}),
      },
      body: JSON.stringify(payload),
      signal,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Preview request failed" }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const reader = res.body?.getReader();
    if (!reader) return;

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || "";

      for (const block of lines) {
        if (!block.trim()) continue;
        const eventMatch = block.match(/event:\s*([^\n]+)/);
        const dataMatch = block.match(/data:\s*([^\n]+)/);

        if (eventMatch && dataMatch) {
          const eventType = eventMatch[1].trim();
          try {
            const dataObj = JSON.parse(dataMatch[1].trim());
            onEvent(eventType, dataObj);
          } catch {
            onEvent(eventType, { raw: dataMatch[1] });
          }
        }
      }
    }
  }

  // =========================================================================
  // CONVERSATIONS & STREAMING CHAT API
  // =========================================================================

  async listConversations(assistantId?: string): Promise<ConversationItem[]> {
    const url = assistantId ? `/conversations?assistant_id=${assistantId}` : "/conversations";
    return this.request<ConversationItem[]>(url, { method: "GET" }, true);
  }

  async createConversation(payload: { assistant_id: string; title?: string }): Promise<ConversationItem> {
    return this.request<ConversationItem>("/conversations", {
      method: "POST",
      body: JSON.stringify(payload),
    }, true);
  }

  async deleteConversation(conversationId: string): Promise<void> {
    await this.request<void>(`/conversations/${conversationId}`, { method: "DELETE" }, true);
  }

  async updateConversation(
    conversationId: string,
    payload: { title?: string; status?: string }
  ): Promise<ConversationItem> {
    return this.request<ConversationItem>(`/conversations/${conversationId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }, true);
  }

  async listMessages(conversationId: string): Promise<MessageItem[]> {
    return this.request<MessageItem[]>(`/conversations/${conversationId}/messages`, { method: "GET" }, true);
  }

  // ---------------------------------------------------------------------------
  // M07: Provider Directory, BYOK Key Vault & Quotas
  // ---------------------------------------------------------------------------

  async getProviderDirectory(): Promise<ProviderDirectoryItem[]> {
    return this.request<ProviderDirectoryItem[]>("/providers/directory", { method: "GET" }, true);
  }

  async listProviderCredentials(): Promise<ProviderCredential[]> {
    return this.request<ProviderCredential[]>("/providers/credentials", { method: "GET" }, true);
  }

  async createProviderCredential(data: {
    provider_name: string;
    display_name: string;
    api_key: string;
    base_url?: string;
    is_default?: boolean;
  }): Promise<ProviderCredential> {
    return this.request<ProviderCredential>("/providers/credentials", {
      method: "POST",
      body: JSON.stringify(data),
    }, true);
  }

  async testProviderCredential(id: string): Promise<{ valid: boolean; error: string | null }> {
    return this.request<{ valid: boolean; error: string | null }>(`/providers/credentials/${id}/test`, {
      method: "POST",
    }, true);
  }

  async rotateProviderCredential(id: string, new_api_key: string): Promise<ProviderCredential> {
    return this.request<ProviderCredential>(`/providers/credentials/${id}/rotate`, {
      method: "POST",
      body: JSON.stringify({ new_api_key }),
    }, true);
  }

  async revokeProviderCredential(id: string): Promise<ProviderCredential> {
    return this.request<ProviderCredential>(`/providers/credentials/${id}/revoke`, {
      method: "POST",
    }, true);
  }

  async deleteProviderCredential(id: string): Promise<void> {
    return this.request<void>(`/providers/credentials/${id}`, {
      method: "DELETE",
    }, true);
  }

  async getProviderUsageSummary(): Promise<ProviderUsageSummary> {
    return this.request<ProviderUsageSummary>("/providers/usage/summary", { method: "GET" }, true);
  }

  // ---------------------------------------------------------------------------
  // M07: Safe URL Ingestion & Chunk Inspector
  // ---------------------------------------------------------------------------

  async ingestDocumentUrl(knowledge_base_id: string, url: string): Promise<any> {
    return this.request<any>("/documents/ingest-url", {
      method: "POST",
      body: JSON.stringify({ knowledge_base_id, url }),
    }, true);
  }

  async listDocumentChunks(document_id: string, limit = 100, offset = 0): Promise<DocumentChunk[]> {
    return this.request<DocumentChunk[]>(`/documents/${document_id}/chunks?limit=${limit}&offset=${offset}`, {
      method: "GET",
    }, true);
  }

  // ---------------------------------------------------------------------------
  // M07: Retrieval Playground
  // ---------------------------------------------------------------------------

  async searchRetrievalPlayground(data: {
    knowledge_base_id: string;
    query: string;
    mode?: string;
    top_k?: number;
    similarity_threshold?: number;
  }): Promise<PlaygroundSearchResponse> {
    return this.request<PlaygroundSearchResponse>("/retrieval/playground", {
      method: "POST",
      body: JSON.stringify(data),
    }, true);
  }

  async streamChatMessage(
    conversationId: string,
    content: string,
    callbacks: {
      onToken: (delta: string) => void;
      onCitation?: (citation: MessageCitationItem) => void;
      onCitations?: (citations: MessageCitationItem[]) => void;
      onComplete?: (metadata: { messageId: string }) => void;
      onError?: (error: string) => void;
    }
  ): Promise<void> {
    const token = this.getToken();
    const activeTenantId = this.getActiveTenantId();


    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (activeTenantId) headers["X-Tenant-ID"] = activeTenantId;

    const res = await fetch(`${this.getApiV1()}/conversations/${conversationId}/messages/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify({ content }),
    });

    if (!res.ok) {
      const err = await res.text();
      callbacks.onError?.(`HTTP ${res.status}: ${err}`);
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) {
      callbacks.onError?.("No response stream available");
      return;
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() || "";

      for (const frame of frames) {
        if (!frame.trim()) continue;
        const lines = frame.split("\n");
        let event = "";
        let dataStr = "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            event = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            dataStr = line.slice(6).trim();
          }
        }

        if (event && dataStr) {
          try {
            const data = JSON.parse(dataStr);
            if (event === "token" && data.delta) {
              callbacks.onToken(data.delta);
            } else if (event === "retrieval_complete" && data.citations) {
              callbacks.onCitations?.(data.citations);
            } else if (event === "citation" && data.citation) {
              callbacks.onCitation?.(data.citation);
            } else if (event === "message_complete") {
              callbacks.onComplete?.({ messageId: data.message_id });
            } else if (event === "message_error") {
              callbacks.onError?.(data.error || "Unknown stream error");
            }
          } catch {
            // Ignore parse errors on partial frames
          }
        }
      }
    }
  }

  // Assistant Publishing
  async getAssistantPublication(assistantId: string): Promise<AssistantPublication> {
    return this.request<AssistantPublication>(`/assistants/${assistantId}/publication`);
  }

  async publishAssistant(assistantId: string, payload: AssistantPublicationCreate): Promise<AssistantPublication> {
    return this.request<AssistantPublication>(`/assistants/${assistantId}/publish`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async unpublishAssistant(assistantId: string): Promise<AssistantPublication> {
    return this.request<AssistantPublication>(`/assistants/${assistantId}/unpublish`, {
      method: "POST",
    });
  }

  async updateAssistantPublication(
    assistantId: string,
    payload: Partial<AssistantPublicationCreate>
  ): Promise<AssistantPublication> {
    return this.request<AssistantPublication>(`/assistants/${assistantId}/publication`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  // Developer API Keys
  async listApiKeys(): Promise<APIKeyItem[]> {
    return this.request<APIKeyItem[]>("/developer/api-keys");
  }

  async createApiKey(payload: APIKeyCreateRequest): Promise<APIKeyCreatedResponse> {
    return this.request<APIKeyCreatedResponse>("/developer/api-keys", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async revokeApiKey(keyId: string): Promise<{ success: boolean; message: string }> {
    return this.request<{ success: boolean; message: string }>(`/developer/api-keys/${keyId}`, {
      method: "DELETE",
    });
  }

  // AI Evaluation & Benchmarking (M09)
  async listEvalDatasets(): Promise<EvalDataset[]> {
    return this.request<EvalDataset[]>("/evaluations/datasets");
  }

  async getEvalDataset(id: string): Promise<EvalDataset> {
    return this.request<EvalDataset>(`/evaluations/datasets/${id}`);
  }

  async createEvalDataset(payload: {
    name: string;
    description?: string;
    items?: Array<{
      question: string;
      expected_answer?: string;
      expected_chunk_ids?: string[];
      is_unanswerable?: boolean;
      is_adversarial?: boolean;
      item_metadata?: Record<string, any>;
    }>;
  }): Promise<EvalDataset> {
    return this.request<EvalDataset>("/evaluations/datasets", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async seedStarterBenchmarks(): Promise<EvalDataset[]> {
    return this.request<EvalDataset[]>("/evaluations/datasets/seed-starter", {
      method: "POST",
    });
  }

  async listEvalRuns(assistantId?: string): Promise<EvalRun[]> {
    const url = assistantId ? `/evaluations/runs?assistant_id=${assistantId}` : "/evaluations/runs";
    return this.request<EvalRun[]>(url);
  }

  async getEvalRun(runId: string): Promise<EvalRun> {
    return this.request<EvalRun>(`/evaluations/runs/${runId}`);
  }

  async triggerEvalRun(payload: {
    assistant_id: string;
    dataset_id: string;
    eval_type?: string;
    judge_provider?: string;
    judge_model?: string;
  }): Promise<EvalRun> {
    return this.request<EvalRun>("/evaluations/runs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async compareEvalRuns(runIdA: string, runIdB: string): Promise<EvalRunComparison> {
    return this.request<EvalRunComparison>(`/evaluations/runs/${runIdA}/compare/${runIdB}`);
  }

  // Platform Observability & Tracing (M09)
  async listTraces(params?: {
    assistant_id?: string;
    status?: string;
    traffic_type?: string;
    limit?: number;
  }): Promise<AssistantTraceItem[]> {
    const q = new URLSearchParams();
    if (params?.assistant_id) q.set("assistant_id", params.assistant_id);
    if (params?.status) q.set("status", params.status);
    if (params?.traffic_type) q.set("traffic_type", params.traffic_type);
    if (params?.limit) q.set("limit", String(params.limit));
    const qs = q.toString() ? `?${q.toString()}` : "";
    return this.request<AssistantTraceItem[]>(`/observability/traces${qs}`);
  }

  async getTraceDetail(traceId: string): Promise<AssistantTraceItem> {
    return this.request<AssistantTraceItem>(`/observability/traces/${traceId}`);
  }

  async getObservabilityMetrics(): Promise<ObservabilityMetrics> {
    return this.request<ObservabilityMetrics>("/observability/metrics");
  }

  // Public Chat Endpoints (Zero Auth / Anonymous Visitor)
  async getPublicAssistant(publicId: string): Promise<PublicAssistantMetadata> {
    const res = await fetch(`${API_V1}/public/assistants/${publicId}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Assistant not found or publication is inactive");
    }
    return res.json();
  }

  async getPublicEmbedConfig(publicId: string): Promise<PublicEmbedConfig> {
    const res = await fetch(`${API_V1}/public/assistants/${publicId}/embed-config`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to load embed configuration");
    }
    return res.json();
  }

  async streamPublicChat(
    publicId: string,
    message: string,
    sessionToken: string | undefined,
    callbacks: {
      onToken: (delta: string) => void;
      onCitation?: (citation: MessageCitationItem) => void;
      onCitations?: (citations: MessageCitationItem[]) => void;
      onComplete?: (metadata: { messageId: string }) => void;
      onError?: (error: string) => void;
    }
  ): Promise<void> {
    const res = await fetch(`${this.getApiV1()}/public/assistants/${publicId}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message, session_token: sessionToken }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Chat request failed: ${res.status}`);
    }

    const reader = res.body?.getReader();
    if (!reader) throw new Error("Response body is not readable");

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() || "";

      for (const frame of frames) {
        if (!frame.trim()) continue;
        const lines = frame.split("\n");
        let event = "";
        let dataStr = "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            event = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            dataStr = line.slice(6).trim();
          }
        }

        if (event && dataStr) {
          try {
            const data = JSON.parse(dataStr);
            if (event === "token" && data.delta) {
              callbacks.onToken(data.delta);
            } else if (event === "retrieval_complete" && data.citations) {
              callbacks.onCitations?.(data.citations);
            } else if (event === "citation" && data.citation) {
              callbacks.onCitation?.(data.citation);
            } else if (event === "message_complete") {
              callbacks.onComplete?.({ messageId: data.message_id });
            } else if (event === "message_error") {
              callbacks.onError?.(data.error || "Unknown stream error");
            }
          } catch {
            // Ignore partial frames
          }
        }
      }
    }
  }
}

export const api = new ApiClient();

