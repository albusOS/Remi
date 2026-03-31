"""Test DelinquencyConcentration signal detection."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from remi.knowledge.entailment.engine import EntailmentEngine
from remi.models.properties import Lease, LeaseStatus, Tenant, Unit
from remi.models.signals import Severity
from remi.stores.properties import InMemoryPropertyStore
from remi.stores.signals import InMemorySignalStore
from tests.conftest import seed_basic_portfolio


@pytest.mark.asyncio
async def test_delinquency_fires_above_critical(
    engine: EntailmentEngine,
    property_store: InMemoryPropertyStore,
    signal_store: InMemorySignalStore,
) -> None:
    ids = await seed_basic_portfolio(property_store)
    today = date.today()

    await property_store.upsert_unit(Unit(
        id="u-1", property_id=ids["property_id"], unit_number="101",
    ))
    await property_store.upsert_tenant(Tenant(
        id="t-1", name="Delinquent Dan", email="d@test.com",
        balance_owed=Decimal("500"), balance_30_plus=Decimal("300"),
    ))
    await property_store.upsert_lease(Lease(
        id="l-1", unit_id="u-1", tenant_id="t-1",
        property_id=ids["property_id"],
        start_date=today - timedelta(days=365),
        end_date=today + timedelta(days=180),
        monthly_rent=Decimal("1000"),
        status=LeaseStatus.ACTIVE,
    ))

    await engine.run_all()
    sigs = await signal_store.list_signals(signal_type="DelinquencyConcentration")

    assert len(sigs) == 1
    assert sigs[0].severity == Severity.HIGH
    assert sigs[0].evidence["delinquent_count"] == 1
    assert sigs[0].evidence["delinquency_rate"] >= 0.08


@pytest.mark.asyncio
async def test_delinquency_does_not_fire_below_threshold(
    engine: EntailmentEngine,
    property_store: InMemoryPropertyStore,
    signal_store: InMemorySignalStore,
) -> None:
    ids = await seed_basic_portfolio(property_store)
    today = date.today()

    await property_store.upsert_unit(Unit(
        id="u-1", property_id=ids["property_id"], unit_number="101",
    ))
    await property_store.upsert_tenant(Tenant(
        id="t-1", name="Good Guy", email="g@test.com",
        balance_owed=Decimal("50"),
    ))
    await property_store.upsert_lease(Lease(
        id="l-1", unit_id="u-1", tenant_id="t-1",
        property_id=ids["property_id"],
        start_date=today - timedelta(days=365),
        end_date=today + timedelta(days=180),
        monthly_rent=Decimal("2000"),
        status=LeaseStatus.ACTIVE,
    ))

    await engine.run_all()
    sigs = await signal_store.list_signals(signal_type="DelinquencyConcentration")
    assert len(sigs) == 0
