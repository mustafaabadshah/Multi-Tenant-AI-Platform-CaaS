# User Journeys — Multi-Tenant AI Assistant Platform

**Document Version:** 1.0.0  
**Design Philosophy:** Linear × Apple Notes (Simple by default, powerful when needed)  
**Target Personas:** Student (Education), HR Manager (Business), AI Engineer (Technical), Business Owner (Publishing)  

---

## 1. Journey 1: Undergraduate Student Creating an Exam Prep Assistant

### 1.1 Goal & Persona Profile
- **User:** Maya, a 3rd-year Biology undergraduate preparing for Molecular Genetics exams.
- **Technical Literacy:** Non-technical; has no knowledge of RAG, vector databases, chunking, or tokens.
- **Objective:** Upload lecture slide PDFs and a textbook chapter, create an interactive study partner that tests her knowledge with practice questions, active recall drills, and concise explanations with page references.

### 1.2 Step-by-Step Experience

```
[Start Dashboard] ──> [Click "Create Assistant"] ──> [Select "Exam Prep" Template]
         │
         ▼
[Drop Lecture Slides & Syllabus PDF] ──> [Choose Tone: "Socratic & Concise"]
         │
         ▼
[Click "Start Studying"] ──> [Interactive Quiz & Instant Citation Verification]
```

1. **Discovery & Template Selection:**
   - Maya opens the platform dashboard. She clicks the primary action button: `+ New Assistant`.
   - The **Assistant Studio Wizard** opens with sensible visual cards. She selects the **Education** category and clicks **"Exam Prep & Flashcard Tutor"**.
   - *System Action:* Pre-fills the assistant instructions with proven pedagogical guidelines (active recall, asking follow-up questions, never giving away answers immediately, citing specific slide pages).

2. **Knowledge Ingestion (Simple Dropzone):**
   - The wizard presents Step 2: "Add Your Study Materials".
   - Maya drags and drops `Genetics_Lectures_1_to_8.pdf` and `Syllabus_Fall2026.pdf`.
   - The UI shows clean, Apple Notes-style progress pills:
     `Genetics_Lectures_1_to_8.pdf` (142 pages) — `Extracting Text → Ready (412 Chunks)`
   - Maya is not asked about chunk sizes or embedding models; the system automatically applies recursive text splitting and CPU embeddings.

3. **Persona & Response Style:**
   - Step 3 asks two simple questions:
     - *Response Style:* Maya selects `Socratic (Test me with questions)`.
     - *Strictness:* Maya toggles `Only answer from my uploaded notes` to prevent extraneous textbook material from confusing her syllabus focus.

4. **Studying & Chatting:**
   - Maya clicks `Complete & Open Chat`.
   - She types: *"Quiz me on CRISPR-Cas9 mechanism of action from Lecture 4."*
   - The assistant immediately streams a targeted question:
     > *"Let's test your understanding of Cas9 cleavage. What specific sequence motif must be adjacent to the target DNA for Cas9 to bind, and what enzyme creates the double-strand break? [1]"*
   - Maya clicks citation pill `[1]`. The **Citation Inspector** modal opens, highlighting Slide 18 of `Genetics_Lectures_1_to_8.pdf` with the PAM sequence diagram in crisp focus.
   - Maya answers, receives immediate constructive feedback, and continues her exam prep seamlessly.

---

## 2. Journey 2: HR Manager Creating an Employee Policy Assistant

### 2.1 Goal & Persona Profile
- **User:** David, HR Director at an 80-person logistics enterprise.
- **Technical Literacy:** Business operator; comfortable with SaaS tools, permissions, and company confidentiality.
- **Objective:** Deploy an internal assistant that accurately answers employee questions about parental leave, health insurance, remote work policies, and expense limits, restricted to authenticated employees.

### 2.2 Step-by-Step Experience

```
[Organization Workspace] ──> [Create Assistant: "HR Policy Guide"]
         │
         ▼
[Select Template: "Company Handbook & HR"] ──> [Attach "Employee_Handbook_2026.docx"]
         │
         ▼
[Set Access: "All Employees"] ──> [Configure Refusal Rule: "Escalate to hr@company.com"]
         │
         ▼
[Test in Sandbox] ──> [Publish to Workspace Directory]
```

1. **Assistant Setup:**
   - David navigates to his organization workspace: `Acme Logistics`.
   - He selects `+ New Assistant` and chooses the **"Company Handbook & Policy"** template.
   - Name: `Acme People Guide`.
   - Description: `Your friendly assistant for Acme employee benefits, leave policies, and workplace guidelines.`

2. **Connecting Verified Knowledge:**
   - David connects the existing company knowledge base: `Acme Corporate Policies`, containing `Employee_Handbook_2026.docx`, `Health_Benefits_Guide.pdf`, and `Travel_Expense_Policy.xlsx`.
   - In the upload settings, David ensures the documents are scoped to `Access: Workspace (All Employees)`.

3. **Behavior & Escalation Rules:**
   - Under "Refusal & Escalation Behavior", David selects:
     - *When information is missing:* `State that the policy is not in the handbook and instruct the employee to email hr@acmelogistics.com`.
     - *Tone:* `Warm, Professional, and Supportive`.
     - *Disclaimers:* Enabled `Include official policy disclaimer footer`.

4. **Verification & Launch:**
   - David tests a query in the side-by-side sandbox:
     - Query: *"Can I expense dinner if I work past 8 PM?"*
     - Assistant Response:
       > *"Yes. Under Acme's Travel & Expense Policy, employees working past 8:00 PM at the office are eligible for a dinner meal allowance of up to $30.00 USD. Receipts must be submitted via Expensify within 14 calendar days. [1]*
       > *[1] Travel_Expense_Policy.xlsx — Sheet: Meal Allowances, Row 14"*
   - Confident in the accuracy, David clicks `Publish to Workspace`. The assistant appears instantly on every Acme employee's dashboard sidebar.

---

## 3. Journey 3: AI Engineer Configuring Advanced Hybrid RAG & BYOK

### 3.1 Goal & Persona Profile
- **User:** Alex, Senior AI Platform Engineer.
- **Technical Literacy:** Highly technical; writes Python, understands vector embeddings, hybrid search math, and API cost optimization.
- **Objective:** Configure an ultra-fast, low-cost technical documentation assistant using Groq Llama 3.3 70B, custom chunking parameters, pgvector cosine search with BM25 hybrid reciprocal rank fusion, and inspect retrieval recall in the playground.

### 3.2 Step-by-Step Experience

```
[Workspace Settings] ──> [Add BYOK Groq API Key] ──> [Test Connection: 200 OK]
         │
         ▼
[Assistant Studio] ──> [Toggle "Advanced Mode"] ──> [Select Groq Llama 3.3 70B]
         │
         ▼
[Knowledge Studio] ──> [Chunk Inspector: Tune Chunk Size 512, Overlap 64]
         │
         ▼
[Retrieval Playground] ──> [Inspect FTS vs. Dense Cosine Scores & RRF Rank]
         │
         ▼
[Evaluation Studio] ──> [Run 20 Test Questions: 95% Recall, 0.42s Avg Latency]
```

1. **Connecting Custom BYOK Credentials:**
   - Alex opens `/dashboard/settings/providers`.
   - Under **Bring Your Own Key (BYOK)**, he selects `Groq Cloud`.
   - He pastes his API key and clicks `Test Connection`. The system initiates a lightweight ping (`model="llama-3.3-70b-versatile"`, `max_tokens=1`), returning `Connected (142ms latency)`.
   - The key is encrypted via AES-256-GCM and stored in the tenant vault.

2. **Advanced Assistant Configuration:**
   - Alex navigates to `Assistants` and creates `Docs-Engine-V1`.
   - He toggles the **"Advanced Mode"** switch at the top right.
   - The interface reveals granular technical inputs:
     - *Provider:* `Groq`
     - *Model:* `llama-3.3-70b-versatile`
     - *Temperature:* `0.1` (deterministic factual retrieval)
     - *Max Tokens:* `2048`
     - *Retrieval Mode:* `Hybrid (BM25 + Semantic pgvector)`
     - *Top-K Chunks:* `8`
     - *RRF K-Constant:* `60`
     - *Dense/Sparse Weight Balance:* `0.7 Dense / 0.3 Lexical`

3. **Chunk Inspection & Tuning:**
   - Alex opens the connected Knowledge Base and navigates to the **Chunk Inspector** tab.
   - He uploads `Kubernetes_Architecture_Manual.pdf`.
   - He previews chunk boundaries: with `chunk_size=512` and `chunk_overlap=64`, he confirms that section headings like `## Control Plane Components` are preserved in `heading_path` metadata.

4. **Retrieval Playground & Evaluation:**
   - Alex opens the **Retrieval Playground** tab.
   - He submits query: *"How does kube-scheduler handle node affinity?"*
   - The playground displays a split matrix:
     - *Dense Cosine Score:* 0.842 (Rank 1)
     - *PostgreSQL BM25 Score:* 14.28 (Rank 2)
     - *Fused RRF Rank:* Score 0.0328 (Rank 1 overall)
     - *Token Budget:* 1,420 / 8,000 tokens utilized.
   - Satisfied, Alex exports the assistant configuration to his team's CI/CD evaluation runner.

---

## 4. Journey 4: Small Business Owner Embedding a Support Chatbot

### 4.1 Goal & Persona Profile
- **User:** Elena, owner of a boutique design agency (Elena Studios).
- **Technical Literacy:** Moderate; manages a Webflow website and customer CRM.
- **Objective:** Deploy a 24/7 client onboarding chatbot on her public website that answers pricing questions, schedules consultations, and collects client emails.

### 4.2 Step-by-Step Experience

```
[Create Assistant: "Elena Studios Concierge"] ──> [Upload Portfolio & Service Pricing PDF]
         │
         ▼
[Configure Lead Capture: Collect Name & Email] ──> [Publish: "Public Embed Widget"]
         │
         ▼
[Customize Branding: Theme Black/Blue, Position Bottom-Right]
         │
         ▼
[Copy <script> Tag] ──> [Paste into Webflow Custom Code] ──> [Live on Website]
```

1. **Creating the Public Concierge:**
   - Elena creates an assistant named `Elena Studios Concierge`.
   - Template: **"Customer Support & Inquiries"**.
   - Knowledge: Uploads `Services_Pricing_2026.pdf` and `Design_Process_FAQ.docx`.

2. **Publishing Configuration:**
   - Under the **Publish & Share** tab, Elena sets:
     - *Visibility:* `Public`
     - *Allowed Domains:* `elenastudios.com, www.elenastudios.com`
     - *Lead Capture Form:* Enabled (asks visitor for Name and Work Email before conversation turn 3).
     - *Greeting Message:* *"Hello! I'm Elena's virtual studio assistant. How can I help you bring your brand to life today?"*

3. **Widget Customization & Embed Code:**
   - Elena previews the live widget in the interactive preview panel.
   - She selects `Theme: Dark (Linear Black)`, `Accent: Electric Blue`, `Position: Bottom Right`.
   - She clicks `Copy Embed Code`:
     ```html
     <!-- Multi-Tenant AI Platform Widget -->
     <script
       src="https://platform.domain.com/widget/embed.js"
       data-assistant="asst_7f8a9b2c"
       data-theme="dark"
       data-accent="#38bdf8"
       async>
     </script>
     ```
   - She pastes the script into her Webflow site header. Within two minutes, her website visitors are receiving instant answers with verified portfolio references.
