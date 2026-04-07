import { get, post, patch, del } from "./client";
import type {
  ManagerListItem,
  ManagerReview,
  MeetingBriefResponse,
  MeetingBriefListResponse,
} from "@/lib/types";

export const managersApi = {
  list: () =>
    get<{ managers: (Omit<ManagerListItem, "id"> & { manager_id: string })[] }>("/api/v1/managers")
      .then((r) => r.managers.map(({ manager_id, ...rest }) => ({ id: manager_id, ...rest }))),

  getReview: (id: string) =>
    get<ManagerReview>(`/api/v1/managers/${id}/review`),

  create: (data: { name: string; email?: string; company?: string; phone?: string }) =>
    post<{ manager_id: string; name: string }>("/api/v1/managers", data),

  update: (id: string, updates: { name?: string; email?: string; company?: string; phone?: string }) =>
    patch<{ manager_id: string; name: string }>(`/api/v1/managers/${id}`, updates),

  delete: (id: string) =>
    del<{ deleted: boolean }>(`/api/v1/managers/${id}`),

  merge: (sourceId: string, targetId: string) =>
    post<{ target_manager_id: string; properties_moved: number; source_deleted: boolean }>(
      "/api/v1/managers/merge",
      { source_manager_id: sourceId, target_manager_id: targetId },
    ),

  assignProperties: (managerId: string, propertyIds: string[]) =>
    post<{ manager_id: string; assigned: number; already_assigned: number; not_found: string[] }>(
      `/api/v1/managers/${managerId}/assign`,
      { property_ids: propertyIds },
    ),

  generateMeetingBrief: (managerId: string, focus?: string) =>
    post<MeetingBriefResponse>(
      `/api/v1/managers/${managerId}/meeting-brief`,
      { focus: focus || null },
    ),

  listMeetingBriefs: (managerId: string, limit = 10) =>
    get<MeetingBriefListResponse>(`/api/v1/managers/${managerId}/meeting-briefs?limit=${limit}`),
};
