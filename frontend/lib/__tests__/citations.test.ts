/**
 * M28.10 Citation Integrity and Grouping Tests
 */

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { dedupeCitations, groupCitationsBySource } from "../citations.ts";
import type { MessageCitationItem } from "../api.ts";

describe("M28.10 Citation Grouping & Deduplication", () => {
  it("should group multiple chunks from the same PDF document into a single source card", () => {
    const rawCitations: MessageCitationItem[] = [
      {
        id: "cit-1",
        citation_num: 1,
        chunk_id: "chk-aaa",
        document_name: "Solar_irradiance__TechScience.pdf",
        citation_text: "Snippet from section 1...",
        source_type: "document",
        page_number: 2,
      },
      {
        id: "cit-2",
        citation_num: 2,
        chunk_id: "chk-bbb",
        document_name: "Solar_irradiance__TechScience.pdf",
        citation_text: "Snippet from section 3...",
        source_type: "document",
        page_number: 5,
      },
      {
        id: "cit-3",
        citation_num: 3,
        chunk_id: "chk-ccc",
        document_name: "Solar_irradiance__TechScience.pdf",
        citation_text: "Snippet from section 4...",
        source_type: "document",
        page_number: 5, // Same page as cit-2
      },
      {
        id: "cit-4",
        citation_num: 4,
        chunk_id: "chk-ddd",
        document_name: "C++ For Loop - W3Schools",
        citation_text: "C++ loops...",
        source_type: "web",
        source_url: "https://www.w3schools.com/cpp/cpp_for_loop.asp",
        domain: "www.w3schools.com",
        page_number: null,
      },
    ];

    const grouped = groupCitationsBySource(rawCitations);

    // Should produce exactly 2 grouped sources, not 4 indistinguishable badges!
    assert.equal(grouped.length, 2);

    const solarGroup = grouped.find((g) => g.document_name === "Solar_irradiance__TechScience.pdf");
    assert.ok(solarGroup, "Solar document group must exist");
    assert.deepEqual(solarGroup.citation_nums, [1, 2, 3]);
    assert.deepEqual(solarGroup.pages, [2, 5]); // Pages 2 and 5 aggregated without duplicates
    assert.equal(solarGroup.chunks.length, 3);

    const cppGroup = grouped.find((g) => g.source_type === "web");
    assert.ok(cppGroup, "Web source group must exist");
    assert.equal(cppGroup.domain, "www.w3schools.com");
    assert.deepEqual(cppGroup.citation_nums, [4]);
    assert.deepEqual(cppGroup.pages, []);
  });

  it("should deduplicate citations by chunk_id and identity", () => {
    const existing: MessageCitationItem[] = [
      {
        id: "cit-1",
        citation_num: 1,
        chunk_id: "chk-111",
        document_name: "Doc A",
        citation_text: "Text A",
        source_type: "document",
      },
    ];
    const incoming: MessageCitationItem[] = [
      {
        id: "cit-1-duplicate",
        citation_num: 1,
        chunk_id: "chk-111", // Same chunk_id
        document_name: "Doc A",
        citation_text: "Text A",
        source_type: "document",
      },
      {
        id: "cit-2",
        citation_num: 2,
        chunk_id: "chk-222",
        document_name: "Doc B",
        citation_text: "Text B",
        source_type: "document",
      },
    ];

    const deduped = dedupeCitations(existing, incoming);
    assert.equal(deduped.length, 2);
    assert.equal(deduped[0].chunk_id, "chk-111");
    assert.equal(deduped[1].chunk_id, "chk-222");
  });

  it("should separate two distinct web sources even if titles are similar", () => {
    const webCitations: MessageCitationItem[] = [
      {
        id: "cit-w1",
        citation_num: 1,
        chunk_id: null,
        document_name: "Recent Advances in RAG",
        citation_text: "arXiv paper on modular RAG...",
        source_type: "web",
        source_url: "https://arxiv.org/abs/2312.10997",
        domain: "arxiv.org",
      },
      {
        id: "cit-w2",
        citation_num: 2,
        chunk_id: null,
        document_name: "Recent Advances in RAG - Blog",
        citation_text: "Blog post summarizing RAG...",
        source_type: "web",
        source_url: "https://example.com/blog/recent-advances-in-rag",
        domain: "example.com",
      },
    ];

    const grouped = groupCitationsBySource(webCitations);
    assert.equal(grouped.length, 2);
    assert.equal(grouped[0].domain, "arxiv.org");
    assert.equal(grouped[1].domain, "example.com");
  });
});
