export interface VacantUnit {
  unit_id: string;
  unit_number: string;
  property_id: string;
  property_name: string;
  occupancy_status: string | null;
  days_vacant: number | null;
  market_rent: number;
}

export interface VacancyTracker {
  total_vacant: number;
  total_notice: number;
  total_market_rent_at_risk: number;
  avg_days_vacant: number | null;
  units: VacantUnit[];
}
