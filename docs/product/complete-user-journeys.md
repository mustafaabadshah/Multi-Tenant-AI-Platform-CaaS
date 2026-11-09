# Complete User Journeys — Personas, Workflows & Usability Standards

**Document Purpose:** Living reference detailing end-to-end user experiences for the 6 target platform personas.  
**UX Direction:** Linear × Apple Notes (restrained monochrome, clear typography, zero decorative bloat).  

---

## 1. Persona 1: University Student (Exam Preparation)

### User Context
- **Name:** Liam, Computer Science & Biology Undergraduate
- **Needs:** Turn 300 pages of biochemistry lecture notes and textbook chapters into an interactive quiz partner that helps him identify knowledge gaps without hallucinating.

### End-to-End Workflow
1. **Sign In & Workspace Selection:** Liam signs into his personal workspace.
2. **Knowledge Upload:** In **Knowledge Studio**, Liam clicks "New Knowledge Base", names it "Biochemistry 201", and drags 4 PDF lecture decks. Ingestion begins immediately, showing real-time extraction, chunking, and embedding progress.
3. **Chunk Inspection:** Liam opens the **Chunk Inspector** to verify that amino acid chemical structures and diagram summaries were cleanly segmented.
4. **Assistant Creation:** Liam clicks "New Assistant", picks the **"Student Exam Prep"** template.
   - *Step 1 (Identity):* Names it "Biochem Quizzer", sets tone to "Encouraging & Socratic".
   - *Step 2 (Knowledge):* Selects "Biochemistry 201".
   - *Step 3 (Behavior):* Leaves settings in Simple mode (Audience: "Undergraduate", Uncertainty: "Strictly admit when answer is not in notes", Citations: "Always include footnote citations").
   - *Step 4 (Model):* Selects "Groq LPU Engine" with `llama-3.3-70b-versatile` for instantaneous streaming responses.
5. **Interactive Testing:** In the Assistant Studio preview pane, Liam types: *"Quiz me on the rate-limiting step of glycolysis."*
   - Assistant answers with Socratic guidance, citing Slide 14 of Lecture 3 with an exact snippet.
6. **Publishing / Sharing:** Liam clicks the **Publish** tab:
   - Selects **"Public Web Link"**.
   - Clicks "Publish Assistant". The platform generates a clean link: `https://platform.domain/p/biochem-exam-prep-9f2b`.
   - Liam opens the link on his mobile phone on the campus shuttle and quizzes himself on the go.

---

## 2. Persona 2: Secondary School Teacher (MCQ & Quiz Generation)

### User Context
- **Name:** Elena, 10th Grade History & Social Studies Teacher
- **Needs:** Generate 20 multiple-choice questions from the World War II syllabus with verified answer keys and page references to the authorized school curriculum.

### End-to-End Workflow
1. **Creation via Template:** Elena clicks "Create Assistant" and selects the **"MCQ & Exam Generator"** template.
2. **Knowledge Attachment:** Elena selects the school district's approved history curriculum PDF.
3. **Prompt & Behavior Configuration:** Elena sets:
   - Response Style: "Structured JSON / Markdown Question Format".
   - Strict Grounding: "Reject queries outside syllabus; generate 4 options per question with exactly 1 correct answer and justification."
4. **Testing in Studio:** Elena submits: *"Generate 5 MCQs on the Battle of Midway."*
   - Assistant streams 5 well-formatted questions, bolding the correct answer and citing page 182 of the syllabus.
5. **Publishing to Fellow Faculty:** Elena selects **"Workspace Members"** visibility so other teachers in her department can use the generator without making it publicly discoverable to students.

---

## 3. Persona 3: Enterprise HR Administrator (Internal Policies)

### User Context
- **Name:** Marcus, Head of People Operations at TechCorp (1,200 employees)
- **Needs:** Deploy an internal policy assistant for employee benefits, leave policies, and travel expenses while ensuring sensitive executive compensation files remain strictly confidential.

### End-to-End Workflow
1. **Department Setup:** Marcus verifies that the "Human Resources" department and "Executive Leadership" groups exist under `/dashboard/departments`.
2. **Knowledge Partitioning:**
   - Ingests `Employee_Handbook_2026.pdf` with `access_level="INTERNAL"` (all employees).
   - Ingests `Executive_Bonus_Structure.pdf` restricted specifically to `department_id="HR"` and `access_level="RESTRICTED"`.
3. **Assistant Configuration:** Creates "TechCorp People Assistant", attaches the HR Knowledge Base.
4. **Publishing Scope:** Selects visibility **"Workspace Members"**.
5. **Security Validation:**
   - When an ordinary engineering employee queries *"What are my parental leave benefits?"*, the assistant cites page 22 of the handbook.
   - When the same employee queries *"What was the VP of Sales bonus target?"*, the retrieval authorizer automatically discards restricted chunks. The assistant responds: *"I cannot find information about executive bonus structures in the company handbook."*

---

## 4. Persona 4: Customer Support Lead (Website Embed Widget)

### User Context
- **Name:** Chloe, Customer Success Director at a SaaS startup
- **Needs:** Ingest public help center articles and embed a floating chat bubble on `https://acme.com/support` that answers product questions 24/7.

### End-to-End Workflow
1. **URL Ingestion:** Chloe uses the **Safe URL Ingestion** tool to ingest 25 documentation pages from `https://docs.acme.com`. The SSRF engine verifies destination safety, validates TLS, parses titles, and indexes content.
2. **Assistant Tuning:** Chloe picks the **"Customer Support Specialist"** template, sets friendly conversational tone, and configures a greeting: *"Hi there! How can I help you with Acme today?"*.
3. **Publishing & Embed Configuration:**
   - In the **Publish** tab, Chloe toggles visibility to **"Public"**.
   - Toggles **"Enable Website Embed Widget"**.
   - Enters Allowed Domains: `acme.com`, `docs.acme.com`, `localhost:3000`.
   - Sets Brand Accent Color: `#0284c7` (Sky Blue).
   - Platform generates embed code:
     ```html
     <script src="https://platform.domain/embed.js" data-assistant="pub-78a1c9e4" async></script>
     ```
4. **Immediate Revocation Guard:** If Chloe detects an unexpected model behavior or needs to update documentation, she clicks **"Unpublish"** in the Studio; all external widgets immediately display a friendly maintenance notice within 0ms.

---

## 5. Persona 5: Professional Researcher (Source Grounding)

### User Context
- **Name:** Dr. Aris, Biotech Research Fellow
- **Needs:** Extract and cross-reference clinical trial methodologies across 50 scientific papers, verifying every claim with paragraph-level provenance.

### End-to-End Workflow
1. **Ingestion & Inspection:** Dr. Aris uploads research papers in PDF format.
2. **Chunk Inspector Analysis:** In Knowledge Studio, Dr. Aris opens the **Chunk Inspector** to inspect chunk indices, token counts, and heading paths.
3. **Retrieval Playground Testing:** Before querying the assistant, Dr. Aris uses the **Retrieval Playground** to compare lexical search (`ts_rank_cd`), semantic cosine distance, and reciprocal rank fusion (RRF) for query *"dosage titration protocol"*.
4. **Assistant Inference:** Assistant is set to "Strict Academic" citation style with top-K=8 chunks and temperature=0.2. Every generated paragraph is mapped directly to a numbered citation footnote.

---

## 6. Persona 6: Software Developer (API & SDK Integration)

### User Context
- **Name:** Devin, Full-Stack Software Engineer
- **Needs:** Connect an AI assistant into a mobile application backend without managing RAG vector storage or provider credential complexity.

### End-to-End Workflow
1. **Provision API Key:** In `/dashboard/settings`, Devin navigates to **Developer API Keys**, clicks "Generate New Key", selects scopes `["assistant:read", "assistant:chat"]`, and names it `Mobile-App-Production`.
2. **One-Time Secret Copy:** The platform generates `mmaip_sec_99a8b7c6d5e4f3a2b1...`. Devin copies the secret and saves it in his app's `.env`. The platform stores only the SHA-256 hash.
3. **SDK Integration (TypeScript):**
   ```typescript
   import { MMAIPClient } from "@mmaip/client";

   const client = new MMAIPClient({
     apiKey: process.env.MMAIP_API_KEY,
     baseUrl: "https://api.platform.domain",
   });

   const stream = await client.assistants.streamChat("asst-88f2b1a0", {
     message: "Summarize today's product release notes",
   });

   for await (const token of stream) {
     process.stdout.write(token.delta);
   }
   ```
4. **Usage Monitoring:** Devin visits `/dashboard/providers` and views real-time token consumption, request counts, and quota headroom categorized under `traffic_type="developer_api"`.
