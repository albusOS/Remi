import { get, post, patch, del, qs } from "./client";
import type { PropertyDetail, RentRollResponse } from "@/lib/types";

export const propertiesApi = {
  list: (params?: { manager_id?: string; owner_id?: string }) =>
    get<{ properties: PropertyDetail[] }>(`/api/v1/properties${qs(params || {})}`).then((r) => r.properties),

  get: (id: string) =>
    get<PropertyDetail>(`/api/v1/properties/${id}`),

  getRentRoll: (propertyId: string) =>
    get<RentRollResponse>(`/api/v1/properties/${propertyId}/rent-roll`),

  create: (data: { name: string; manager_id?: string; owner_id?: string; street: string; city: string; state: string; zip_code: string; property_type?: string; year_built?: number }) =>
    post<{ property_id: string; name: string }>("/api/v1/properties", data),

  update: (id: string, updates: { name?: string; street?: string; city?: string; state?: string; zip_code?: string; manager_id?: string; owner_id?: string }) =>
    patch<{ id: string; name: string }>(`/api/v1/properties/${id}`, updates),

  delete: (id: string) =>
    del<{ deleted: boolean }>(`/api/v1/properties/${id}`),
};
