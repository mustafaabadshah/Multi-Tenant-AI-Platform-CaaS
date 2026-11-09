/**
 * Official TypeScript Client SDK for Multi-Tenant AI Platform (CaaS)
 */

export interface MMAIPClientOptions {
  apiKey: string;
  baseUrl?: string;
  timeoutMs?: number;
}

export interface AssistantInfo {
  id: string;
  name: string;
  description?: string;
  llm_provider: string;
  default_model: string;
  created_at: string;
}

export interface ChatOptions {
  message: string;
  conversationId?: string;
}

export interface StreamEvent {
  event: string;
  data: Record<string, any>;
}

export class MMAIPError extends Error {
  statusCode?: number;
  constructor(message: string, statusCode?: number) {
    super(message);
    this.name = "MMAIPError";
    this.statusCode = statusCode;
  }
}

export class MMAIPClient {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly timeoutMs: number;

  constructor(options: MMAIPClientOptions) {
    if (!options.apiKey) {
      throw new MMAIPError("API key is required to initialize MMAIPClient");
    }
    this.apiKey = options.apiKey.trim();
    this.baseUrl = (options.baseUrl || "http://localhost:8000/api/v1").replace(/\/+$/, "");
    this.timeoutMs = options.timeoutMs || 30000;
  }

  public assistants = {
    list: async (): Promise<AssistantInfo[]> => {
      const res = await this.request("/developer/assistants", { method: "GET" });
      return res as AssistantInfo[];
    },

    streamChat: async function* (
      assistantId: string,
      options: ChatOptions
    ): AsyncGenerator<StreamEvent, void, unknown> {
      const url = `${this.baseUrl}/developer/assistants/${assistantId}/chat`;
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.apiKey}`,
        },
        body: JSON.stringify({
          message: options.message,
          conversation_id: options.conversationId,
        }),
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new MMAIPError(`Chat request failed (${response.status}): ${errText}`, response.status);
      }

      if (!response.body) {
        throw new MMAIPError("No response body received from streaming endpoint");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const block of lines) {
          if (!block.trim()) continue;
          let eventType = "message";
          let dataStr = "";

          for (const line of block.split("\n")) {
            if (line.startsWith("event:")) {
              eventType = line.replace("event:", "").trim();
            } else if (line.startsWith("data:")) {
              dataStr += line.replace("data:", "").trim();
            }
          }

          if (dataStr) {
            try {
              const parsed = JSON.parse(dataStr);
              yield { event: eventType, data: parsed };
            } catch {
              yield { event: eventType, data: { raw: dataStr } };
            }
          }
        }
      }
    }.bind(this),
  };

  private async request(endpoint: string, options: RequestInit): Promise<any> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${this.apiKey}`,
      ...(options.headers || {}),
    };

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      });

      if (!response.ok) {
        const text = await response.text();
        throw new MMAIPError(`Request failed with status ${response.status}: ${text}`, response.status);
      }

      return await response.json();
    } finally {
      clearTimeout(timeout);
    }
  }
}
