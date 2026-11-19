# M28.8 Design System & Visual Quality — Linear × Apple Notes Standard

**Milestone:** M28.8  
**Date:** November 19, 2026  
**Aesthetic Standard:** Linear × Apple Notes Disciplined SaaS Design  
**Framework:** Tailwind CSS 4 (`@import "tailwindcss";`)

---

## 1. Visual Direction & Aesthetic Philosophy

The platform's design system rejects noisy consumer gradients, oversized neon badges, and arbitrary palette fragmentation in favor of a restrained, high-craft productivity tool aesthetic inspired by **Linear** and **Apple Notes**:
- **Light Theme Dominance:** Crisp white cards (`#ffffff`) floating over neutral gray canvas (`#f9fafb`).
- **Restrained Accent:** Deep Enterprise Blue (`#2563eb`, hover `#1d4ed8`, tint `#eff6ff`) used purposefully for primary interactive affordances.
- **Micro-Shadows:** Subtle elevation (`shadow-xs`: `0 1px 2px 0 rgb(0 0 0 / 0.05)`).
- **Soft Separators:** Muted borders (`#e5e7eb` / `#e2e8f0`).
- **Typography:** Apple system typography stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto`) with clear size hierarchy (Page titles 20-24px, body 13-14px, metadata 10-11px).

---

## 2. Core Design Tokens (CSS Variables)

Defined in `frontend/app/globals.css`:

```css
:root {
  --background: #f9fafb;
  --background-secondary: #ffffff;
  --foreground: #111827;
  --foreground-secondary: #374151;
  --card: #ffffff;
  --card-foreground: #111827;
  --border: #e5e7eb;
  --border-focus: #2563eb;
  --primary: #2563eb;
  --primary-hover: #1d4ed8;
  --primary-light: #eff6ff;
  --accent: #7c3aed;
  --muted: #6b7280;
  --muted-light: #f3f4f6;
  --muted-foreground: #9ca3af;
  --success: #10b981;
  --success-light: #ecfdf5;
  --warning: #f59e0b;
  --warning-light: #fffbeb;
  --danger: #ef4444;
  --danger-light: #fef2f2;
}
```

---

## 3. Reusable Component Primitives

The frontend design system relies on a unified component library in `frontend/components/ui/`:

| Component | File Path | Usage & Accessibility |
|---|---|---|
| `Button` | `frontend/components/ui/Button.tsx` | Variants: `primary`, `secondary`, `outline`, `ghost`, `danger`. Sizes: `xs`, `sm`, `md`, `lg`. Accessible focus rings. |
| `Card` | `frontend/components/ui/Card.tsx` | Minimalist border + subtle shadow surface. |
| `Modal` | `frontend/components/ui/Modal.tsx` | Accessible dialog with backdrop blur, focus trap, Esc key listener. |
| `ConfirmModal` | `frontend/components/ui/ConfirmModal.tsx` | Actionable confirmation dialog for destructive actions (e.g. deleting conversation or KB). |
| `Badge` | `frontend/components/ui/Badge.tsx` | Non-intrusive status indicators (`READY`, `PROCESSING`, `FAILED`). |
| `Spinner` | `frontend/components/ui/Spinner.tsx` | Loading states for async operations. |
| `EmptyState` | `frontend/components/ui/EmptyState.tsx` | Actionable zero-state views with descriptive iconography and primary action button. |

---

## 4. Antigravity Agent Skill Integration

A dedicated agent skill was created at:
`.agents/skills/caas-product-ux/SKILL.md`

This skill enforces:
- Task-oriented home page patterns.
- Progressive disclosure of advanced technical settings.
- Clear distinction between ephemeral chat context and permanent knowledge.
- WCAG AA accessibility compliance across all future milestones.
