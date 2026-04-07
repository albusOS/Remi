"""Shared test fixtures for the test suite."""

from __future__ import annotations

import pytest

from remi.agent.signals import DomainTBox, load_domain_yaml, set_domain_yaml_path
from remi.agent.workflow.loader import set_agents_dir
from remi.application.core.models import (
    Address,
    Property,
    PropertyManager,
)
from remi.application.infra.stores.mem import InMemoryPropertyStore
from remi.types.paths import AGENTS_DIR, DOMAIN_YAML_PATH


@pytest.fixture(autouse=True, scope="session")
def _configure_agent_paths() -> None:
    """Set agent/ module-level paths so tests can use load_workflow / load_domain_yaml."""
    set_agents_dir(AGENTS_DIR)
    set_domain_yaml_path(DOMAIN_YAML_PATH)


@pytest.fixture
def domain_tbox() -> DomainTBox:
    raw = load_domain_yaml()
    return DomainTBox.from_yaml(raw)


@pytest.fixture
def property_store() -> InMemoryPropertyStore:
    return InMemoryPropertyStore()


# ---------------------------------------------------------------------------
# Fixture data helpers
# ---------------------------------------------------------------------------

_ADDR = Address(street="100 Smithfield St", city="Pittsburgh", state="PA", zip_code="15222")


async def seed_basic_data(ps: InMemoryPropertyStore) -> dict[str, str]:
    """Seed one manager -> one property.

    Returns a dict of entity IDs for convenience.
    """
    mgr = PropertyManager(id="mgr-1", name="Jake Kraus", email="jake@rivaridge.com")
    await ps.upsert_manager(mgr)

    prop = Property(id="prop-1", manager_id="mgr-1", name="100 Smithfield St", address=_ADDR)
    await ps.upsert_property(prop)

    return {"manager_id": "mgr-1", "property_id": "prop-1"}
