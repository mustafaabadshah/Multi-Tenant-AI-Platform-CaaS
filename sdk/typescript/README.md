# @mmaip/client — TypeScript SDK for Multi-Tenant AI Platform

Lightweight, zero-dependency TypeScript & JavaScript client SDK for programmatic assistant chat and retrieval integration.

## Installation

```bash
npm install @mmaip/client
```

## Quick Start

```typescript
import { MMAIPClient } from "@mmaip/client";

const client = new MMAIPClient({
  apiKey: process.env.MMAIP_API_KEY!,
  baseUrl: "http://localhost:8000/api/v1",
});

// 1. List available assistants
const assistants = await client.assistants.list();
console.log("Assistants:", assistants);

// 2. Stream a chat message
const stream = client.assistants.streamChat(assistants[0].id, {
  message: "Explain the key concepts in Chapter 4",
});

for await (const event of stream) {
  if (event.event === "token") {
    process.stdout.write(event.data.delta);
  } else if (event.event === "citation") {
    console.log(`\n[Citation ${event.data.citation_num}]: ${event.data.document_name}`);
  }
}
```
