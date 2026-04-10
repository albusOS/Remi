import { get, post, patch, del, upload as uploadForm, qs } from "./client";
import type { DocumentMeta, UploadResult, CorrectRowResponse, WaitingTask } from "@/lib/types";

export const documentsApi = {
  list: (params?: { q?: string; kind?: string; tags?: string; sort?: string; limit?: number }) =>
    get<{ documents: DocumentMeta[] }>(`/api/v1/documents${qs(params || {})}`).then((r) => r.documents),

  get: (id: string) =>
    get<DocumentMeta & { preview: Record<string, unknown>[] }>(`/api/v1/documents/${id}`),

  queryRows: (id: string, limit = 100) =>
    get<{ rows: Record<string, unknown>[]; count: number }>(`/api/v1/documents/${id}/rows?limit=${limit}`),

  queryChunks: (id: string, limit = 100) =>
    get<{ document_id: string; chunks: { index: number; text: string; page: number | null }[]; count: number }>(
      `/api/v1/documents/${id}/chunks?limit=${limit}`,
    ),

  listTags: () =>
    get<{ tags: string[] }>("/api/v1/documents/tags").then((r) => r.tags),

  updateTags: (id: string, tags: string[]) =>
    patch<{ tags: string[] }>(`/api/v1/documents/${id}/tags`, { tags }),

  upload: async (file: File, manager?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (manager) form.append("manager", manager);
    return uploadForm<UploadResult>("/api/v1/documents/upload", form);
  },

  delete: (id: string) =>
    del<Record<string, unknown>>(`/api/v1/documents/${id}`),

  correctRow: (documentId: string, rowData: Record<string, unknown>, reportType?: string) =>
    post<CorrectRowResponse>(`/api/v1/documents/${documentId}/correct-row`, { row_data: rowData, report_type: reportType }),

  correctEntity: (entityType: string, entityId: string, corrections: Record<string, unknown>) =>
    post<Record<string, unknown>>("/api/v1/knowledge/correct", { entity_type: entityType, entity_id: entityId, corrections }),

  getWaitingTask: (documentId: string) =>
    get<WaitingTask>(`/api/v1/documents/tasks/waiting?document_id=${encodeURIComponent(documentId)}`),

  supplyHumanAnswers: (taskId: string, answers: Record<string, string>) =>
    post<{ task_id: string; resumed: boolean }>("/api/v1/documents/tasks/answer", {
      task_id: taskId,
      answers,
    }),
};
