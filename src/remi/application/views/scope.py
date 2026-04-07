"""Property-set scope resolution — the universal filter primitive.

Both owner and manager scoping resolve to a set of property IDs.
Resolvers accept this set directly and don't need to know which role
produced it.
"""

from __future__ import annotations

from remi.application.core.protocols import PropertyStore


async def property_ids_for_manager(store: PropertyStore, manager_id: str) -> set[str]:
    """Resolve the property IDs a manager is responsible for.

    Direct FK: Property.manager_id.
    """
    props = await store.list_properties(manager_id=manager_id)
    return {p.id for p in props}


async def property_ids_for_owner(store: PropertyStore, owner_id: str) -> set[str]:
    """Resolve the property IDs an owner holds.

    Direct FK: Property.owner_id.
    """
    props = await store.list_properties(owner_id=owner_id)
    return {p.id for p in props}
