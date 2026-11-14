"use client";

import React, { useEffect, useState, useRef } from "react";
import {
  api,
  AssistantItem,
  AssistantTemplate,
  KnowledgeBaseItem,
} from "@/lib/api";
import {
  Sparkles,
  GraduationCap,
  Briefcase,
  User,
  Compass,
  ArrowRight,
  ArrowLeft,
  Check,
  Send,
  Square,
  Bot,
  Database,
  Sliders,
  ShieldCheck,
  Layers,
  X,
  RefreshCw,
  FileText,
  HelpCircle,
} from "lucide-react";
import MarkdownRenderer from "@/components/chat/MarkdownRenderer";


interface AssistantCreationWizardProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (assistant: AssistantItem) => void;
  tenantKBs: KnowledgeBaseItem[];
}

export default function AssistantCreationWizard({
  isOpen,
  onClose,
  onSuccess,
  tenantKBs,
}: AssistantCreationWizardProps) {
  // Wizard Step: 1 = Purpose, 2 = Audience, 3 = Knowledge, 4 = Behavior, 5 = Test
  const [step, setStep] = useState<1 | 2 | 3 | 4 | 5>(1);

  // Template State
  const [templates, setTemplates] = useState<AssistantTemplate[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("All");
  const [selectedTemplate, setSelectedTemplate] = useState<AssistantTemplate | null>(null);
  const [loadingTemplates, setLoadingTemplates] = useState(false);

  // Step 2: Identity & Audience
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [audienceLevel, setAudienceLevel] = useState("general");

  // Step 3: Knowledge (Optional)
  const [selectedKBIds, setSelectedKBIds] = useState<string[]>([]);

  // Step 4: Behavior & Configuration (Simple vs Advanced)
  const [mode, setMode] = useState<"simple" | "advanced">("simple");
  const [responseStyle, setResponseStyle] = useState("balanced");
  const [uncertaintyBehavior, setUncertaintyBehavior] = useState("admit");
  const [citationStyle, setCitationStyle] = useState("strict");
  const [systemPrompt, setSystemPrompt] = useState("");

  // Advanced technical settings
  const [llmProvider, setLlmProvider] = useState("omniroute");
  const [defaultModel, setDefaultModel] = useState("auto");
  const [temperature, setTemperature] = useState(0.4);
  const [maxTokens, setMaxTokens] = useState(1024);
  const [retrievalMode, setRetrievalMode] = useState<"hybrid" | "semantic" | "lexical">("hybrid");
  const [topK, setTopK] = useState(5);

  // Step 5: Test Preview State
  const [testInput, setTestInput] = useState("");
  const [testMessages, setTestMessages] = useState<Array<{ role: "user" | "assistant"; content: string; citations?: any[] }>>([]);
  const [testStreaming, setTestStreaming] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const testChatEndRef = useRef<HTMLDivElement>(null);

  // Submitting state
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Load templates on mount
  useEffect(() => {
    if (!isOpen) return;
    setLoadingTemplates(true);
    api
      .listTemplates()
      .then((res) => {
        setTemplates(res.templates);
      })
      .catch((err) => {
        console.error("Failed to load templates", err);
      })
      .finally(() => setLoadingTemplates(false));
  }, [isOpen]);

  // When a template is selected, apply its defaults
  const handleSelectTemplate = (tmpl: AssistantTemplate | null) => {
    setSelectedTemplate(tmpl);
    if (tmpl) {
      setName(tmpl.name);
      setDescription(tmpl.description);
      setAudienceLevel(tmpl.intended_audience || "general");
      setResponseStyle(tmpl.default_response_style || "balanced");
      setUncertaintyBehavior(tmpl.default_uncertainty_behavior || "admit");
      setCitationStyle(tmpl.default_citation_style || "strict");
      setSystemPrompt(tmpl.default_instructions);
      setRetrievalMode((tmpl.default_retrieval_mode as any) || "hybrid");
      setTopK(tmpl.default_top_k || 5);
      setTemperature(tmpl.default_temperature || 0.4);
    } else {
      // Custom Domain Blank Blueprint
      setName("");
      setDescription("");
      setAudienceLevel("general");
      setResponseStyle("balanced");
      setUncertaintyBehavior("admit");
      setCitationStyle("strict");
      setSystemPrompt("You are an intelligent and helpful domain assistant.");
      setRetrievalMode("hybrid");
      setTopK(5);
      setTemperature(0.5);
    }
  };

  // Test message execution in Step 5
  const handleSendTest = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!testInput.trim() || testStreaming) return;

    const query = testInput.trim();
    setTestInput("");
    setTestError(null);
    setTestStreaming(true);

    const userEntry = { role: "user" as const, content: query };
    const assistantEntry = { role: "assistant" as const, content: "", citations: [] };
    setTestMessages((prev) => [...prev, userEntry, assistantEntry]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      await api.streamPreviewTest(
        {
          message: query,
          system_prompt: systemPrompt,
          llm_provider: llmProvider,
          default_model: defaultModel,
          temperature,
          max_tokens: maxTokens,
          retrieval_mode: retrievalMode,
          top_k: topK,
          knowledge_base_ids: selectedKBIds,
        },
        (event, data) => {
          if (event === "token" && data.delta) {
            setTestMessages((prev) => {
              if (prev.length === 0) return prev;
              const next = [...prev];
              const last = next[next.length - 1];
              if (last.role === "assistant") {
                next[next.length - 1] = {
                  ...last,
                  content: last.content + data.delta,
                };
              }
              return next;
            });
          } else if (event === "retrieval_complete" && data.citations) {
            setTestMessages((prev) => {
              if (prev.length === 0) return prev;
              const next = [...prev];
              const last = next[next.length - 1];
              if (last.role === "assistant") {
                next[next.length - 1] = {
                  ...last,
                  citations: data.citations,
                };
              }
              return next;
            });
          } else if (event === "message_error") {
            setTestError(data.error || "Generation error");
          }
        },
        controller.signal
      );
    } catch (err: any) {
      if (err.name !== "AbortError") {
        setTestError(err.message || "Failed to communicate with preview engine");
      }
    } finally {
      setTestStreaming(false);
      abortControllerRef.current = null;
    }
  };

  const handleSaveAssistant = async () => {
    if (!name.trim()) {
      setSaveError("Assistant name is required");
      setStep(2);
      return;
    }

    setSaving(true);
    setSaveError(null);

    try {
      const created = await api.createAssistant({
        name: name.trim(),
        description: description.trim() || undefined,
        template_id: selectedTemplate ? selectedTemplate.id : undefined,
        audience_level: audienceLevel,
        response_style: responseStyle,
        uncertainty_behavior: uncertaintyBehavior,
        citation_style: citationStyle,
        llm_provider: llmProvider,
        default_model: defaultModel,
        temperature,
        max_tokens: maxTokens,
        visibility: "workspace",
        retrieval_mode: retrievalMode,
        top_k: topK,
        system_prompt: systemPrompt.trim() || undefined,
        knowledge_base_ids: selectedKBIds,
      });

      onSuccess(created);
      onClose();
    } catch (err: any) {
      setSaveError(err.message || "Failed to save assistant");
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  const filteredTemplates =
    selectedCategory === "All"
      ? templates
      : templates.filter((t) => t.category.toLowerCase() === selectedCategory.toLowerCase());

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 md:p-6 bg-gray-900/50 backdrop-blur-xs animate-fadeIn">
      <div className="bg-white border border-gray-200 rounded-3xl max-w-4xl w-full shadow-2xl flex flex-col max-h-[92vh] overflow-hidden text-gray-900">
        {/* Header Bar */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-gray-900 tracking-tight">Assistant Studio &middot; Guided Creation</h2>
              <p className="text-[11px] text-gray-500">
                Step {step} of 5 &middot;{" "}
                {step === 1 && "Choose Purpose & Template"}
                {step === 2 && "Define Identity & Audience"}
                {step === 3 && "Attach Knowledge (Optional)"}
                {step === 4 && "Configure Behavior & Tone"}
                {step === 5 && "Test Preview & Launch"}
              </p>
            </div>
          </div>

          {/* Stepper Progress Badges */}
          <div className="hidden sm:flex items-center gap-1.5 bg-gray-100 p-1 rounded-xl border border-gray-200 text-[11px] font-mono">
            {[1, 2, 3, 4, 5].map((s) => (
              <button
                key={s}
                onClick={() => setStep(s as any)}
                className={`w-6 h-6 rounded-lg flex items-center justify-center font-bold transition ${
                  step === s
                    ? "bg-blue-600 text-white shadow-xs"
                    : s < step
                    ? "bg-white text-blue-600 border border-gray-200"
                    : "text-gray-400"
                }`}
              >
                {s < step ? <Check className="w-3.5 h-3.5" /> : s}
              </button>
            ))}
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-500 hover:text-gray-800 transition cursor-pointer"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 bg-white">
          {/* =============================================================== */}
          {/* STEP 1: PURPOSE & TEMPLATE SELECTION                            */}
          {/* =============================================================== */}
          {step === 1 && (
            <div className="space-y-5 animate-fadeIn">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div>
                  <h3 className="text-base font-bold text-gray-900 tracking-tight">What kind of assistant are you building?</h3>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Select a purpose template with proven pedagogical or operational guidelines, or start custom.
                  </p>
                </div>

                {/* Category Pills */}
                <div className="flex items-center gap-1 bg-gray-100 p-1 rounded-xl border border-gray-200 text-xs">
                  {["All", "Education", "Business", "Personal", "Domain"].map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => setSelectedCategory(cat)}
                      className={`px-3 py-1 rounded-lg font-medium transition cursor-pointer ${
                        selectedCategory === cat
                          ? "bg-white text-blue-600 font-semibold shadow-xs"
                          : "text-gray-600 hover:text-gray-900"
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              </div>

              {/* Template Cards Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {/* Custom Blank Option */}
                <div
                  onClick={() => handleSelectTemplate(null)}
                  className={`p-4 rounded-2xl border transition cursor-pointer flex flex-col justify-between select-none shadow-xs ${
                    selectedTemplate === null
                      ? "border-blue-600 bg-blue-50/40 ring-1 ring-blue-600/30"
                      : "border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50/60"
                  }`}
                >
                  <div>
                    <div className="w-8 h-8 rounded-xl bg-gray-100 text-gray-700 flex items-center justify-center mb-3 border border-gray-200">
                      <Sliders className="w-4 h-4" />
                    </div>
                    <h4 className="text-xs font-bold text-gray-900">Custom Domain Assistant</h4>
                    <p className="text-[11px] text-gray-500 mt-1 leading-relaxed">
                      Blank canvas with standard hybrid defaults. Configure from scratch without pre-set rules.
                    </p>
                  </div>
                  <div className="mt-3 pt-2 border-t border-gray-100 flex items-center justify-between text-[10px] text-gray-400 font-mono">
                    <span>Category: Custom</span>
                    <span>General</span>
                  </div>
                </div>

                {/* Registered Templates */}
                {filteredTemplates.map((tmpl) => {
                  const isSelected = selectedTemplate?.id === tmpl.id;
                  return (
                    <div
                      key={tmpl.id}
                      onClick={() => handleSelectTemplate(tmpl)}
                      className={`p-4 rounded-2xl border transition cursor-pointer flex flex-col justify-between select-none shadow-xs ${
                        isSelected
                          ? "border-blue-600 bg-blue-50/40 ring-1 ring-blue-600/30"
                          : "border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50/60"
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <div className="w-8 h-8 rounded-xl bg-blue-50 border border-blue-100 text-blue-600 flex items-center justify-center">
                            {tmpl.category === "Education" && <GraduationCap className="w-4 h-4" />}
                            {tmpl.category === "Business" && <Briefcase className="w-4 h-4" />}
                            {tmpl.category === "Personal" && <User className="w-4 h-4" />}
                            {tmpl.category === "Domain" && <Compass className="w-4 h-4" />}
                          </div>
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-gray-100 text-gray-700 border border-gray-200">
                            {tmpl.category}
                          </span>
                        </div>
                        <h4 className="text-xs font-bold text-gray-900">{tmpl.name}</h4>
                        <p className="text-[11px] text-gray-500 mt-1 leading-relaxed line-clamp-3">
                          {tmpl.description}
                        </p>
                      </div>

                      <div className="mt-3 pt-2 border-t border-gray-100 flex items-center justify-between text-[10px] text-gray-400 font-mono">
                        <span>Audience: {tmpl.intended_audience}</span>
                        <span className="text-blue-600 font-semibold">{tmpl.default_response_style}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* =============================================================== */}
          {/* STEP 2: AUDIENCE & IDENTITY                                     */}
          {/* =============================================================== */}
          {step === 2 && (
            <div className="max-w-xl mx-auto space-y-5 animate-fadeIn">
              <div>
                <h3 className="text-base font-bold text-gray-900 tracking-tight">Name & Audience</h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  Who is this assistant for, and what should it be called?
                </p>
              </div>

              <div className="space-y-4 text-xs">
                <div>
                  <label className="block text-gray-700 font-semibold mb-1">
                    Assistant Name <span className="text-blue-600">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Molecular Genetics Tutor, Acme People Guide"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-blue-600 focus:ring-1 focus:ring-blue-600 outline-none transition"
                  />
                </div>

                <div>
                  <label className="block text-gray-700 font-semibold mb-1">Scope & Description</label>
                  <textarea
                    rows={2}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Brief description of what this assistant does..."
                    className="w-full px-3.5 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-blue-600 focus:ring-1 focus:ring-blue-600 outline-none resize-none transition"
                  />
                </div>

                <div>
                  <label className="block text-gray-700 font-semibold mb-1">Intended Audience</label>
                  <select
                    value={audienceLevel}
                    onChange={(e) => setAudienceLevel(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-blue-600 focus:ring-1 focus:ring-blue-600 outline-none transition"
                  >
                    <option value="general">General Public (Accessible to everyone)</option>
                    <option value="school">School Students (Simple vocabulary & examples)</option>
                    <option value="undergraduate">University / Undergraduate (Academic rigor)</option>
                    <option value="employees">Internal Employees (Corporate context & policies)</option>
                    <option value="customers">Customers & Clients (Supportive & polite)</option>
                    <option value="researchers">Specialized Researchers (Literature review & depth)</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {/* =============================================================== */}
          {/* STEP 3: KNOWLEDGE (OPTIONAL)                                    */}
          {/* =============================================================== */}
          {step === 3 && (
            <div className="max-w-2xl mx-auto space-y-5 animate-fadeIn">
              <div>
                <h3 className="text-base font-bold text-gray-900 tracking-tight">Connect Knowledge Bases (Optional)</h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  Select knowledge bases for grounded retrieval. If you have no documents yet, you can skip this step!
                </p>
              </div>

              {/* Informational Callout */}
              <div className="p-3.5 rounded-2xl bg-blue-50 border border-blue-100 text-xs text-blue-900 flex items-start gap-2.5">
                <HelpCircle className="w-4 h-4 shrink-0 mt-0.5 text-blue-600" />
                <div>
                  <span className="font-semibold block text-gray-900">Knowledge is 100% Optional</span>
                  <span className="text-[11px] text-gray-600 block mt-0.5">
                    Assistants can operate purely on model intelligence and custom instructions. You can attach documents later at any time.
                  </span>
                </div>
              </div>

              {tenantKBs.length === 0 ? (
                <div className="p-8 rounded-2xl bg-gray-50 border border-gray-200 text-center space-y-2">
                  <Database className="w-8 h-8 text-gray-400 mx-auto" />
                  <h4 className="text-xs font-bold text-gray-800">No Knowledge Bases in Workspace</h4>
                  <p className="text-[11px] text-gray-500 max-w-sm mx-auto">
                    You can proceed without documents now and upload study materials or handbooks later in the Knowledge Studio.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  <span className="text-xs font-semibold text-gray-700 block">Available Knowledge Bases</span>
                  <div className="max-h-60 overflow-y-auto p-2 rounded-2xl bg-gray-50 border border-gray-200 space-y-1.5">
                    {tenantKBs.map((kb) => {
                      const checked = selectedKBIds.includes(kb.id);
                      return (
                        <label
                          key={kb.id}
                          className={`flex items-center gap-3 p-3 rounded-xl border transition cursor-pointer select-none text-xs ${
                            checked
                              ? "bg-blue-50/60 border-blue-600 text-gray-900"
                              : "bg-white border-gray-200 text-gray-700 hover:border-gray-300"
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedKBIds((prev) => [...prev, kb.id]);
                              } else {
                                setSelectedKBIds((prev) => prev.filter((id) => id !== kb.id));
                              }
                            }}
                            className="accent-blue-600 rounded w-4 h-4"
                          />
                          <div className="min-w-0 flex-1">
                            <span className="font-semibold block truncate text-gray-900">{kb.name}</span>
                            {kb.description && (
                              <span className="text-[11px] text-gray-500 block truncate mt-0.5">
                                {kb.description}
                              </span>
                            )}
                          </div>
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-gray-100 text-gray-700 border border-gray-200 shrink-0">
                            {kb.document_count} docs
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* =============================================================== */}
          {/* STEP 4: BEHAVIOR & CONFIGURATION (SIMPLE VS ADVANCED)            */}
          {/* =============================================================== */}
          {step === 4 && (
            <div className="space-y-5 animate-fadeIn">
              <div className="flex items-center justify-between border-b border-gray-200 pb-3">
                <div>
                  <h3 className="text-base font-bold text-gray-900 tracking-tight">Behavior & Response Style</h3>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Configure how your assistant responds to questions and handles missing information.
                  </p>
                </div>

                {/* Simple vs Advanced Toggle */}
                <div className="flex items-center bg-gray-100 p-1 rounded-xl border border-gray-200 text-xs">
                  <button
                    type="button"
                    onClick={() => setMode("simple")}
                    className={`px-3 py-1 rounded-lg font-medium transition cursor-pointer ${
                      mode === "simple" ? "bg-white text-blue-600 font-semibold shadow-xs" : "text-gray-600 hover:text-gray-900"
                    }`}
                  >
                    Simple Mode
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode("advanced")}
                    className={`px-3 py-1 rounded-lg font-medium transition cursor-pointer ${
                      mode === "advanced" ? "bg-white text-blue-600 font-semibold shadow-xs" : "text-gray-600 hover:text-gray-900"
                    }`}
                  >
                    Advanced Mode
                  </button>
                </div>
              </div>

              {/* SIMPLE MODE CONTROLS */}
              {mode === "simple" ? (
                <div className="max-w-xl mx-auto space-y-4 text-xs">
                  <div>
                    <label className="block text-gray-700 font-semibold mb-1">Response Style</label>
                    <select
                      value={responseStyle}
                      onChange={(e) => setResponseStyle(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-blue-600 focus:ring-1 focus:ring-blue-600 outline-none"
                    >
                      <option value="balanced">Balanced & Direct (Clear answers with essential context)</option>
                      <option value="socratic">Socratic & Inquisitive (Guides with questions & active recall)</option>
                      <option value="concise">Concise & Bulleted (Fast, bullet-point summaries)</option>
                      <option value="detailed">Detailed & Comprehensive (In-depth analysis & explanations)</option>
                      <option value="professional">Professional & Formal (Corporate standards)</option>
                      <option value="friendly">Warm & Empathetic (Supportive and patient)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-gray-700 font-semibold mb-1">When Information is Missing or Uncertain</label>
                    <select
                      value={uncertaintyBehavior}
                      onChange={(e) => setUncertaintyBehavior(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-blue-600 focus:ring-1 focus:ring-blue-600 outline-none"
                    >
                      <option value="admit">Honestly state: &quot;I could not find information on that&quot;</option>
                      <option value="clarify">Ask clarifying questions to narrow down the query</option>
                      <option value="synthesize">Provide general knowledge with an explicit disclaimer</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-gray-700 font-semibold mb-1">Citation Strictness</label>
                    <select
                      value={citationStyle}
                      onChange={(e) => setCitationStyle(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-blue-600 focus:ring-1 focus:ring-blue-600 outline-none"
                    >
                      <option value="strict">Strict (Always cite source documents and page numbers)</option>
                      <option value="general">General (Mention source titles when relevant)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-gray-700 font-semibold mb-1">System Instructions & Persona</label>
                    <textarea
                      rows={5}
                      value={systemPrompt}
                      onChange={(e) => setSystemPrompt(e.target.value)}
                      placeholder="Guidelines regarding role, tone, and scope..."
                      className="w-full px-3.5 py-2.5 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-blue-600 focus:ring-1 focus:ring-blue-600 outline-none resize-none font-mono text-[11px]"
                    />
                  </div>
                </div>
              ) : (
                /* ADVANCED MODE CONTROLS */
                <div className="space-y-4 text-xs">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-gray-700 font-semibold mb-1">LLM Provider</label>
                      <select
                        value={llmProvider}
                        onChange={(e) => setLlmProvider(e.target.value)}
                        className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-blue-600 focus:ring-1 focus:ring-blue-600 outline-none font-mono"
                      >
                        <option value="omniroute">OmniRoute (Local Gateway)</option>
                        <option value="openai">OpenAI (Direct BYOK)</option>
                        <option value="anthropic">Anthropic Claude (Direct BYOK)</option>
                        <option value="gemini">Google Gemini (Direct BYOK)</option>
                        <option value="groq">Groq LPU (Direct BYOK)</option>
                        <option value="mock">Offline Mock (Deterministic CPU)</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-gray-700 font-semibold mb-1">Model Name</label>
                      <input
                        type="text"
                        value={defaultModel}
                        onChange={(e) => setDefaultModel(e.target.value)}
                        className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-blue-600 focus:ring-1 focus:ring-blue-600 outline-none font-mono"
                      />
                    </div>

                    <div>
                      <label className="block text-gray-700 font-semibold mb-1">Temperature ({temperature})</label>
                      <input
                        type="range"
                        min="0.0"
                        max="1.5"
                        step="0.05"
                        value={temperature}
                        onChange={(e) => setTemperature(parseFloat(e.target.value))}
                        className="w-full accent-blue-600 mt-2"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-gray-700 font-semibold mb-1">Retrieval Mode</label>
                      <select
                        value={retrievalMode}
                        onChange={(e) => setRetrievalMode(e.target.value as any)}
                        className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-blue-600 focus:ring-1 focus:ring-blue-600 outline-none font-mono"
                      >
                        <option value="hybrid">Hybrid (BM25 + Semantic RRF)</option>
                        <option value="semantic">Semantic Only (Dense Cosine)</option>
                        <option value="lexical">Lexical Only (Full-Text FTS)</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-gray-700 font-semibold mb-1">Top-K Chunks ({topK})</label>
                      <input
                        type="number"
                        min="1"
                        max="20"
                        value={topK}
                        onChange={(e) => setTopK(parseInt(e.target.value) || 5)}
                        className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-blue-600 focus:ring-1 focus:ring-blue-600 outline-none font-mono"
                      />
                    </div>

                    <div>
                      <label className="block text-gray-700 font-semibold mb-1">Max Output Tokens</label>
                      <input
                        type="number"
                        min="64"
                        max="4096"
                        value={maxTokens}
                        onChange={(e) => setMaxTokens(parseInt(e.target.value) || 1024)}
                        className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-blue-600 focus:ring-1 focus:ring-blue-600 outline-none font-mono"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-gray-700 font-semibold mb-1">Complete System Instructions</label>
                    <textarea
                      rows={6}
                      value={systemPrompt}
                      onChange={(e) => setSystemPrompt(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-blue-600 focus:ring-1 focus:ring-blue-600 outline-none font-mono text-[11px]"
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* =============================================================== */}
          {/* STEP 5: TEST PREVIEW & LAUNCH                                   */}
          {/* =============================================================== */}
          {step === 5 && (
            <div className="space-y-4 animate-fadeIn flex flex-col h-[520px]">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-gray-900 tracking-tight">Test Sandbox</h3>
                  <p className="text-xs text-gray-500">
                    Try sending a message to verify responses before finalizing your assistant.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-blue-50 text-blue-700 border border-blue-200">
                    Model: {defaultModel}
                  </span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-gray-100 text-gray-700 border border-gray-200">
                    KBs: {selectedKBIds.length} connected
                  </span>
                </div>
              </div>

              {testError && (
                <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs">
                  {testError}
                </div>
              )}

              {/* Chat Messages Frame */}
              <div className="flex-1 overflow-y-auto p-4 rounded-2xl bg-gray-50 border border-gray-200 space-y-3 text-xs">
                {testMessages.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center p-6 text-gray-400 space-y-2">
                    <Bot className="w-8 h-8 text-gray-300" />
                    <p className="text-xs">Your assistant is ready to preview. Type a message below.</p>
                    {selectedTemplate?.suggested_starter_questions && (
                      <div className="flex flex-wrap gap-1.5 justify-center max-w-md mt-2">
                        {selectedTemplate.suggested_starter_questions.map((q, idx) => (
                          <button
                            key={idx}
                            onClick={() => {
                              setTestInput(q);
                            }}
                            className="px-2.5 py-1 rounded-lg bg-white border border-gray-200 hover:border-gray-300 text-[11px] text-gray-700 transition shadow-xs cursor-pointer"
                          >
                            &ldquo;{q}&rdquo;
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  testMessages.map((msg, i) => (
                    <div
                      key={i}
                      className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
                    >
                      <div
          className={`max-w-[85%] p-3 rounded-2xl shadow-xs ${
            msg.role === "user"
              ? "bg-blue-600 text-white rounded-br-none"
              : "bg-white border border-gray-200 text-gray-900 rounded-bl-none"
          }`}
        >
          {msg.role === "user" ? (
            <p className="whitespace-pre-wrap text-sm">{msg.content || (testStreaming && i === testMessages.length - 1 ? "..." : "")}</p>
          ) : (
            <MarkdownRenderer
              content={msg.content || ""}
              citations={msg.citations || []}
              className="text-sm"
            />
          )}
                        {msg.citations && msg.citations.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-gray-100 flex flex-wrap gap-1">
                            {msg.citations.map((c: any) => (
                              <span
                                key={c.citation_num}
                                className="px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 font-mono text-[10px] border border-blue-200"
                              >
                                [{c.citation_num}] {c.document_name}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}
                <div ref={testChatEndRef} />
              </div>

              {/* Chat Input */}
              <form onSubmit={handleSendTest} className="flex gap-2">
                <input
                  type="text"
                  value={testInput}
                  onChange={(e) => setTestInput(e.target.value)}
                  placeholder="Ask a question to test..."
                  disabled={testStreaming}
                  className="flex-1 px-3.5 py-2.5 rounded-xl bg-white border border-gray-300 text-gray-900 placeholder:text-gray-400 text-xs focus:border-blue-600 focus:ring-1 focus:ring-blue-600 outline-none transition disabled:opacity-50"
                />
                {testStreaming ? (
                  <button
                    type="button"
                    onClick={() => abortControllerRef.current?.abort()}
                    className="px-4 py-2.5 rounded-xl bg-red-600 hover:bg-red-700 text-white text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer"
                  >
                    <Square className="w-3.5 h-3.5 fill-current" />
                    <span>Stop</span>
                  </button>
                ) : (
                  <button
                    type="submit"
                    disabled={!testInput.trim()}
                    className="px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold flex items-center gap-1.5 transition disabled:opacity-50 shadow-xs cursor-pointer"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>Send</span>
                  </button>
                )}
              </form>
            </div>
          )}
        </div>

        {/* Footer Navigation */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 bg-gray-50">
          <div>
            {step > 1 && (
              <button
                type="button"
                onClick={() => setStep((s) => (s - 1) as any)}
                className="px-4 py-2 rounded-xl text-gray-600 hover:text-gray-900 text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Back</span>
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-gray-600 hover:text-gray-900 text-xs font-semibold transition cursor-pointer"
            >
              Cancel
            </button>

            {step < 5 ? (
              <button
                type="button"
                onClick={() => {
                  if (step === 2 && !name.trim()) {
                    setSaveError("Please provide an assistant name.");
                    return;
                  }
                  setSaveError(null);
                  setStep((s) => (s + 1) as any);
                }}
                className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold flex items-center gap-1.5 transition shadow-sm cursor-pointer"
              >
                <span>Continue</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            ) : (
              <button
                type="button"
                disabled={saving}
                onClick={handleSaveAssistant}
                className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold flex items-center gap-1.5 transition shadow-sm disabled:opacity-50 cursor-pointer"
              >
                <Check className="w-3.5 h-3.5" />
                <span>{saving ? "Saving Assistant..." : "Save Assistant"}</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
