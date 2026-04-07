export interface SignalSummary {
  signal_id: string;
  signal_type: string;
  severity: "critical" | "high" | "medium" | "low";
  entity_type: string;
  entity_id: string;
  entity_name: string;
  description: string;
  detected_at: string;
}

export interface SignalDigestEntity {
  entity_id: string;
  entity_type: string;
  entity_name: string;
  worst_severity: "critical" | "high" | "medium" | "low";
  signal_count: number;
  severity_counts: Record<string, number>;
  signals: SignalSummary[];
}

export interface SignalDigest {
  total_signals: number;
  total_entities: number;
  severity_counts: Record<string, number>;
  entities: SignalDigestEntity[];
}
