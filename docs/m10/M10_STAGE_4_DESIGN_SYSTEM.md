# M10 Stage 4 — Global Design System Specification

**Project:** Multi-Tenant AI Assistant Platform (Chatbot-as-a-Service / CaaS)  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Milestone:** M10 Stage 4  
**Design Reference:** WoiceAI (`https://github.com/asdkazmi/woiceai-web`)  
**Paradigm:** Clean Light SaaS Interface, Restrained Blue Primary, Subtle Gray Borders, Collapsible Navigation  
**Date:** 2026-11-10  
**Status:** IMPLEMENTED  

---

## 1. Visual Token Architecture

The design system adopts a clean, restrained light theme as the platform default, replacing ad-hoc dark slate and glassmorphism styling while maintaining WCAG 2.1 AA accessibility ratios.

### Color Tokens

| Token | CSS Variable / Tailwind | Hex Value | Purpose |
|---|---|---|---|
| **Canvas Background** | `--background` / `bg-gray-50` | `#f9fafb` | Primary viewport background |
| **Surface (Card/Panel)** | `--card` / `bg-white` | `#ffffff` | Content containers, modals, table surfaces |
| **Primary Text** | `--foreground` / `text-gray-900` | `#111827` | Headings, primary labels, table data |
| **Secondary Text** | `--foreground-secondary` / `text-gray-700` | `#374151` | Body copy, active navigation labels |
| **Muted Text** | `--muted` / `text-gray-500` | `#6b7280` | Captions, timestamps, helper text |
| **Borders** | `--border` / `border-gray-200` | `#e5e7eb` | Standard dividers, card borders, tab rails |
| **Input Borders** | `border-gray-300` | `#d1d5db` | Unfocused form fields and inputs |
| **Primary Accent** | `--primary` / `bg-blue-600` | `#2563eb` | Primary buttons, active tabs, user chat bubbles |
| **Primary Hover** | `--primary-hover` / `hover:bg-blue-700`| `#1d4ed8` | Interactive button hover state |
| **Primary Light** | `--primary-light` / `bg-blue-50` | `#eff6ff` | Active menu pills, badge backgrounds, tag chips |
| **Success State** | `--success` / `text-emerald-700` | `#10b981` | Active status pills, verified indicators |
| **Warning State** | `--warning` / `text-amber-700` | `#f59e0b` | Pending states, quota alerts |
| **Danger State** | `--danger` / `text-red-700` | `#ef4444` | Destructive actions, error messages, delete triggers |
| **Focus Ring** | `focus:ring-2 focus:ring-blue-500/20` | Dynamic | Accessible keyboard focus indicators |

---

## 2. Reusable Component Primitive Library

All reusable primitives reside under `frontend/components/ui/` with typed interfaces:

```
frontend/components/ui/
├── Button.tsx           # Primary, secondary, danger, ghost, outline variants + loading spinner
├── Input.tsx            # Accessible text input with label, icon, and validation error
├── Card.tsx             # White surface card with subtle border and optional hover state
├── Badge.tsx            # Color-coded pill badge (blue, green, purple, amber, red, gray)
├── Spinner.tsx          # SVG animated spinner with size options (sm, md, lg)
├── Modal.tsx            # Accessible modal dialog with backdrop, title, close, and Escape key
├── ConfirmModal.tsx     # Specialized confirmation modal for destructive and caution actions
├── EmptyState.tsx       # Standard empty state placeholder with icon, description, and action
├── StatusIndicator.tsx  # Dynamic status pill with pulsing live dot
└── index.ts             # Unified barrel export
```

---

## 3. Global Application Shell Architecture

The platform navigation shell (`frontend/app/dashboard/layout.tsx`) has been unified into a professional Woice-inspired layout:

```
+---------------------------------------------------------------------------------------------------------+
| [Logo] Woice AI Platform | [Workspace Selector v] | Navigation Links ... | User Account | [Logout]      |
+---------------------------------------------------------------------------------------------------------+
| Desktop: Persistent Sidebar (Expanded 256px <-> Collapsed 64px)                                        |
| Mini-rail toggle allows operators to maximize viewport real estate for multi-column studios.           |
|                                                                                                         |
| Categorized Navigation Rail:                                                                            |
| • Workspace:                                                                                            |
|   - Overview (/dashboard)                                                                               |
|   - Assistants (/dashboard/assistants)                                                                  |
|   - Knowledge (/dashboard/knowledge)                                                                    |
|   - Conversations (/dashboard/conversations) [First-Class Chat Workspace]                              |
| • Operate:                                                                                              |
|   - Observability (/dashboard/observability)                                                            |
| • Organization:                                                                                         |
|   - Employees (/dashboard/employees)                                                                    |
|   - Departments (/dashboard/departments)                                                                |
|   - Groups (/dashboard/groups)                                                                          |
|   - Organization (/dashboard/workspace)                                                                |
| • Settings:                                                                                             |
|   - Providers & Keys (/dashboard/providers)                                                             |
|   - Audit Logs (/dashboard/audit)                                                                       |
|   - Settings (/dashboard/settings)                                                                     |
+---------------------------------------------------------------------------------------------------------+
| Sticky Top Navigation:                                                                                  |
| Active Workspace Pill | Tenant Slug | Tenant Isolated Security Pill | API Docs Link | RBAC Active Pill   |
+---------------------------------------------------------------------------------------------------------+
| Responsive Viewports:                                                                                   |
| Mobile (< 1024px): Hamburger menu opens sliding drawer with backdrop blur.                              |
| Tablet (768px - 1024px): Compact sidebar with icon tooltips prevents horizontal overflow.             |
| Desktop (>= 1024px): Full layout with collapsible mini-sidebar.                                          |
+---------------------------------------------------------------------------------------------------------+
```

---

## 4. Interaction Consistency Guidelines

1. **Direct Action:** Interactive controls must trigger immediate mutations or state updates. No placeholder links.
2. **Keyboard Accessibility:** All interactive elements support Tab focus, visible focus rings, and Escape key dialog dismissal.
3. **Real Backend Synchronization:** All metrics, counts, and lists reflect live backend state; no artificial delays or fabricated telemetry.
