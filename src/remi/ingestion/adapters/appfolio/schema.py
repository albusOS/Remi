"""AppFolio report type definitions: enums, column maps, detection rules.

Encodes the exact column layouts and section labels from real AppFolio
exports.  Nothing in this module depends on domain models or ingestion logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AppFolioReportType(StrEnum):
    RENT_ROLL = "rent_roll"
    DELINQUENCY = "delinquency"
    LEASE_EXPIRATION = "lease_expiration"
    PROPERTY_DIRECTORY = "property_directory"
    UNKNOWN = "unknown"


# Human-readable descriptions used in LLM classification prompts.
REPORT_TYPE_DESCRIPTIONS: dict[str, str] = {
    AppFolioReportType.RENT_ROLL: (
        "Lists every unit in the portfolio with occupancy status, lease dates, "
        "rent, and vacancy days. Typically has section headers like Current / Vacant-Unrented."
    ),
    AppFolioReportType.DELINQUENCY: (
        "Shows tenants with outstanding balances: amount owed, 0-30 day and 30+ day buckets, "
        "last payment date, and tenant status (Current / Notice / Evict)."
    ),
    AppFolioReportType.LEASE_EXPIRATION: (
        "Details upcoming lease expirations: move-in date, lease-end date, rent vs market rent, "
        "sqft, tenant name. Often has a Tags column carrying the property manager name."
    ),
    AppFolioReportType.PROPERTY_DIRECTORY: (
        "A listing of all properties in the portfolio with their assigned property manager "
        "and basic address information. Some properties may have no manager assigned."
    ),
}

# ---------------------------------------------------------------------------
# Column definitions per report type
# ---------------------------------------------------------------------------

RENT_ROLL_COLUMNS: dict[str, str] = {
    "Property": "property_address",
    "Unit": "unit_number",
    "BD/BA": "bd_ba",
    "Lease From": "lease_start",
    "Lease To": "lease_end",
    "Posted To Website": "posted_website",
    "Posted To Internet": "posted_internet",
    "Revenue": "revenue_flag",
    "Days Vacant": "days_vacant",
    "Description": "notes",
}

# Rent roll section headers → occupancy status slug
RENT_ROLL_SECTIONS: dict[str, str] = {
    "Current": "occupied",
    "Notice-Rented": "notice_rented",
    "Notice-Unrented": "notice_unrented",
    "Vacant-Rented": "vacant_rented",
    "Vacant-Unrented": "vacant_unrented",
}

DELINQUENCY_COLUMNS: dict[str, str] = {
    "Tenant Status": "tenant_status",
    "Property": "property_address",
    "Unit": "unit_number",
    "Name": "tenant_name",
    "Rent": "monthly_rent",
    "Amount Receivable": "amount_owed",
    "Delinquent Subsidy Amount": "subsidy_delinquent",
    "Last Payment": "last_payment_date",
    "0-30": "balance_0_30",
    "30+": "balance_30_plus",
    "Tags": "tags",
    "Delinquency Notes": "delinquency_notes",
}

LEASE_EXPIRATION_COLUMNS: dict[str, str] = {
    "Tags": "tags",
    "Property": "property_address",
    "Unit": "unit_number",
    "Move In": "move_in_date",
    "Lease Expires": "lease_expires",
    "Rent": "monthly_rent",
    "Market Rent": "market_rent",
    "Sqft": "sqft",
    "Tenant Name": "tenant_name",
    "Deposit": "deposit",
    "Phone Numbers": "phone_numbers",
}


@dataclass(frozen=True)
class ReportTypeDefinition:
    """Describes how to structurally detect a report type from its column names.

    required_columns: every column must be present for this type to be a candidate.
    signature_columns: characteristic columns that raise confidence when present.
    min_score: fraction of signature_columns that must match (0-1). Defaults to 0.5.
    """

    report_type: str
    required_columns: frozenset[str]
    signature_columns: frozenset[str]
    min_score: float = 0.5


# Ordered by specificity (most distinctive first).  Earlier entries win ties.
REPORT_TYPE_DEFINITIONS: list[ReportTypeDefinition] = [
    ReportTypeDefinition(
        report_type=AppFolioReportType.DELINQUENCY,
        required_columns=frozenset({"Property", "Unit", "0-30", "30+", "Amount Receivable"}),
        signature_columns=frozenset(
            {
                "Tenant Status",
                "Name",
                "Last Payment",
                "Tags",
                "Delinquency Notes",
                "Rent",
                "Delinquent Subsidy Amount",
            }
        ),
    ),
    ReportTypeDefinition(
        report_type=AppFolioReportType.LEASE_EXPIRATION,
        required_columns=frozenset({"Property", "Unit", "Lease Expires", "Market Rent"}),
        signature_columns=frozenset(
            {"Tags", "Move In", "Sqft", "Tenant Name", "Deposit", "Phone Numbers", "Rent"}
        ),
    ),
    ReportTypeDefinition(
        report_type=AppFolioReportType.RENT_ROLL,
        required_columns=frozenset({"Property", "Unit", "Lease From", "Lease To", "Days Vacant"}),
        signature_columns=frozenset(
            {"BD/BA", "Posted To Website", "Posted To Internet", "Revenue", "Description"}
        ),
    ),
    ReportTypeDefinition(
        report_type=AppFolioReportType.PROPERTY_DIRECTORY,
        required_columns=frozenset({"Property"}),
        signature_columns=frozenset({
            "Site Manager Name", "Property Manager", "Units",
            "Type", "Address", "Status",
        }),
        min_score=0.2,
    ),
]
