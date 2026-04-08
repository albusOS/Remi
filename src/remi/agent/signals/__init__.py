"""signals — domain schema: entity types, relationships, and processes.

The domain schema describes the structural vocabulary of the business.
The agent discovers patterns and significance from actual data.
"""

from remi.agent.signals.tbox import (
    DomainSchema,
    DomainTBox,
    EntityTypeDef,
    MutableTBox,
    ProcessDef,
    RelationshipDef,
    load_domain_yaml,
    set_domain_yaml_path,
)

__all__ = [
    "DomainSchema",
    "DomainTBox",
    "EntityTypeDef",
    "MutableTBox",
    "ProcessDef",
    "RelationshipDef",
    "load_domain_yaml",
    "set_domain_yaml_path",
]
