"""Test that domain.yaml loads and parses into a typed DomainSchema."""

from __future__ import annotations

from remi.agent.signals import (
    DomainSchema,
    EntityTypeDef,
    ProcessDef,
    RelationshipDef,
    load_domain_yaml,
)

EXPECTED_ENTITY_TYPES = {
    "PropertyManager",
    "Property",
    "Unit",
    "Lease",
    "Tenant",
    "MaintenanceRequest",
    "Owner",
    "Vendor",
}

EXPECTED_PROCESSES = {
    "collections",
    "leasing",
    "maintenance",
    "turnover",
    "performance",
}


def _domain() -> DomainSchema:
    return DomainSchema.from_yaml(load_domain_yaml())


class TestYamlLoading:
    def test_domain_yaml_loads(self) -> None:
        raw = load_domain_yaml()
        assert raw["apiVersion"] == "remi/v1"
        assert raw["kind"] == "DomainSchema"

    def test_domain_schema_parses_typed(self) -> None:
        domain = _domain()
        assert len(domain.entity_types) >= 1
        assert len(domain.relationships) >= 1
        assert len(domain.processes) >= 1


class TestEntityTypes:
    def test_expected_entity_types_defined(self) -> None:
        domain = _domain()
        actual = {et.name for et in domain.entity_types}
        assert EXPECTED_ENTITY_TYPES.issubset(actual), (
            f"Missing entity types: {EXPECTED_ENTITY_TYPES - actual}"
        )

    def test_entity_types_are_typed(self) -> None:
        domain = _domain()
        for et in domain.entity_types:
            assert isinstance(et, EntityTypeDef)
            assert et.name
            assert et.description

    def test_entity_type_lookup(self) -> None:
        domain = _domain()
        assert domain.entity_type("PropertyManager") is not None
        assert domain.entity_type("NonexistentType") is None

    def test_entity_type_has_key_fields(self) -> None:
        domain = _domain()
        pm = domain.entity_type("PropertyManager")
        assert pm is not None
        assert len(pm.key_fields) > 0
        assert "name" in pm.key_fields


class TestRelationships:
    def test_relationships_are_typed(self) -> None:
        domain = _domain()
        for rel in domain.relationships:
            assert isinstance(rel, RelationshipDef)
            assert rel.name
            assert rel.source
            assert rel.target

    def test_manages_relationship_exists(self) -> None:
        domain = _domain()
        manages = [r for r in domain.relationships if r.name == "MANAGES"]
        assert len(manages) == 1
        assert manages[0].source == "PropertyManager"
        assert manages[0].target == "Property"

    def test_relationships_for_entity(self) -> None:
        domain = _domain()
        unit_rels = domain.relationships_for("Unit")
        rel_names = {r.name for r in unit_rels}
        assert "HAS_UNIT" in rel_names
        assert "HAS_LEASE" in rel_names


class TestProcesses:
    def test_expected_processes_defined(self) -> None:
        domain = _domain()
        actual = {p.name for p in domain.processes}
        assert EXPECTED_PROCESSES.issubset(actual), (
            f"Missing processes: {EXPECTED_PROCESSES - actual}"
        )

    def test_processes_are_typed(self) -> None:
        domain = _domain()
        for proc in domain.processes:
            assert isinstance(proc, ProcessDef)
            assert proc.name
            assert proc.description
            assert len(proc.involves) > 0

    def test_processes_involving_entity(self) -> None:
        domain = _domain()
        tenant_procs = domain.processes_involving("Tenant")
        proc_names = {p.name for p in tenant_procs}
        assert "collections" in proc_names
        assert "leasing" in proc_names


class TestDomainQueries:
    def test_entity_type_names(self) -> None:
        domain = _domain()
        names = domain.entity_type_names()
        assert "PropertyManager" in names
        assert "Unit" in names
        assert len(names) == len(domain.entity_types)
