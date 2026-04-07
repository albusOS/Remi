export interface UsageInfo {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  model?: string;
  provider?: string;
  cost?: number;
  latency_ms?: number;
  trace_id?: string;
  intent?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  tools?: ToolCall[];
  usage?: UsageInfo;
  error?: string;
}

export interface SessionSummary {
  id: string;
  agent: string;
  messageCount: number;
  preview: string;
  createdAt: string;
  updatedAt: string;
  streaming: boolean;
}

export interface ToolCall {
  id: string;
  tool: string;
  arguments: Record<string, unknown>;
  result?: unknown;
  status: "calling" | "done" | "error";
  duration?: number;
}

export interface AgentMeta {
  name: string;
  description: string;
  version: string;
  primary: boolean;
  tags: string[];
}
