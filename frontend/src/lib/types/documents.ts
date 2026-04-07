export type DocumentKind = "tabular" | "text" | "image";

export interface TextChunk {
  index: number;
  text: string;
  page: number | null;
}

export interface DocumentMeta {
  id: string;
  filename: string;
  content_type: string;
  kind: DocumentKind;
  row_count: number;
  columns: string[];
  report_type: string;
  chunk_count: number;
  page_count: number;
  tags: string[];
  size_bytes: number;
  uploaded_at: string;
}

export type ReviewKind =
  | "ambiguous_row"
  | "validation_warning"
  | "entity_match"
  | "classification_uncertain"
  | "manager_inferred";

export type ReviewSeverity = "info" | "warning" | "action_needed";

export interface ReviewOption {
  id: string;
  label: string;
}

export interface ReviewItem {
  kind: ReviewKind;
  severity: ReviewSeverity;
  message: string;
  row_index?: number | null;
  entity_type?: string | null;
  entity_id?: string | null;
  field_name?: string | null;
  raw_value?: string | null;
  suggestion?: string | null;
  options?: ReviewOption[];
  row_data?: Record<string, unknown> | null;
}

export interface UploadKnowledge {
  entities_extracted: number;
  relationships_extracted: number;
  ambiguous_rows: number;
  rows_accepted: number;
  rows_rejected: number;
  rows_skipped: number;
  validation_warnings: string[];
  review_items: ReviewItem[];
}

export interface DuplicateInfo {
  existing_id: string;
  existing_filename: string;
  uploaded_at: string;
}

export interface UploadResult {
  id: string;
  filename: string;
  kind: string;
  row_count: number;
  report_type: string;
  columns: string[];
  chunk_count: number;
  page_count: number;
  tags: string[];
  size_bytes: number;
  knowledge: UploadKnowledge;
  duplicate?: DuplicateInfo | null;
}

export interface CorrectRowResponse {
  accepted: boolean;
  entities_created: number;
  relationships_created: number;
  review_items: ReviewItem[];
  validation_warnings: string[];
}
