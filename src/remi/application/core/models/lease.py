"""Lease — a contract between a tenant and a unit for a period of time."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from remi.application.core.models.enums import LeaseStatus, LeaseType, RenewalStatus


class Lease(BaseModel, frozen=True):
    """A lease contract — preserved across ingestion cycles, never overwritten.

    market_rent is the market rate AT THE TIME this lease was signed or last
    renewed — used for loss-to-lease calculations against this specific contract.

    first_seen_at: when this lease first appeared in a report.
    last_confirmed_at: the most recent report that confirmed this lease is active.
    When a tenant vacates, the lease status is set to TERMINATED/EXPIRED;
    the record is kept for historical occupancy queries.
    """

    # --- Identity ---
    id: str
    unit_id: str
    tenant_id: str
    property_id: str
    # --- Contract terms ---
    start_date: date
    end_date: date
    monthly_rent: Decimal
    deposit: Decimal = Decimal("0")
    status: LeaseStatus = LeaseStatus.ACTIVE
    market_rent: Decimal = Decimal("0")
    is_month_to_month: bool = False
    lease_type: LeaseType | None = None
    notice_days: int | None = None
    subsidy_program: str | None = None
    # --- Renewal lifecycle ---
    renewal_status: RenewalStatus | None = None
    renewal_offered_date: date | None = None
    renewal_offer_rent: Decimal | None = None
    renewal_offer_term_months: int | None = None
    # --- Concessions ---
    concession_amount: Decimal | None = None
    concession_months: int | None = None
    # --- Lifecycle dates ---
    prior_lease_id: str | None = None
    notice_date: date | None = None
    move_in_date: date | None = None
    move_out_date: date | None = None
    first_seen_at: datetime | None = None
    last_confirmed_at: datetime | None = None
    # --- Provenance ---
    content_hash: str | None = None
    source_document_id: str | None = None
