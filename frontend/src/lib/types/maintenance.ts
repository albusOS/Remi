export interface MaintenanceRequest {
  id: string;
  property_id: string;
  unit_id: string;
  title: string;
  category: string;
  priority: "low" | "medium" | "high" | "emergency";
  status: "open" | "in_progress" | "completed" | "cancelled";
  cost: number | null;
  created: string;
  resolved: string | null;
}

export interface MaintenanceListResponse {
  count: number;
  requests: MaintenanceRequest[];
}

export interface MaintenanceSummary {
  total: number;
  by_status: Record<string, number>;
  by_category: Record<string, number>;
  total_cost: number;
}

export interface MaintenanceTrendPeriod {
  period: string;
  opened: number;
  completed: number;
  net_open: number;
  total_cost: number;
  avg_resolution_days: number | null;
  by_category: Record<string, number>;
}

export interface MaintenanceTrend {
  manager_id: string | null;
  property_id: string | null;
  unit_id: string | null;
  periods: MaintenanceTrendPeriod[];
  period_count: number;
  direction: "improving" | "worsening" | "stable" | "insufficient_data";
}
