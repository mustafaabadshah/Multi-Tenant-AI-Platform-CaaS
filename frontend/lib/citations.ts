import type { MessageCitationItem } from "@/lib/api";

export function dedupeCitations(
  existing: MessageCitationItem[],
  incoming: MessageCitationItem[]
): MessageCitationItem[] {
  const seen = new Set<string>();
  const merged: MessageCitationItem[] = [];

  for (const citation of [...existing, ...incoming]) {
    const key = citation.chunk_id
      ? `chunk:${citation.chunk_id}`
      : citation.source_url
        ? `url:${citation.source_url}:${citation.citation_num ?? ""}`
        : citation.citation_num != null
          ? `num:${citation.citation_num}:${citation.document_name}`
          : citation.id
            ? `id:${citation.id}`
            : null;

    if (key) {
      if (seen.has(key)) continue;
      seen.add(key);
    }
    merged.push(citation);
  }

  return merged;
}

export interface GroupedCitationSource {
  key: string;
  document_name: string;
  source_type: string;
  source_url?: string | null;
  domain?: string | null;
  citation_nums: number[];
  pages: number[];
  primary_citation: MessageCitationItem;
  chunks: MessageCitationItem[];
}

export function groupCitationsBySource(citations: MessageCitationItem[]): GroupedCitationSource[] {
  const groups: Map<string, GroupedCitationSource> = new Map();

  for (const c of citations) {
    const groupKey = c.source_url
      ? `url:${c.source_url}`
      : `doc:${(c.document_name || "document").toLowerCase().trim()}`;

    if (!groups.has(groupKey)) {
      groups.set(groupKey, {
        key: groupKey,
        document_name: c.document_name || "Document",
        source_type: c.source_type || "document",
        source_url: c.source_url,
        domain: c.domain,
        citation_nums: c.citation_num != null ? [c.citation_num] : [],
        pages: c.page_number != null ? [c.page_number] : [],
        primary_citation: c,
        chunks: [c],
      });
    } else {
      const g = groups.get(groupKey)!;
      g.chunks.push(c);
      if (c.citation_num != null && !g.citation_nums.includes(c.citation_num)) {
        g.citation_nums.push(c.citation_num);
        g.citation_nums.sort((a, b) => a - b);
      }
      if (c.page_number != null && !g.pages.includes(c.page_number)) {
        g.pages.push(c.page_number);
        g.pages.sort((a, b) => a - b);
      }
    }
  }

  return Array.from(groups.values());
}
