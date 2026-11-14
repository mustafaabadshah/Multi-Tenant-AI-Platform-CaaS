import type { MessageCitationItem } from "@/lib/api";

export function dedupeCitations(
  existing: MessageCitationItem[],
  incoming: MessageCitationItem[]
): MessageCitationItem[] {
  const seen = new Set<string>();
  const merged: MessageCitationItem[] = [];

  for (const citation of [...existing, ...incoming]) {
    const key =
      citation.citation_num != null
        ? `num:${citation.citation_num}`
        : citation.chunk_id
          ? `chunk:${citation.chunk_id}`
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
