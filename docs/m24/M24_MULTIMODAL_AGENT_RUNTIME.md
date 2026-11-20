# M24 — Multimodal Agentic Runtime & Voice Conversation UX

## 1. Unified AssistantRuntime Architecture
Milestone 24 integrates text, voice transcripts, conversation document attachments, citations, and MCP/custom tools into a single coherent orchestration pipeline inside `backend/app/assistant_runtime/runtime.py`.

### Unified Orchestration Flow
```
User Input
  ├── Keyboard Text
  ├── Speech Recognition Transcript
  └── Attached Document(s)
          │
          ▼
AssistantRuntime
  ├── 1. Tenant & Conversation Authorization (strict fail-closed)
  ├── 2. Attachment Retrieval (searches conversation attachment chunks)
  ├── 3. Knowledge Base RAG Retrieval (hybrid dense/sparse vector search)
  ├── 4. Augmented Context Assembly (merges attachment & KB chunks)
  ├── 5. Tool Evaluation (custom tools & MCP server tools)
  ├── 6. Human Approval Check (high-risk tools halt for approval token)
  └── 7. SSE Event Streaming (token deltas, citations, tool states)
          │
          ▼
User Experience
  ├── Streaming Markdown Text
  ├── Verified Citations
  ├── Optional Automatic TTS (Listen / Voice Chat Modes)
  └── Interactive Approval Cards
```

## 2. Voice Interaction Modes
Four distinct interaction modes are supported directly in the chat UI:
1. **Text Mode**: Keyboard input with streaming text response.
2. **Dictation Mode**: Speech-to-text populates the editable textarea, allowing manual edits before sending.
3. **Listen Mode**: Keyboard input with assistant responses automatically read aloud via client-side TTS.
4. **Voice Conversation Mode**: Continuous voice-driven conversation loop. Microphone input is automatically transcribed and submitted; the assistant's streaming response is synthesized aloud once finalized.

## 3. Human-in-the-Loop Tool Approval Safety
In Voice Conversation mode, if an external action or high-risk tool requires human approval:
- The streaming pipeline yields `tool_approval_required`.
- The frontend immediately halts the automatic voice loop.
- The approval card renders with argument details and a cryptographic approval token.
- Automatic speech recognition is prevented from restarting until a human operator explicitly clicks "Approve & Execute" or "Deny".
- Spoken transcripts saying "yes" or "proceed" are strictly rejected as approval tokens.
