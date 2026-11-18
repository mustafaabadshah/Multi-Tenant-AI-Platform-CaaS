# M28.1 — First-Time User Experience & Guided Onboarding

## 1. Principles
- **No Empty Zeros:** First-time workspaces with 0 assistants or 0 knowledge bases should never display barren zero counts without a clear call-to-action.
- **Progressive Disclosure:** Simple creation by default; advanced hyperparameters (temperature, top_k, chunk size, vector distance metrics) revealed only when toggled.
- **Immediate Path to Value:** After creating an assistant, users are placed into a working chat rather than dumped onto an empty admin page.

## 2. Onboarding Workflow Implemented
1. **Welcome Card on Overview (`/dashboard`):**
   - Automatically detects when a workspace has 0 assistants.
   - Displays a clean linear banner: *"Create your first AI Assistant"* with a direct primary button to start.
2. **Contextual Chat Guidance (`/dashboard/conversations`):**
   - If user navigates to Chat Studio before creating an assistant, displays an empty-state illustration with *"Create your first assistant"* button, eliminating raw browser alerts.
   - When an assistant exists but no messages have been sent, provides 2 clickable starter query chips:
     - *"What can you help me with?"*
     - *"Summarize key document info"*
3. **5-Step Assistant Creation Wizard (`AssistantCreationWizard`):**
   - Step 1: Purpose & Template Selection (General, Support, Engineering, HR, Sales).
   - Step 2: Name, Description, and Target Audience Level.
   - Step 3: Optional Knowledge Base connection.
   - Step 4: Persona Style (Simple vs Advanced mode toggle).
   - Step 5: Interactive Test Sandbox before saving.
