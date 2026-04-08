import { dashboardApi } from "./dashboard";
import { managersApi } from "./managers";
import { propertiesApi } from "./properties";
import { leasesApi } from "./leases";
import { maintenanceApi } from "./maintenance";
import { documentsApi } from "./documents";
import { searchApi, ownersApi, tenantsApi, actionsApi, notesApi, ontologyApi, signalsApi, eventsApi } from "./misc";

/**
 * Unified API facade — preserves the `api.xxx()` call shape that every
 * component already uses, while the implementation is now split into
 * domain-scoped modules.
 */
export const api = {
  dashboardOverview: dashboardApi.overview,
  delinquencyBoard: dashboardApi.delinquencyBoard,
  leasesExpiring: dashboardApi.leasesExpiring,
  vacancyTracker: dashboardApi.vacancyTracker,
  needsManager: dashboardApi.needsManager,
  delinquencyTrend: dashboardApi.delinquencyTrend,
  occupancyTrend: dashboardApi.occupancyTrend,
  rentTrend: dashboardApi.rentTrend,
  maintenanceTrend: dashboardApi.maintenanceTrend,

  listManagers: managersApi.list,
  getManagerReview: managersApi.getReview,
  createManager: managersApi.create,
  updateManager: managersApi.update,
  deleteManager: managersApi.delete,
  mergeManagers: managersApi.merge,
  assignProperties: managersApi.assignProperties,
  generateMeetingBrief: managersApi.generateMeetingBrief,
  listMeetingBriefs: managersApi.listMeetingBriefs,

  listProperties: propertiesApi.list,
  getProperty: propertiesApi.get,
  getRentRoll: propertiesApi.getRentRoll,
  createProperty: propertiesApi.create,
  updateProperty: propertiesApi.update,
  deleteProperty: propertiesApi.delete,

  listLeases: leasesApi.list,
  createLease: leasesApi.create,
  updateLease: leasesApi.update,
  deleteLease: leasesApi.delete,

  listMaintenance: maintenanceApi.list,
  maintenanceSummary: maintenanceApi.summary,
  createMaintenance: maintenanceApi.create,
  updateMaintenance: maintenanceApi.update,
  deleteMaintenance: maintenanceApi.delete,

  listDocuments: documentsApi.list,
  getDocument: documentsApi.get,
  queryRows: documentsApi.queryRows,
  queryChunks: documentsApi.queryChunks,
  listDocumentTags: documentsApi.listTags,
  updateDocumentTags: documentsApi.updateTags,
  uploadDocument: documentsApi.upload,
  deleteDocument: documentsApi.delete,
  correctRow: documentsApi.correctRow,
  correctEntity: documentsApi.correctEntity,

  search: searchApi.search,
  listOwners: ownersApi.list,

  createTenant: tenantsApi.create,
  updateTenant: tenantsApi.update,
  deleteTenant: tenantsApi.delete,

  listActionItems: actionsApi.list,
  createActionItem: actionsApi.create,
  updateActionItem: actionsApi.update,
  deleteActionItem: actionsApi.delete,

  listEntityNotes: notesApi.list,
  batchEntityNotes: notesApi.batch,
  createEntityNote: notesApi.create,
  updateEntityNote: notesApi.update,
  deleteEntityNote: notesApi.delete,

  graphSnapshot: ontologyApi.graphSnapshot,
  graphSubgraph: ontologyApi.graphSubgraph,
  operationalGraph: ontologyApi.operationalGraph,
  domainSchema: ontologyApi.domainSchema,

  listSignals: signalsApi.list,

  listEvents: eventsApi.list,
  entityEvents: eventsApi.forEntity,
};

export { dashboardApi, managersApi, propertiesApi, leasesApi, maintenanceApi, documentsApi };
export { searchApi, ownersApi, tenantsApi, actionsApi, notesApi, ontologyApi, signalsApi, eventsApi };
