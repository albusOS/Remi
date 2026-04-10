"""Test ingestion of real sample reports using deterministic column maps.

Simulates what the LLM would produce for each report type and tests
the full persist pipeline. No LLM calls needed.

Run with: uv run python scripts/test_real_ingestion.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


async def main() -> None:
    from remi.agent.documents.adapters.parsers import parse_document
    from remi.application.core.models.enums import ReportType
    from remi.application.ingestion.models import IngestionResult
    from remi.application.ingestion.operations import (
        IngestionCtx,
        ManagerResolver,
        ROW_PERSISTERS,
        apply_column_map,
        validate_rows,
    )
    from remi.application.stores.mem import InMemoryPropertyStore

    ps = InMemoryPropertyStore()
    reports = Path(__file__).resolve().parent.parent / "data" / "sample_reports" / "Alex_Budavich_Reports"
    ct = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    async def ingest(
        filename: str,
        column_map: dict[str, str],
        entity_type: str,
        report_type: ReportType,
        doc_id: str,
        *,
        upload_manager_id: str | None = None,
    ) -> IngestionResult:
        content = (reports / filename).read_bytes()
        doc = parse_document(filename, content, ct)
        print(f"  Parsed: {doc.row_count} rows, {len(doc.column_names)} cols")
        print(f"  Columns: {doc.column_names}")

        mapped = apply_column_map(doc.rows, column_map, entity_type)
        print(f"  Mapped: {len(mapped)} rows as {entity_type}")

        result = IngestionResult(document_id=doc_id, report_type=report_type)
        accepted = validate_rows(mapped, result)
        print(f"  Validated: {len(accepted)} accepted, {result.rows_rejected} rejected, {result.rows_skipped} skipped")

        ctx = IngestionCtx(
            platform="appfolio",
            report_type=report_type,
            doc_id=doc_id,
            namespace="ingestion",
            ps=ps,
            manager_resolver=ManagerResolver(ps),
            result=result,
            upload_manager_id=upload_manager_id,
        )

        errors = 0
        for row in accepted:
            persister = ROW_PERSISTERS.get(row.get("type", ""))
            if persister:
                try:
                    await persister(row, ctx)
                except Exception as e:
                    errors += 1
                    if errors <= 3:
                        print(f"  ERROR persisting row: {e}")

        print(f"  Entities: {result.entities_created}, errors: {errors}")
        return result

    print("=" * 70)
    print("REAL REPORT INGESTION TEST")
    print("=" * 70)

    # ── 1. Property Directory ─────────────────────────────────────────────
    print("\n── 1. Property Directory (property_directory-20260330.xlsx) ──")
    r1 = await ingest(
        "property_directory-20260330.xlsx",
        column_map={
            "Property": "property_address",
            "Units": "_unit_count",
            "Site Manager Name": "name",
        },
        entity_type="PropertyManager",
        report_type=ReportType.PROPERTY_DIRECTORY,
        doc_id="doc-prop-dir",
    )

    managers = await ps.list_managers()
    props = await ps.list_properties()
    total_units = 0
    for p in props:
        total_units += len(await ps.list_units(property_id=p.id))
    print(f"\n  State after property directory:")
    print(f"    Managers: {len(managers)}")
    print(f"    Properties: {len(props)}")
    print(f"    Units: {total_units}")
    assert total_units > 0, f"FAIL: total_units={total_units} after property directory"
    assert len(managers) > 0, f"FAIL: no managers created"
    assert len(props) > 0, f"FAIL: no properties created"
    print("  ✓ Property directory PASSED")

    # ── 2. Rent Roll / Vacancy ────────────────────────────────────────────
    print("\n── 2. Rent Roll / Vacancy (Rent Roll_Vacancy (1).xlsx) ──")
    r2 = await ingest(
        "Rent Roll_Vacancy (1).xlsx",
        column_map={
            "Property": "property_address",
            "Unit": "unit_number",
            "BD/BA": "_bd_ba",
            "Lease From": "start_date",
            "Lease To": "end_date",
            "Posted To Website": "_posted_website",
            "Posted To Internet": "_posted_internet",
            "Revenue": "_revenue",
            "Days Vacant": "_days_vacant",
            "Description": "_description",
        },
        entity_type="Unit",
        report_type=ReportType.RENT_ROLL,
        doc_id="doc-rent-roll",
        upload_manager_id=None,
    )

    props2 = await ps.list_properties()
    total_units2 = 0
    for p in props2:
        total_units2 += len(await ps.list_units(property_id=p.id))
    print(f"\n  State after rent roll:")
    print(f"    Properties: {len(props2)}")
    print(f"    Units: {total_units2}")
    assert total_units2 > total_units, f"FAIL: units didn't increase after rent roll"
    print("  ✓ Rent roll PASSED")

    # ── 3. Lease Expiration Detail ────────────────────────────────────────
    print("\n── 3. Lease Expiration (Lease Expiration Detail By Month.xlsx) ──")
    r3 = await ingest(
        "Lease Expiration Detail By Month.xlsx",
        column_map={
            "Tags": "_manager_tag",
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
        },
        entity_type="Lease",
        report_type=ReportType.LEASE_EXPIRATION,
        doc_id="doc-lease-exp",
    )

    total_units3 = 0
    for p in await ps.list_properties():
        total_units3 += len(await ps.list_units(property_id=p.id))
    leases = []
    for p in await ps.list_properties():
        for u in await ps.list_units(property_id=p.id):
            ls = await ps.list_leases(unit_id=u.id)
            leases.extend(ls)
    print(f"\n  State after lease expiration:")
    print(f"    Properties: {len(await ps.list_properties())}")
    print(f"    Units: {total_units3}")
    print(f"    Leases: {len(leases)}")
    assert len(leases) > 0, f"FAIL: no leases created"
    print("  ✓ Lease expiration PASSED")

    # ── 4. Delinquency ───────────────────────────────────────────────────
    print("\n── 4. Delinquency (Delinquency.xlsx) ──")
    r4 = await ingest(
        "Delinquency.xlsx",
        column_map={
            "Tenant Status": "tenant_status",
            "Property": "property_address",
            "Unit": "unit_number",
            "Name": "tenant_name",
            "Rent": "monthly_rent",
            "Amount Receivable": "balance_total",
            "Delinquent Subsidy Amount": "_subsidy",
            "Last Payment": "last_payment_date",
            "0-30": "balance_0_30",
            "30+": "balance_30_plus",
            "Tags": "_lease_tags",
            "Delinquency Notes": "notes",
        },
        entity_type="BalanceObservation",
        report_type=ReportType.DELINQUENCY,
        doc_id="doc-delinq",
    )

    print(f"\n  State after delinquency:")
    all_props = await ps.list_properties()
    total_units_final = 0
    for p in all_props:
        total_units_final += len(await ps.list_units(property_id=p.id))
    print(f"    Properties: {len(all_props)}")
    print(f"    Units: {total_units_final}")
    assert r4.entities_created > 0, f"FAIL: no entities from delinquency"
    print("  ✓ Delinquency PASSED")

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("FINAL STATE SUMMARY")
    all_managers = await ps.list_managers()
    all_props = await ps.list_properties()
    all_units_count = 0
    for p in all_props:
        all_units_count += len(await ps.list_units(property_id=p.id))
    all_leases = []
    for p in all_props:
        for u in await ps.list_units(property_id=p.id):
            ls = await ps.list_leases(unit_id=u.id)
            all_leases.extend(ls)

    print(f"  Managers:   {len(all_managers)}")
    print(f"  Properties: {len(all_props)}")
    print(f"  Units:      {all_units_count}")
    print(f"  Leases:     {len(all_leases)}")
    print("=" * 70)

    if all_units_count == 0:
        print("\n✗ FAILED: total_units is 0!")
        sys.exit(1)
    else:
        print(f"\n✓ ALL PASSED — {all_units_count} units, {len(all_leases)} leases, {len(all_managers)} managers")


if __name__ == "__main__":
    asyncio.run(main())
