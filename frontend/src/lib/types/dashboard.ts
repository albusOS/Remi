import type { ManagerOverview } from "./managers";

export interface PropertyOverview {
  property_id: string;
  property_name: string;
  address: string;
  manager_id: string | null;
  manager_name: string | null;
  total_units: number;
  occupied: number;
  vacant: number;
  occupancy_rate: number;
  monthly_rent: number;
  market_rent: number;
  loss_to_lease: number;
  open_maintenance: number;
}

export interface DashboardOverview {
  total_properties: number;
  total_units: number;
  occupied: number;
  vacant: number;
  occupancy_rate: number;
  total_monthly_rent: number;
  total_market_rent: number;
  total_loss_to_lease: number;
  properties: PropertyOverview[];
  total_managers: number;
  managers: ManagerOverview[];
}

export interface NeedsManagerProperty {
  id: string;
  name: string;
  address: string;
}

export interface NeedsManagerResponse {
  total: number;
  properties: NeedsManagerProperty[];
}
