import { get, post, patch, del, qs } from "./client";
import type { MaintenanceListResponse, MaintenanceSummary } from "@/lib/types";

export const maintenanceApi = {
  list: (params?: { property_id?: string; unit_id?: string; status?: string }) =>
    get<MaintenanceListResponse>(`/api/v1/maintenance${qs(params || {})}`),

  summary: (params?: { property_id?: string; unit_id?: string }) =>
    get<MaintenanceSummary>(`/api/v1/maintenance/summary${qs(params || {})}`),

  create: (data: { unit_id: string; property_id: string; title: string; description?: string; category?: string; priority?: string }) =>
    post<{ request_id: string; title: string; property_id: string; unit_id: string }>("/api/v1/maintenance", data),

  update: (id: string, updates: { title?: string; description?: string; status?: string; priority?: string; category?: string; vendor?: string; cost?: number }) =>
    patch<{ id: string; name: string }>(`/api/v1/maintenance/${id}`, updates),

  delete: (id: string) =>
    del<{ deleted: boolean }>(`/api/v1/maintenance/${id}`),
};
