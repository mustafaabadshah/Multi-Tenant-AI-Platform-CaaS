# M28.4 UX Aesthetics & Accessibility Audit

## 1. Design Direction: Linear × Apple Notes Light

The M28.4 user experience strictly implements the platform's restrained, purposeful design language:
- **Color Palette:** Warm off-whites (`#FBFBFA`, `#F7F7F5`), neutral zinc/slate borders (`#E5E5E3`, `#D4D4D0`), deep neutral typography (`#191919`, `#37352F`), and muted subtle accents (`#0066CC` or deep slate).
- **Typography:** Modern variable sans-serif hierarchy (Inter/system-ui), crisp line heights (1.5–1.6), and clear semantic weight distribution.
- **Micro-Interactions:** Subtle border transitions (150ms ease), gentle focus outlines, and zero garish glowing animations.
- **Modals & Overlays:** Minimalist backdrop blur (`backdrop-blur-sm`), clear keyboard dismissal (`Escape`), and prominent cancel/confirm actions.

## 2. Ingestion & Save UX

### 2.1 Web Source "Save to Knowledge Base" Modal
- Distinct 3-way radio selection cards:
  1. **Reference Only:** Bookmark metadata only (0 chunks).
  2. **My Notes:** Save user synthesis / comments as chunks.
  3. **Searchable Content:** Chunk and index full extracted body text.
- Clear character count and target Knowledge Base selector.
- Immediate inline confirmation toast upon successful save.

### 2.2 Citations & Provenance Display
- Citations appear in a dedicated drawer and collapsible badges.
- Badges indicate format provenance: `[Web]`, `[PDF]`, `[Image]`, and `[OCR Derived]`.
- No spurious `(p. 1)` for web or single-image sources.

## 3. Accessibility & Keyboard Navigation (WCAG 2.1 AA)

- **Keyboard Focus Management:** All interactive elements (`<button>`, `<select>`, `<textarea>`, modal dialogs) provide high-contrast visible focus rings (`focus-visible:ring-2`).
- **Screen Reader Support:** Semantic HTML tags, `aria-label` attributes on icon-only buttons (Microphone, Audio, Close, Send).
- **Color Contrast:** Text contrast ratios exceed 4.5:1 against container backgrounds.
- **Escape Key Interception:** Modal dialogs and drawers dismiss cleanly on `Escape` keypress.
