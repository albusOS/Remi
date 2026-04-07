export interface PropertyDetail {
  id: string;
  name: string;
  address: Record<string, string>;
  property_type: string;
  year_built: number;
  manager_id: string | null;
  manager_name: string | null;
  owner_id: string | null;
  owner_name: string | null;
  total_units: number;
  units: Unit[];
  occupancy_rate: number;
  monthly_revenue: number;
  active_leases: number;
}

export interface Unit {
  id: string;
  property_id: string;
  unit_number: string;
  bedrooms: number;
  bathrooms: number;
  sqft: number;
  market_rent: number;
  current_rent: number;
  status: "vacant" | "occupied" | "maintenance" | "offline";
  floor: number;
}

export interface RentRollLease {
  id: string;
  status: "active" | "expired" | "terminated" | "pending";
  start_date: string;
  end_date: string;
  monthly_rent: number;
  deposit: number;
  days_to_expiry: number | null;
}

export interface RentRollTenant {
  id: string;
  name: string;
  email: string;
  phone: string | null;
}

export interface RentRollMaintenance {
  id: string;
  title: string;
  category: string;
  priority: "low" | "medium" | "high" | "emergency";
  status: "open" | "in_progress";
  cost: number | null;
}

export type UnitIssue =
  | "vacant"
  | "down_for_maintenance"
  | "below_market"
  | "expired_lease"
  | "expiring_soon"
  | "open_maintenance";

export interface RentRollRow {
  unit_id: string;
  unit_number: string;
  floor: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  sqft: number | null;
  status: "vacant" | "occupied" | "maintenance" | "offline";
  market_rent: number;
  current_rent: number;
  rent_gap: number;
  pct_below_market: number;
  lease: RentRollLease | null;
  tenant: RentRollTenant | null;
  open_maintenance: number;
  maintenance_items: RentRollMaintenance[];
  issues: UnitIssue[];
}

export interface RentRollResponse {
  property_id: string;
  property_name: string;
  total_units: number;
  occupied: number;
  vacant: number;
  total_market_rent: number;
  total_actual_rent: number;
  total_loss_to_lease: number;
  total_vacancy_loss: number;
  rows: RentRollRow[];
}
