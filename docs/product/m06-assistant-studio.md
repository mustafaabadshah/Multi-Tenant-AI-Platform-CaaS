# M06: Assistant Studio & Guided Creation Specification

## 1. Executive Summary

Milestone M06 transitions the Multi-Tenant AI Platform from a raw technical RAG foundation to a complete, customer-facing **Assistant Studio**. Ordinary users—students, tutors, HR personnel, operations managers, and business owners—can discover, configure, test, version, and manage AI assistants tailored to their specific domains without needing to understand vector databases, embeddings, or retrieval algorithms.

---

## 2. Design System: Linear × Apple Notes

The Assistant Studio follows a disciplined, minimalist design philosophy:
- **Palette**: Deep slate backgrounds (`#020617`, `#090a0f`), crisp white typography (`#f8fafc`), subtle borders (`#1e293b`), and Sky Blue (`#38bdf8`) accents for focus and primary action states.
- **Visual Hierarchy**: Low visual noise, structured information density, and unambiguous interaction targets.
- **Dual-Experience Model**:
  - **Studio Workspace**: Full lifecycle management, persona prompt definition, 4-tier prompt safety visualization, model tuning, and an auditable configuration version history with forward rollback.
  - **Chat Sandbox**: Interactive real-time conversational testing with streaming tokens, inline citations (`[1]`), and visual document context inspection.

---

## 3. Data-Driven Assistant Template Registry

Rather than hardcoded forms, M06 introduces an extensible, versioned registry (`app/templates/registry.py`) providing 12 initial purpose-built blueprints across 4 core categories:

### Education
1. **Student Exam Preparation (`exam_prep`)**: Active recall coaching, Socratic follow-up questions, and strict citations of course lecture slides.
2. **Subject Tutor (`subject_tutor`)**: Concept exploration with intuitive analogies and adaptive difficulty levels.
3. **MCQ & Exam Generator (`mcq_generator`)**: Generates structured multiple-choice questions with answer keys and diagnostic explanations.
4. **Notes & Textbook Assistant (`notes_textbook`)**: Synthesizes textbook chapters, generates summaries, and highlights key formulas/definitions.

### Business
5. **HR & Employee Handbook (`hr_handbook`)**: Grounds responses strictly in approved company policies; explicitly admits lack of documentation rather than hallucinating employment rules.
6. **Internal Company Knowledge (`company_knowledge`)**: Cross-departmental knowledge assistant connecting documentation across engineering, product, and operations.
7. **Customer Support (`customer_support`)**: Professional, empathetic tone providing accurate troubleshooting steps without unsupported commitments.
8. **SOP & Operations Assistant (`sop_operations`)**: Step-by-step procedural compliance for standard operating procedures and incident response.

### Personal & Professional
9. **Personal Document Assistant (`personal_vault`)**: Private document analysis (contracts, leases, financial statements) with strict confidentiality and explicit citations.
10. **Research Assistant (`research_assistant`)**: Rigorous academic analysis separating source-backed findings from general inferences.

### Domain & Specialized
11. **Sports Knowledge Assistant (`sports_coach`)**: Rules, training methodology, tactical breakdowns, and performance tracking.
12. **Custom Domain Assistant (`custom_domain`)**: Blank blueprint allowing customized instructions, response styles, and optional knowledge.

---

## 4. Five-Step Assistant Creation Wizard

The creation experience is divided into five logical, low-friction steps:

```
[ Step 1: Purpose ]  -->  [ Step 2: Audience ]  -->  [ Step 3: Knowledge (Optional) ]  -->  [ Step 4: Behavior ]  -->  [ Step 5: Test & Launch ]
  Choose Template           Name, Description,       Select Knowledge Bases (or 0)           Simple vs Advanced          Live SSE Sandbox Preview
  or Custom Blueprint       Intended Level           General instructions without files      Safe Defaults Applied       One-Click Save
```

1. **Purpose**: Filter templates by category (Education, Business, Personal, Domain) or select the blank blueprint.
2. **Audience**: Define assistant identity, domain focus, and audience level (beginner, intermediate, advanced, academic).
3. **Knowledge (Strictly Optional)**: Users can attach existing tenant knowledge bases or proceed without uploading any files. Assistants are fully functional purely from model knowledge and custom instructions.
4. **Behavior**:
   - **Simple Mode**: Intuitive sliders and selectors for Tone/Response Style (friendly, professional, academic, concise, socratic), Uncertainty Handling (admit vs clarify), and Citation Style (strict vs relaxed).
   - **Advanced Mode**: Direct control over technical parameters (Temperature, Top-K, Output Tokens, Retrieval Strategy) without losing simple settings.
5. **Test & Launch**: A real-time sandbox test using backend preview streaming (`/api/v1/assistants/preview-test`) allowing users to test before finalizing.

---

## 5. Configuration Versioning & Forward Rollback

Every modification to an assistant's configuration automatically captures an immutable configuration snapshot in `assistant_versions`:
- **Forward-Only Rollback**: Rolling back to a previous version (e.g., v1 from v2) generates a new audit record (v3) containing the restored snapshot. Historical records are never deleted or rewritten.
- **Tenant Scoping**: All version queries and rollback requests are strictly scoped by `tenant_id`. Cross-tenant rollback attempts receive 404/400.
