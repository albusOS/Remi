export interface FieldChange {
  field: string;
  old_value: unknown;
  new_value: unknown;
}

export interface ChangeEvent {
  entity_type: string;
  entity_id: string;
  change_type: "created" | "updated" | "removed";
  source: string;
  timestamp: string;
  fields: FieldChange[];
}

export interface ChangeSetSummary {
  id: string;
  source: string;
  source_detail: string;
  adapter_name: string;
  report_type: string | null;
  document_id: string;
  timestamp: string;
  summary: { created: number; updated: number; unchanged: number; removed: number };
  total_changes: number;
  is_empty: boolean;
  events: ChangeEvent[];
  unchanged_ids: string[];
}

export interface ActionItemResponse {
  id: string;
  title: string;
  description: string;
  status: "open" | "in_progress" | "done" | "cancelled";
  priority: "low" | "medium" | "high" | "urgent";
  manager_id: string | null;
  property_id: string | null;
  tenant_id: string | null;
  due_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface EntityNoteResponse {
  id: string;
  content: string;
  entity_type: string;
  entity_id: string;
  provenance: "user_stated" | "data_derived" | "inferred";
  source_doc?: string | null;
  created_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SearchHit {
  entity_id: string;
  entity_type: string;
  label: string;
  title: string;
  subtitle: string;
  score: number;
  metadata: Record<string, unknown>;
}

export interface SearchResponse {
  query: string;
  results: SearchHit[];
  total: number;
}

export interface FeedEvent {
  seq: number;
  topic: string;
  payload: Record<string, unknown>;
  event_id: string;
  timestamp: string;
  source: string;
}

export interface FeedResponse {
  events: FeedEvent[];
  cursor: number;
  has_more: boolean;
}
