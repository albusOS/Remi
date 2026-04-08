import { get, post, patch, del, qs } from "./client";
import type {
  ActionItemResponse,
  EntityNoteResponse,
  SearchResponse,
  SignalSummary,
  ChangeSetSummary,
  GraphSnapshot,
  GraphSubgraph,
  OperationalGraph,
} from "@/lib/types";

export const searchApi = {
  search: (q: string, limit = 10) =>
    get<SearchResponse>(`/api/v1/search${qs({ q, limit })}`),
};

export const ownersApi = {
  list: () =>
    get<{ id: string; name: string; owner_type: string; company: string | null; email: string; phone: string | null; property_count: number }[]>("/api/v1/owners"),
};

export const tenantsApi = {
  create: (data: { name: string; email?: string; phone?: string }) =>
    post<{ tenant_id: string; name: string }>("/api/v1/tenants", data),

  update: (id: string, updates: { name?: string; email?: string; phone?: string; status?: string }) =>
    patch<{ id: string; name: string }>(`/api/v1/tenants/${id}`, updates),

  delete: (id: string) =>
    del<{ deleted: boolean }>(`/api/v1/tenants/${id}`),
};

export const actionsApi = {
  list: (params?: { manager_id?: string; property_id?: string; status?: string }) =>
    get<{ items: ActionItemResponse[]; total: number }>(`/api/v1/actions/items${qs(params || {})}`),

  create: (data: { title: string; description?: string; priority?: string; manager_id?: string; property_id?: string; tenant_id?: string; due_date?: string }) =>
    post<ActionItemResponse>("/api/v1/actions/items", data),

  update: (id: string, updates: { title?: string; description?: string; status?: string; priority?: string; due_date?: string }) =>
    patch<ActionItemResponse>(`/api/v1/actions/items/${id}`, updates),

  delete: (id: string) =>
    del<{ deleted: boolean }>(`/api/v1/actions/items/${id}`),
};

export const notesApi = {
  list: (entityType: string, entityId: string) =>
    get<{ notes: EntityNoteResponse[]; total: number }>(
      `/api/v1/notes?entity_type=${encodeURIComponent(entityType)}&entity_id=${encodeURIComponent(entityId)}`,
    ),

  batch: (entityType: string, entityIds: string[]) =>
    post<{ notes_by_entity: Record<string, EntityNoteResponse[]> }>(
      "/api/v1/notes/batch",
      { entity_type: entityType, entity_ids: entityIds },
    ),

  create: (entityType: string, entityId: string, content: string) =>
    post<EntityNoteResponse>("/api/v1/notes", { content, entity_type: entityType, entity_id: entityId }),

  update: (noteId: string, content: string) =>
    patch<EntityNoteResponse>(`/api/v1/notes/${noteId}`, { content }),

  delete: (noteId: string) =>
    del<{ deleted: boolean }>(`/api/v1/notes/${noteId}`),
};

export interface DomainSchemaResponse {
  entity_types: Array<{ name: string; description: string; key_fields: string[] }>;
  relationships: Array<{ name: string; source: string; target: string; description: string }>;
  processes: Array<{ name: string; description: string; involves: string[] }>;
}

export const ontologyApi = {
  graphSnapshot: (scope?: { manager_id?: string; owner_id?: string }) =>
    get<GraphSnapshot>(`/api/v1/ontology/snapshot${qs(scope || {})}`),

  graphSubgraph: (entityId: string, depth = 2) =>
    get<GraphSubgraph>(`/api/v1/ontology/subgraph/${entityId}${qs({ depth })}`),

  operationalGraph: () =>
    get<OperationalGraph>("/api/v1/ontology/graph/operational"),

  domainSchema: () =>
    get<DomainSchemaResponse>("/api/v1/ontology/domain-schema"),
};

export const signalsApi = {
  list: (params?: { manager_id?: string; property_id?: string; severity?: string; signal_type?: string }) =>
    get<{ count: number; signals: SignalSummary[] }>(`/api/v1/signals${qs(params || {})}`),
};

export const eventsApi = {
  list: (limit = 20) =>
    get<{ count: number; changesets: ChangeSetSummary[] }>(`/api/v1/events${qs({ limit })}`),

  forEntity: (entityId: string, limit = 50) =>
    get<{ entity_id: string; count: number; changesets: ChangeSetSummary[] }>(
      `/api/v1/events/entity/${entityId}${qs({ limit })}`,
    ),
};
