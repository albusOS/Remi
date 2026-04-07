export interface ExpiringLease {
  lease_id: string;
  tenant_name: string;
  property_id: string;
  property_name: string;
  unit_id: string;
  unit_number: string;
  monthly_rent: number;
  market_rent: number;
  end_date: string;
  days_left: number;
  is_month_to_month: boolean;
}

export interface LeaseCalendar {
  days_window: number;
  total_expiring: number;
  month_to_month_count: number;
  leases: ExpiringLease[];
}

export interface LeaseListItem {
  id: string;
  tenant: string;
  unit_id: string;
  property_id: string;
  start: string;
  end: string;
  rent: number;
  status: string;
}

export interface LeaseListResponse {
  count: number;
  leases: LeaseListItem[];
}
