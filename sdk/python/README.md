# mmaip — Python SDK for Multi-Tenant AI Platform

Official lightweight Python client for the Multi-Tenant AI Platform (CaaS) Developer API.

## Installation

```bash
pip install mmaip
```

## Quick Start

```python
import os
from mmaip import MMAIPClient

client = MMAIPClient(
    api_key=os.environ["MMAIP_API_KEY"],
    base_url="http://localhost:8000/api/v1",
)

# 1. List assistants
assistants = client.list_assistants()
print("Available Assistants:", [a["name"] for a in assistants])

# 2. Stream a response
for event in client.stream_chat(assistants[0]["id"], message="Summarize the company vacation policy"):
    if event["event"] == "token":
        print(event["data"]["delta"], end="", flush=True)
    elif event["event"] == "citation":
        print(f"\n[Source]: {event['data']['document_name']} (Page {event['data'].get('page_number')})")
```
