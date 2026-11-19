"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  api,
  AssistantItem,
  AssistantTemplate,
  KnowledgeBaseItem,
} from "@/lib/api";
import {
  Bot,
  Database,
  Sliders,
  Check,
  X,
  Sparkles,
  MessageSquare,
  ArrowRight,
  ShieldCheck,
  Layers,
} from "lucide-react";
import Button from "@/components/ui/Button";
import Spinner from "@/components/ui/Spinner";

interface AssistantCreationWizardProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (assistant: AssistantItem) => void;
  onStartChat?: (assistant: AssistantItem) => void;
  tenantKBs: KnowledgeBaseItem[];
}

export default function AssistantCreationWizard({
  isOpen,
  onClose,
  onSuccess,
  onStartChat,
  tenantKBs,
}: AssistantCreationWizardProps) {
  const router = useRouter();

  // Basic required fields
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  // Optional fields
  const [selectedKBIds, setSelectedKBIds] = useState<string[]>([]);
  const [templates, setTemplates] = useState<AssistantTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("");
  const [loadingTemplates, setLoadingTemplates] = useState(false);

  // Progressive Disclosure: Advanced settings
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState("");
  const [llmProvider, setLlmProvider] = useState("omniroute");
  const [defaultModel, setDefaultModel] = useState("auto");
  const [temperature, setTemperature] = useState(0.5);
  const [retrievalMode, setRetrievalMode] = useState<"hybrid" | "semantic" | "lexical">("hybrid");

  // State: saving and created result
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [createdAssistant, setCreatedAssistant] = useState<AssistantItem | null>(null);

  // Load templates on mount
  useEffect(() => {
    if (!isOpen) return;
    setLoadingTemplates(true);
    setCreatedAssistant(null);
    setSaveError(null);
    api
      .listTemplates()
      .then((res) => {
        setTemplates(res.templates || []);
      })
      .catch((err) => {
        console.error("Failed to load templates", err);
      })
      .finally(() => setLoadingTemplates(false));
  }, [isOpen]);

  const handleSelectTemplate = (templateId: string) => {
    setSelectedTemplateId(templateId);
    const tmpl = templates.find((t) => t.id === templateId);
    if (tmpl) {
      if (!name) setName(tmpl.name);
      if (!description) setDescription(tmpl.description);
      setSystemPrompt(tmpl.default_instructions || "");
      if (tmpl.default_temperature) setTemperature(tmpl.default_temperature);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setSaveError("Please enter an assistant name.");
      return;
    }

    setSaving(true);
    setSaveError(null);

    try {
      const created = await api.createAssistant({
        name: name.trim(),
        description: description.trim() || undefined,
        template_id: selectedTemplateId || undefined,
        llm_provider: llmProvider,
        default_model: defaultModel,
        temperature,
        max_tokens: 1024,
        visibility: "workspace",
        retrieval_mode: retrievalMode,
        top_k: 5,
        system_prompt: systemPrompt.trim() || undefined,
        knowledge_base_ids: selectedKBIds,
      });

      setCreatedAssistant(created);
    } catch (err: any) {
      setSaveError(err.message || "Failed to create assistant");
    } finally {
      setSaving(false);
    }
  };

  const handleStartChatDirectly = () => {
    if (!createdAssistant) return;
    onClose();
    if (onStartChat) {
      onStartChat(createdAssistant);
    } else {
      router.push(`/dashboard/conversations?assistantId=${createdAssistant.id}`);
    }
  };

  const handleConfigureDirectly = () => {
    if (!createdAssistant) return;
    onSuccess(createdAssistant);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 md:p-6 bg-gray-900/40 backdrop-blur-xs animate-fadeIn">
      <div className="bg-white border border-gray-200 rounded-2xl max-w-lg w-full shadow-xl flex flex-col max-h-[90vh] overflow-hidden text-gray-900">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 bg-gray-50/50">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100">
              <Bot size={16} />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-gray-900">
                {createdAssistant ? "Assistant Ready" : "Create New Assistant"}
              </h3>
              <p className="text-[11px] text-gray-500">
                {createdAssistant
                  ? "Your assistant has been created and is ready to answer questions."
                  : "Set up a grounded AI assistant in your workspace."}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body Content */}
        <div className="p-5 overflow-y-auto flex-1">
          {createdAssistant ? (
            /* Success Screen */
            <div className="py-6 text-center space-y-4">
              <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 border border-emerald-200 flex items-center justify-center mx-auto">
                <Check size={24} />
              </div>
              <div className="space-y-1">
                <h4 className="text-base font-semibold text-gray-900">
                  &ldquo;{createdAssistant.name}&rdquo; is ready
                </h4>
                <p className="text-xs text-gray-500 max-w-sm mx-auto">
                  {createdAssistant.description ||
                    "Connected to workspace models and ready for chat conversations."}
                </p>
              </div>

              <div className="p-3 bg-gray-50 rounded-xl border border-gray-200 text-xs text-gray-600 text-left space-y-1 font-mono text-[11px]">
                <div>Provider: {createdAssistant.llm_provider || "omniroute"} (Model: {createdAssistant.default_model || "auto"})</div>
                <div>Connected KBs: {createdAssistant.connected_kb_ids?.length || 0} Knowledge Bases</div>
              </div>

              <div className="flex flex-col sm:flex-row gap-2 pt-2 justify-center">
                <Button
                  variant="primary"
                  size="md"
                  icon={MessageSquare}
                  onClick={handleStartChatDirectly}
                >
                  Start Chatting Now
                </Button>
                <Button
                  variant="secondary"
                  size="md"
                  icon={Sliders}
                  onClick={handleConfigureDirectly}
                >
                  Configure Details
                </Button>
              </div>
            </div>
          ) : (
            /* Creation Form */
            <form onSubmit={handleCreate} className="space-y-4">
              {saveError && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs">
                  {saveError}
                </div>
              )}

              {/* Quick Template Chips (Optional) */}
              {templates.length > 0 && (
                <div className="space-y-1.5">
                  <span className="text-[11px] font-medium text-gray-500">
                    Start from blueprint (Optional):
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {templates.slice(0, 4).map((tmpl) => (
                      <button
                        key={tmpl.id}
                        type="button"
                        onClick={() => handleSelectTemplate(tmpl.id)}
                        className={`px-2.5 py-1 rounded-lg text-xs transition-colors cursor-pointer border ${
                          selectedTemplateId === tmpl.id
                            ? "bg-blue-50 border-blue-400 text-blue-700 font-medium"
                            : "bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100"
                        }`}
                      >
                        {tmpl.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Required: Name */}
              <div className="space-y-1">
                <label className="block text-xs font-medium text-gray-700">
                  Assistant Name <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  autoFocus
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Research Assistant or Engineering Helper"
                  className="w-full px-3 py-2 text-xs bg-white border border-gray-300 rounded-lg text-gray-900 placeholder:text-gray-400 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                />
              </div>

              {/* Required: Purpose / Description */}
              <div className="space-y-1">
                <label className="block text-xs font-medium text-gray-700">
                  What should this assistant help with?
                </label>
                <textarea
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g. Help our team analyze technical documents, answer questions, and summarize web articles."
                  className="w-full px-3 py-2 text-xs bg-white border border-gray-300 rounded-lg text-gray-900 placeholder:text-gray-400 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-none"
                />
              </div>

              {/* Connect Knowledge Base (Optional) */}
              <div className="space-y-1">
                <label className="block text-xs font-medium text-gray-700">
                  Connect Knowledge Base (Optional)
                </label>
                {tenantKBs.length === 0 ? (
                  <p className="text-[11px] text-gray-400">
                    No Knowledge Bases found. You can connect documents anytime later.
                  </p>
                ) : (
                  <div className="space-y-1 max-h-32 overflow-y-auto border border-gray-200 rounded-lg p-2 bg-gray-50/50">
                    {tenantKBs.map((kb) => (
                      <label
                        key={kb.id}
                        className="flex items-center gap-2 p-1.5 rounded hover:bg-white text-xs cursor-pointer text-gray-700"
                      >
                        <input
                          type="checkbox"
                          checked={selectedKBIds.includes(kb.id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedKBIds((prev) => [...prev, kb.id]);
                            } else {
                              setSelectedKBIds((prev) => prev.filter((id) => id !== kb.id));
                            }
                          }}
                          className="rounded text-blue-600 focus:ring-blue-500"
                        />
                        <span className="font-medium text-gray-800">{kb.name}</span>
                        <span className="text-[10px] text-gray-400">
                          ({kb.document_count ?? 0} docs)
                        </span>
                      </label>
                    ))}
                  </div>
                )}
              </div>

              {/* Progressive Disclosure: Advanced Settings Toggle */}
              <div className="pt-2 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="text-xs text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1 cursor-pointer"
                >
                  <Sliders size={13} />
                  <span>{showAdvanced ? "Hide Advanced Settings" : "Customize Instructions & Model"}</span>
                </button>

                {showAdvanced && (
                  <div className="mt-3 space-y-3 p-3 bg-gray-50 rounded-xl border border-gray-200 animate-fadeIn">
                    <div className="space-y-1">
                      <label className="block text-[11px] font-medium text-gray-700">
                        System Instructions / Persona
                      </label>
                      <textarea
                        rows={2}
                        value={systemPrompt}
                        onChange={(e) => setSystemPrompt(e.target.value)}
                        placeholder="e.g. You are a precise and concise AI assistant. Always ground responses in provided sources."
                        className="w-full p-2 text-xs bg-white border border-gray-300 rounded-lg text-gray-900 outline-none focus:border-blue-500 font-mono resize-none"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <label className="block text-[11px] font-medium text-gray-700">
                          Provider / Model
                        </label>
                        <select
                          value={defaultModel}
                          onChange={(e) => setDefaultModel(e.target.value)}
                          className="w-full p-1.5 text-xs bg-white border border-gray-300 rounded-lg text-gray-800 outline-none"
                        >
                          <option value="auto">auto (OmniRoute default)</option>
                          <option value="gpt-4o-mini">gpt-4o-mini</option>
                          <option value="claude-3-5-sonnet">claude-3-5-sonnet</option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-[11px] font-medium text-gray-700">
                          Retrieval Mode
                        </label>
                        <select
                          value={retrievalMode}
                          onChange={(e) => setRetrievalMode(e.target.value as any)}
                          className="w-full p-1.5 text-xs bg-white border border-gray-300 rounded-lg text-gray-800 outline-none"
                        >
                          <option value="hybrid">Hybrid (Vector + BM25)</option>
                          <option value="semantic">Semantic (Vector Only)</option>
                          <option value="lexical">Lexical (Keyword)</option>
                        </select>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-2 pt-3 border-t border-gray-100">
                <Button
                  variant="secondary"
                  size="sm"
                  type="button"
                  onClick={onClose}
                  disabled={saving}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  type="submit"
                  disabled={saving || !name.trim()}
                >
                  {saving ? "Creating Assistant..." : "Create Assistant"}
                </Button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
