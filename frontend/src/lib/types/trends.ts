export interface DelinquencyTrendPeriod {
  period: string;
  total_balance: number;
  tenant_count: number;
  avg_balance: number;
  max_balance: number;
}

export interface DelinquencyTrend {
  manager_id: string | null;
  periods: DelinquencyTrendPeriod[];
  period_count: number;
  direction: "improving" | "worsening" | "stable" | "insufficient_data";
}

export interface OccupancyTrendPeriod {
  period: string;
  total_units: number;
  occupied: number;
  vacant: number;
  occupancy_rate: number;
}

export interface OccupancyTrend {
  manager_id: string | null;
  property_id: string | null;
  periods: OccupancyTrendPeriod[];
  period_count: number;
  direction: "improving" | "worsening" | "stable" | "insufficient_data";
}

export interface RentTrendPeriod {
  period: string;
  avg_rent: number;
  median_rent: number;
  total_rent: number;
  unit_count: number;
}

export interface RentTrend {
  manager_id: string | null;
  property_id: string | null;
  periods: RentTrendPeriod[];
  period_count: number;
  direction: "improving" | "worsening" | "stable" | "insufficient_data";
}

export interface MeetingBriefAction {
  title: string;
  description?: string;
  priority?: "urgent" | "high" | "medium" | "low";
  owner: "manager" | "director" | "both";
  timeframe: string;
}

export interface MeetingAgendaItem {
  topic: string;
  severity: "high" | "medium" | "low";
  talking_points: string[];
  questions: string[];
  suggested_actions: MeetingBriefAction[];
}

export interface MeetingBrief {
  manager_name: string;
  summary: string;
  agenda: MeetingAgendaItem[];
  positives: string[];
  follow_up_date: string;
}

export interface MeetingBriefAnalysis {
  themes: {
    id: string;
    title: string;
    severity: string;
    summary: string;
    details?: string;
    affected_properties: string[];
    monthly_impact: number;
  }[];
  positive_notes: string[];
  data_gaps?: string[];
}

export interface MeetingBriefResponse {
  id: string;
  manager_id: string;
  snapshot_hash: string;
  brief: MeetingBrief;
  analysis: MeetingBriefAnalysis;
  focus: string | null;
  generated_at: string;
  usage: { prompt_tokens: number; completion_tokens: number };
}

export interface MeetingBriefListResponse {
  briefs: MeetingBriefResponse[];
  total: number;
  current_snapshot_hash: string | null;
}
