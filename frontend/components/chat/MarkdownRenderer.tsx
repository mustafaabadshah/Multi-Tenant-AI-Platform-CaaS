/**
 * MarkdownRenderer — shared Markdown rendering component for all chat surfaces.
 *
 * Design decisions:
 * - Pure JS/TS implementation with no additional heavy npm dependencies.
 * - Never uses dangerouslySetInnerHTML with model-generated content.
 * - Sanitizes link URLs to safe schemes only (https:, http:, mailto:).
 * - Renders citation [N] references as interactive chips when citation data is provided.
 * - Works identically for streaming (partial) and completed messages.
 * - Code blocks are scrollable and inert text only.
 * - Accessible: buttons have aria-labels, citation chips are keyboard-navigable.
 */

"use client";

import React, { useMemo } from "react";
import type { MessageCitationItem } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MarkdownRendererProps {
  /** Raw Markdown text from the LLM. May be partial during streaming. */
  content: string;
  /** Structured citation objects associated with this message. */
  citations?: MessageCitationItem[];
  /** Called when the user clicks a citation chip. */
  onCitationClick?: (citation: MessageCitationItem) => void;
  /** Extra CSS class applied to the root element. */
  className?: string;
}

type BlockType =
  | { kind: "paragraph"; inline: InlineToken[] }
  | { kind: "heading"; level: 1 | 2 | 3 | 4 | 5 | 6; inline: InlineToken[] }
  | { kind: "unordered_list"; items: InlineToken[][] }
  | { kind: "ordered_list"; items: InlineToken[][]; start: number }
  | { kind: "blockquote"; inline: InlineToken[] }
  | { kind: "code_block"; lang: string; code: string }
  | { kind: "hr" }
  | { kind: "table"; header: InlineToken[][]; rows: InlineToken[][][] };

type InlineToken =
  | { t: "text"; v: string }
  | { t: "bold"; v: string }
  | { t: "italic"; v: string }
  | { t: "code"; v: string }
  | { t: "link"; href: string; label: string }
  | { t: "citation"; num: number };

// ---------------------------------------------------------------------------
// URL sanitizer
// ---------------------------------------------------------------------------

function sanitizeUrl(href: string): string | null {
  try {
    const url = new URL(href, "https://SAFE_BASE");
    if (["https:", "http:", "mailto:"].includes(url.protocol)) {
      return href;
    }
    return null;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Inline parser
// ---------------------------------------------------------------------------

function parseInline(text: string): InlineToken[] {
  const tokens: InlineToken[] = [];
  let i = 0;
  const len = text.length;

  while (i < len) {
    // Bold: **text**
    if (text[i] === "*" && text[i + 1] === "*") {
      const end = text.indexOf("**", i + 2);
      if (end !== -1) {
        tokens.push({ t: "bold", v: text.slice(i + 2, end) });
        i = end + 2;
        continue;
      }
    }
    // Italic: *text*  (not **)
    if (text[i] === "*" && text[i + 1] !== "*") {
      const end = text.indexOf("*", i + 1);
      if (end !== -1 && text[end + 1] !== "*") {
        tokens.push({ t: "italic", v: text.slice(i + 1, end) });
        i = end + 1;
        continue;
      }
    }
    // Inline code: `code`
    if (text[i] === "`") {
      const end = text.indexOf("`", i + 1);
      if (end !== -1) {
        tokens.push({ t: "code", v: text.slice(i + 1, end) });
        i = end + 1;
        continue;
      }
    }
    // Link: [label](url)
    if (text[i] === "[") {
      const closeBracket = text.indexOf("]", i + 1);
      if (
        closeBracket !== -1 &&
        text[closeBracket + 1] === "(" &&
        !/^\d+$/.test(text.slice(i + 1, closeBracket))
      ) {
        const closeParen = text.indexOf(")", closeBracket + 2);
        if (closeParen !== -1) {
          const label = text.slice(i + 1, closeBracket);
          const href = text.slice(closeBracket + 2, closeParen);
          const safeHref = sanitizeUrl(href);
          if (safeHref) {
            tokens.push({ t: "link", href: safeHref, label });
          } else {
            tokens.push({ t: "text", v: label });
          }
          i = closeParen + 1;
          continue;
        }
      }
    }
    // Citation: [N] where N is an integer
    if (text[i] === "[") {
      const closeBracket = text.indexOf("]", i + 1);
      if (closeBracket !== -1) {
        const inner = text.slice(i + 1, closeBracket);
        if (/^\d+$/.test(inner)) {
          tokens.push({ t: "citation", num: parseInt(inner, 10) });
          i = closeBracket + 1;
          continue;
        }
      }
    }
    // Accumulate plain text
    const lastToken = tokens[tokens.length - 1];
    if (lastToken && lastToken.t === "text") {
      lastToken.v += text[i];
    } else {
      tokens.push({ t: "text", v: text[i] });
    }
    i++;
  }

  return tokens;
}

// ---------------------------------------------------------------------------
// Block parser
// ---------------------------------------------------------------------------

function parseBlocks(markdown: string): BlockType[] {
  const blocks: BlockType[] = [];

  // Normalize line endings
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code block
    if (line.startsWith("```")) {
      const lang = line.slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      blocks.push({ kind: "code_block", lang, code: codeLines.join("\n") });
      i++; // skip closing ```
      continue;
    }

    // Horizontal rule
    if (/^(\*{3,}|-{3,}|_{3,})\s*$/.test(line)) {
      blocks.push({ kind: "hr" });
      i++;
      continue;
    }

    // ATX Heading
    const headingMatch = line.match(/^(#{1,6})\s+(.*)/);
    if (headingMatch) {
      const level = headingMatch[1].length as 1 | 2 | 3 | 4 | 5 | 6;
      blocks.push({ kind: "heading", level, inline: parseInline(headingMatch[2]) });
      i++;
      continue;
    }

    // Blockquote
    if (line.startsWith("> ")) {
      const quoteLines: string[] = [];
      while (i < lines.length && lines[i].startsWith("> ")) {
        quoteLines.push(lines[i].slice(2));
        i++;
      }
      blocks.push({ kind: "blockquote", inline: parseInline(quoteLines.join(" ")) });
      continue;
    }

    // Unordered list
    if (/^(\s*)[-*+]\s/.test(line)) {
      const items: InlineToken[][] = [];
      while (i < lines.length && /^(\s*)[-*+]\s/.test(lines[i])) {
        items.push(parseInline(lines[i].replace(/^(\s*)[-*+]\s/, "")));
        i++;
      }
      blocks.push({ kind: "unordered_list", items });
      continue;
    }

    // Ordered list
    const orderedMatch = line.match(/^(\s*)(\d+)\.\s/);
    if (orderedMatch) {
      const start = parseInt(orderedMatch[2], 10);
      const items: InlineToken[][] = [];
      while (i < lines.length && /^(\s*)\d+\.\s/.test(lines[i])) {
        items.push(parseInline(lines[i].replace(/^(\s*)\d+\.\s/, "")));
        i++;
      }
      blocks.push({ kind: "ordered_list", items, start });
      continue;
    }

    // Table (GitHub Flavored Markdown)
    if (
      line.includes("|") &&
      i + 1 < lines.length &&
      /^\|?[\s\-|:]+\|?$/.test(lines[i + 1])
    ) {
      const parseCells = (row: string) =>
        row
          .split("|")
          .filter((cell, ci, arr) => !(ci === 0 && arr[0].trim() === "") && !(ci === arr.length - 1 && arr[arr.length - 1].trim() === ""))
          .map((cell) => parseInline(cell.trim()));

      const header = parseCells(line);
      i += 2; // skip separator row
      const rows: InlineToken[][][] = [];
      while (i < lines.length && lines[i].includes("|") && lines[i].trim() !== "") {
        rows.push(parseCells(lines[i]));
        i++;
      }
      blocks.push({ kind: "table", header, rows });
      continue;
    }

    // Blank line — skip
    if (line.trim() === "") {
      i++;
      continue;
    }

    // Paragraph: accumulate consecutive non-blank, non-special lines
    const paraLines: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !lines[i].startsWith("```") &&
      !/^#{1,6}\s/.test(lines[i]) &&
      !lines[i].startsWith("> ") &&
      !/^(\s*)[-*+]\s/.test(lines[i]) &&
      !/^(\s*)\d+\.\s/.test(lines[i]) &&
      !/^(\*{3,}|-{3,}|_{3,})\s*$/.test(lines[i])
    ) {
      paraLines.push(lines[i]);
      i++;
    }
    if (paraLines.length > 0) {
      blocks.push({ kind: "paragraph", inline: parseInline(paraLines.join(" ")) });
    }
  }

  return blocks;
}

// ---------------------------------------------------------------------------
// React renderers
// ---------------------------------------------------------------------------

function InlineView({
  tokens,
  citations,
  onCitationClick,
}: {
  tokens: InlineToken[];
  citations: MessageCitationItem[];
  onCitationClick?: (c: MessageCitationItem) => void;
}) {
  return (
    <>
      {tokens.map((tok, i) => {
        switch (tok.t) {
          case "text":
            return <React.Fragment key={i}>{tok.v}</React.Fragment>;
          case "bold":
            return (
              <strong key={i} className="font-semibold text-gray-900">
                {tok.v}
              </strong>
            );
          case "italic":
            return (
              <em key={i} className="italic">
                {tok.v}
              </em>
            );
          case "code":
            return (
              <code
                key={i}
                className="px-1.5 py-0.5 rounded bg-gray-100 text-blue-700 font-mono text-[0.85em]"
              >
                {tok.v}
              </code>
            );
          case "link":
            return (
              <a
                key={i}
                href={tok.href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 underline hover:text-blue-800 transition-colors"
              >
                {tok.label}
              </a>
            );
          case "citation": {
            const matchingCit = citations.find((c) => c.citation_num === tok.num);
            if (matchingCit && onCitationClick) {
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => onCitationClick(matchingCit)}
                  aria-label={`Citation ${tok.num}: ${matchingCit.document_name}`}
                  className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded text-[11px] font-semibold bg-blue-100 text-blue-700 hover:bg-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-400 transition-colors cursor-pointer align-baseline"
                >
                  [{tok.num}]
                </button>
              );
            }
            // No matching citation data — render as muted plain text
            return <span key={i} className="text-gray-500 text-[11px]">[{tok.num}]</span>;
          }
          default:
            return null;
        }
      })}
    </>
  );
}

function BlockView({
  block,
  citations,
  onCitationClick,
}: {
  block: BlockType;
  citations: MessageCitationItem[];
  onCitationClick?: (c: MessageCitationItem) => void;
}) {
  const inlineProps = { citations, onCitationClick };

  switch (block.kind) {
    case "paragraph":
      return (
        <p className="my-2 leading-relaxed text-gray-900">
          <InlineView tokens={block.inline} {...inlineProps} />
        </p>
      );

    case "heading": {
      const baseClass = "font-semibold text-gray-900 mt-4 mb-1.5 leading-snug";
      const sizeClass = (
        {
          1: "text-lg",
          2: "text-base",
          3: "text-sm font-bold",
          4: "text-sm",
          5: "text-xs font-bold",
          6: "text-xs",
        } as Record<number, string>
      )[block.level];
      if (block.level === 1) return <h1 className={`${baseClass} ${sizeClass}`}><InlineView tokens={block.inline} {...inlineProps} /></h1>;
      if (block.level === 2) return <h2 className={`${baseClass} ${sizeClass}`}><InlineView tokens={block.inline} {...inlineProps} /></h2>;
      if (block.level === 3) return <h3 className={`${baseClass} ${sizeClass}`}><InlineView tokens={block.inline} {...inlineProps} /></h3>;
      if (block.level === 4) return <h4 className={`${baseClass} ${sizeClass}`}><InlineView tokens={block.inline} {...inlineProps} /></h4>;
      if (block.level === 5) return <h5 className={`${baseClass} ${sizeClass}`}><InlineView tokens={block.inline} {...inlineProps} /></h5>;
      return <h6 className={`${baseClass} ${sizeClass}`}><InlineView tokens={block.inline} {...inlineProps} /></h6>;
    }

    case "unordered_list":
      return (
        <ul className="my-2 pl-4 space-y-1 list-disc list-outside text-gray-900">
          {block.items.map((item, idx) => (
            <li key={idx} className="leading-relaxed pl-1">
              <InlineView tokens={item} {...inlineProps} />
            </li>
          ))}
        </ul>
      );

    case "ordered_list":
      return (
        <ol
          className="my-2 pl-4 space-y-1 list-decimal list-outside text-gray-900"
          start={block.start}
        >
          {block.items.map((item, idx) => (
            <li key={idx} className="leading-relaxed pl-1">
              <InlineView tokens={item} {...inlineProps} />
            </li>
          ))}
        </ol>
      );

    case "blockquote":
      return (
        <blockquote className="my-2 pl-3 border-l-4 border-blue-300 text-gray-600 italic">
          <InlineView tokens={block.inline} {...inlineProps} />
        </blockquote>
      );

    case "code_block":
      return (
        <div className="my-3 rounded-lg overflow-hidden border border-gray-200">
          {block.lang && (
            <div className="px-3 py-1.5 bg-gray-800 text-xs text-gray-400 font-mono">
              {block.lang}
            </div>
          )}
          <pre className="p-3 text-xs font-mono overflow-x-auto bg-gray-900 text-gray-100 whitespace-pre">
            {block.code}
          </pre>
        </div>
      );

    case "hr":
      return <hr className="my-3 border-gray-200" />;

    case "table":
      return (
        <div className="my-3 overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full text-sm border-collapse">
            <thead className="bg-gray-50">
              <tr>
                {block.header.map((cell, ci) => (
                  <th
                    key={ci}
                    className="px-3 py-2 text-left text-xs font-semibold text-gray-700 border-b border-gray-200"
                  >
                    <InlineView tokens={cell} {...inlineProps} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, ri) => (
                <tr key={ri} className={ri % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                  {row.map((cell, ci) => (
                    <td
                      key={ci}
                      className="px-3 py-2 text-xs text-gray-800 border-b border-gray-100"
                    >
                      <InlineView tokens={cell} {...inlineProps} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );

    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

export default function MarkdownRenderer({
  content,
  citations = [],
  onCitationClick,
  className = "",
}: MarkdownRendererProps) {
  const blocks = useMemo(() => parseBlocks(content || ""), [content]);

  if (!content || !content.trim()) {
    return <span className="text-gray-400 italic text-sm">…</span>;
  }

  return (
    <div className={`leading-relaxed ${className}`}>
      {blocks.map((block, i) => (
        <BlockView
          key={i}
          block={block}
          citations={citations}
          onCitationClick={onCitationClick}
        />
      ))}
    </div>
  );
}
