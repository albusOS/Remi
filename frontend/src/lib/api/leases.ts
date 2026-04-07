import { get, post, patch, del, qs } from "./client";
import type { LeaseListResponse } from "@/lib/types";

export const leasesApi = {
  list: (params?: { property_id?: string; status?: string }) =>
    get<LeaseListResponse>(`/api/v1/leases${qs(params || {})}`),

  create: (data: { unit_id: string; tenant_id: string; property_id: string; start_date: string; end_date: string; monthly_rent: number; deposit?: number; status?: string }) =>
    post<{ lease_id: string; unit_id: string; tenant_id: string; property_id: string }>("/api/v1/leases", data),

  update: (id: string, updates: { monthly_rent?: number; status?: string; end_date?: string; renewal_status?: string; is_month_to_month?: boolean }) =>
    patch<{ id: string; name: string }>(`/api/v1/leases/${id}`, updates),

  delete: (id: string) =>
    del<{ deleted: boolean }>(`/api/v1/leases/${id}`),
};
