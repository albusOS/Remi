import { get, qs } from "./client";
import type {
  DashboardOverview,
  DelinquencyBoard,
  LeaseCalendar,
  VacancyTracker,
  NeedsManagerResponse,
  DelinquencyTrend,
  OccupancyTrend,
  RentTrend,
  MaintenanceTrend,
} from "@/lib/types";

type Scope = { manager_id?: string; owner_id?: string };

export const dashboardApi = {
  overview: (scope?: Scope) =>
    get<DashboardOverview>(`/api/v1/dashboard/overview${qs(scope || {})}`),

  delinquencyBoard: (scope?: Scope) =>
    get<DelinquencyBoard>(`/api/v1/dashboard/delinquency${qs(scope || {})}`),

  leasesExpiring: (days = 90, scope?: Scope) =>
    get<LeaseCalendar>(`/api/v1/dashboard/leases/expiring${qs({ days, ...scope })}`),

  vacancyTracker: (scope?: Scope) =>
    get<VacancyTracker>(`/api/v1/dashboard/vacancies${qs(scope || {})}`),

  needsManager: () =>
    get<NeedsManagerResponse>("/api/v1/dashboard/needs-manager"),

  delinquencyTrend: (scope?: { manager_id?: string; property_id?: string; periods?: number }) =>
    get<DelinquencyTrend>(`/api/v1/dashboard/trends/delinquency${qs(scope || {})}`),

  occupancyTrend: (scope?: { manager_id?: string; property_id?: string; periods?: number }) =>
    get<OccupancyTrend>(`/api/v1/dashboard/trends/occupancy${qs(scope || {})}`),

  rentTrend: (scope?: { manager_id?: string; property_id?: string; periods?: number }) =>
    get<RentTrend>(`/api/v1/dashboard/trends/rent${qs(scope || {})}`),

  maintenanceTrend: (scope?: { manager_id?: string; property_id?: string; unit_id?: string; periods?: number }) =>
    get<MaintenanceTrend>(`/api/v1/dashboard/trends/maintenance${qs(scope || {})}`),
};
