export interface ManagerMetrics {
  total_units: number;
  occupied: number;
  vacant: number;
  occupancy_rate: number;
  total_actual_rent: number;
  total_market_rent: number;
  loss_to_lease: number;
  vacancy_loss: number;
  open_maintenance: number;
  expiring_leases_90d: number;
}

export interface ManagerListItem {
  id: string;
  name: string;
  email: string;
  company: string | null;
  property_count: number;
  metrics: ManagerMetrics;
  delinquent_count: number;
  total_delinquent_balance: number;
  expired_leases: number;
  below_market_units: number;
  emergency_maintenance: number;
}

export interface ManagerPropertySummary {
  property_id: string;
  property_name: string;
  total_units: number;
  occupied: number;
  vacant: number;
  occupancy_rate: number;
  monthly_actual: number;
  monthly_market: number;
  loss_to_lease: number;
  vacancy_loss: number;
  open_maintenance: number;
  emergency_maintenance: number;
  expiring_leases: number;
  expired_leases: number;
  below_market_units: number;
  issue_count: number;
}

export interface ManagerUnitIssue {
  property_id: string;
  property_name: string;
  unit_id: string;
  unit_number: string;
  issues: string[];
  monthly_impact: number;
}

export interface ManagerReview {
  manager_id: string;
  name: string;
  email: string;
  company: string | null;
  property_count: number;
  metrics: ManagerMetrics;
  delinquent_count: number;
  total_delinquent_balance: number;
  expired_leases: number;
  below_market_units: number;
  emergency_maintenance: number;
  properties: ManagerPropertySummary[];
  top_issues: ManagerUnitIssue[];
}

export interface ManagerOverview {
  manager_id: string;
  manager_name: string;
  property_count: number;
  metrics: ManagerMetrics;
}

export interface ManagerNoteResponse {
  id: string;
  manager_id: string;
  content: string;
  created_at: string;
  updated_at: string;
}
