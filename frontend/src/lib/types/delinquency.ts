export interface DelinquentTenant {
  tenant_id: string;
  tenant_name: string;
  status: string;
  property_id: string | null;
  property_name: string;
  unit_id: string | null;
  unit_number: string;
  balance_owed: number;
  balance_0_30: number;
  balance_30_plus: number;
  last_payment_date: string | null;
  delinquency_notes: string | null;
}

export interface DelinquencyBoard {
  total_delinquent: number;
  total_balance: number;
  tenants: DelinquentTenant[];
}
