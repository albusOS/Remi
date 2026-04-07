"""PostgresPropertyStore — full PropertyStore backed by Postgres via SQLModel."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlmodel import select

from remi.application.core.models import (
    ActionItem,
    ActionItemStatus,
    BalanceObservation,
    Document,
    DocumentType,
    Lease,
    LeaseStatus,
    MaintenanceRequest,
    MaintenanceStatus,
    MeetingBrief,
    Note,
    NoteProvenance,
    Owner,
    Property,
    PropertyManager,
    Tenant,
    TenantStatus,
    TradeCategory,
    Unit,
    Vendor,
)
from remi.application.core.protocols import PropertyStore
from remi.application.infra.stores.pg.converters import (
    action_item_from_row,
    action_item_to_row,
    apply_merge,
    balance_observation_from_row,
    balance_observation_to_row,
    document_from_row,
    document_to_row,
    lease_from_row,
    lease_to_row,
    maintenance_from_row,
    maintenance_to_row,
    manager_from_row,
    manager_to_row,
    note_from_row,
    note_to_row,
    owner_from_row,
    owner_to_row,
    property_from_row,
    property_to_row,
    tenant_from_row,
    tenant_to_row,
    unit_from_row,
    unit_to_row,
    vendor_from_row,
    vendor_to_row,
)
from remi.application.infra.stores.pg.tables import (
    ActionItemRow,
    AppDocumentRow,
    BalanceObservationRow,
    LeaseRow,
    MaintenanceRequestRow,
    NoteRow,
    OwnerRow,
    PropertyManagerRow,
    PropertyRow,
    TenantRow,
    UnitRow,
    VendorRow,
)
from remi.types.result import WriteOutcome, WriteResult


class PostgresPropertyStore(PropertyStore):
    """PropertyStore backed by Postgres via SQLModel async sessions."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._pg_meeting_briefs: dict[str, MeetingBrief] = {}

    # -- PropertyManager ----------------------------------------------------

    async def get_manager(self, manager_id: str) -> PropertyManager | None:
        async with self._session_factory() as session:
            row = await session.get(PropertyManagerRow, manager_id)
            return manager_from_row(row) if row else None

    async def list_managers(self) -> list[PropertyManager]:
        async with self._session_factory() as session:
            result = await session.execute(select(PropertyManagerRow))
            return [manager_from_row(r) for r in result.scalars().all()]

    async def upsert_manager(self, manager: PropertyManager) -> WriteResult[PropertyManager]:
        async with self._session_factory() as session:
            existing = await session.get(PropertyManagerRow, manager.id)
            if existing:
                if manager.content_hash and existing.content_hash == manager.content_hash:
                    return WriteResult(entity=manager_from_row(existing), outcome=WriteOutcome.NOOP)
                apply_merge(existing, manager)
                session.add(existing)
                await session.commit()
                await session.refresh(existing)
                return WriteResult(entity=manager_from_row(existing), outcome=WriteOutcome.UPDATED)
            session.add(manager_to_row(manager))
            await session.commit()
            return WriteResult(entity=manager, outcome=WriteOutcome.CREATED)

    async def delete_manager(self, manager_id: str) -> bool:
        async with self._session_factory() as session:
            row = await session.get(PropertyManagerRow, manager_id)
            if not row:
                return False

            mgr_prop_result = await session.execute(
                select(PropertyRow).where(PropertyRow.manager_id == manager_id)
            )
            for prop in mgr_prop_result.scalars().all():
                prop.manager_id = None
                session.add(prop)

            await session.delete(row)
            await session.commit()
            return True

    # -- Property -----------------------------------------------------------

    async def get_property(self, property_id: str) -> Property | None:
        async with self._session_factory() as session:
            row = await session.get(PropertyRow, property_id)
            return property_from_row(row) if row else None

    async def list_properties(
        self,
        *,
        manager_id: str | None = None,
        owner_id: str | None = None,
    ) -> list[Property]:
        async with self._session_factory() as session:
            stmt = select(PropertyRow)
            if manager_id:
                stmt = stmt.where(PropertyRow.manager_id == manager_id)
            if owner_id:
                stmt = stmt.where(PropertyRow.owner_id == owner_id)
            result = await session.execute(stmt)
            return [property_from_row(r) for r in result.scalars().all()]

    async def upsert_property(self, prop: Property) -> WriteResult[Property]:
        async with self._session_factory() as session:
            existing = await session.get(PropertyRow, prop.id)
            if existing:
                if prop.content_hash and existing.content_hash == prop.content_hash:
                    return WriteResult(
                        entity=property_from_row(existing),
                        outcome=WriteOutcome.NOOP,
                    )
                apply_merge(existing, prop)
                session.add(existing)
                await session.commit()
                await session.refresh(existing)
                entity = property_from_row(existing)
                return WriteResult(entity=entity, outcome=WriteOutcome.UPDATED)
            session.add(property_to_row(prop))
            await session.commit()
            return WriteResult(entity=prop, outcome=WriteOutcome.CREATED)

    async def delete_property(self, property_id: str) -> bool:
        async with self._session_factory() as session:
            row = await session.get(PropertyRow, property_id)
            if not row:
                return False
            for tbl in (UnitRow, LeaseRow):
                result = await session.execute(
                    select(tbl).where(tbl.property_id == property_id)  # type: ignore[attr-defined]
                )
                for child in result.scalars().all():
                    await session.delete(child)
            await session.delete(row)
            await session.commit()
            return True

    # -- Unit ---------------------------------------------------------------

    async def get_unit(self, unit_id: str) -> Unit | None:
        async with self._session_factory() as session:
            row = await session.get(UnitRow, unit_id)
            return unit_from_row(row) if row else None

    async def list_units(
        self,
        *,
        property_id: str | None = None,
    ) -> list[Unit]:
        async with self._session_factory() as session:
            stmt = select(UnitRow)
            if property_id:
                stmt = stmt.where(UnitRow.property_id == property_id)
            result = await session.execute(stmt)
            return [unit_from_row(r) for r in result.scalars().all()]

    async def upsert_unit(self, unit: Unit) -> WriteResult[Unit]:
        async with self._session_factory() as session:
            existing = await session.get(UnitRow, unit.id)
            if existing:
                if unit.content_hash and existing.content_hash == unit.content_hash:
                    return WriteResult(entity=unit_from_row(existing), outcome=WriteOutcome.NOOP)
                apply_merge(existing, unit)
                session.add(existing)
                await session.commit()
                await session.refresh(existing)
                return WriteResult(entity=unit_from_row(existing), outcome=WriteOutcome.UPDATED)
            session.add(unit_to_row(unit))
            await session.commit()
            return WriteResult(entity=unit, outcome=WriteOutcome.CREATED)

    async def delete_unit(self, unit_id: str) -> bool:
        async with self._session_factory() as session:
            row = await session.get(UnitRow, unit_id)
            if not row:
                return False
            await session.delete(row)
            await session.commit()
            return True

    # -- Lease --------------------------------------------------------------

    async def get_lease(self, lease_id: str) -> Lease | None:
        async with self._session_factory() as session:
            row = await session.get(LeaseRow, lease_id)
            return lease_from_row(row) if row else None

    async def list_leases(
        self,
        *,
        unit_id: str | None = None,
        tenant_id: str | None = None,
        property_id: str | None = None,
        status: LeaseStatus | None = None,
    ) -> list[Lease]:
        async with self._session_factory() as session:
            stmt = select(LeaseRow)
            if unit_id:
                stmt = stmt.where(LeaseRow.unit_id == unit_id)
            if tenant_id:
                stmt = stmt.where(LeaseRow.tenant_id == tenant_id)
            if property_id:
                stmt = stmt.where(LeaseRow.property_id == property_id)
            if status:
                stmt = stmt.where(LeaseRow.status == status.value)
            result = await session.execute(stmt)
            return [lease_from_row(r) for r in result.scalars().all()]

    async def upsert_lease(self, lease: Lease) -> WriteResult[Lease]:
        async with self._session_factory() as session:
            existing = await session.get(LeaseRow, lease.id)
            if existing:
                if lease.content_hash and existing.content_hash == lease.content_hash:
                    return WriteResult(entity=lease_from_row(existing), outcome=WriteOutcome.NOOP)
                apply_merge(existing, lease)
                session.add(existing)
                await session.commit()
                await session.refresh(existing)
                return WriteResult(entity=lease_from_row(existing), outcome=WriteOutcome.UPDATED)
            session.add(lease_to_row(lease))
            await session.commit()
            return WriteResult(entity=lease, outcome=WriteOutcome.CREATED)

    async def delete_lease(self, lease_id: str) -> bool:
        async with self._session_factory() as session:
            row = await session.get(LeaseRow, lease_id)
            if not row:
                return False
            await session.delete(row)
            await session.commit()
            return True

    # -- Tenant -------------------------------------------------------------

    async def get_tenant(self, tenant_id: str) -> Tenant | None:
        async with self._session_factory() as session:
            row = await session.get(TenantRow, tenant_id)
            return tenant_from_row(row) if row else None

    async def list_tenants(
        self,
        *,
        property_id: str | None = None,
        status: TenantStatus | None = None,
    ) -> list[Tenant]:
        async with self._session_factory() as session:
            stmt = select(TenantRow)
            if property_id:
                lease_stmt = select(LeaseRow.tenant_id).where(LeaseRow.property_id == property_id)
                stmt = stmt.where(TenantRow.id.in_(lease_stmt))  # type: ignore[union-attr]
            if status:
                stmt = stmt.where(TenantRow.status == status.value)
            result = await session.execute(stmt)
            return [tenant_from_row(r) for r in result.scalars().all()]

    async def upsert_tenant(self, tenant: Tenant) -> WriteResult[Tenant]:
        async with self._session_factory() as session:
            existing = await session.get(TenantRow, tenant.id)
            if existing:
                if tenant.content_hash and existing.content_hash == tenant.content_hash:
                    return WriteResult(entity=tenant_from_row(existing), outcome=WriteOutcome.NOOP)
                apply_merge(existing, tenant)
                session.add(existing)
                await session.commit()
                await session.refresh(existing)
                return WriteResult(entity=tenant_from_row(existing), outcome=WriteOutcome.UPDATED)
            session.add(tenant_to_row(tenant))
            await session.commit()
            return WriteResult(entity=tenant, outcome=WriteOutcome.CREATED)

    async def delete_tenant(self, tenant_id: str) -> bool:
        async with self._session_factory() as session:
            row = await session.get(TenantRow, tenant_id)
            if not row:
                return False
            result = await session.execute(select(LeaseRow).where(LeaseRow.tenant_id == tenant_id))
            for lease in result.scalars().all():
                await session.delete(lease)
            await session.delete(row)
            await session.commit()
            return True

    # -- Maintenance --------------------------------------------------------

    async def get_maintenance_request(self, request_id: str) -> MaintenanceRequest | None:
        async with self._session_factory() as session:
            row = await session.get(MaintenanceRequestRow, request_id)
            return maintenance_from_row(row) if row else None

    async def list_maintenance_requests(
        self,
        *,
        property_id: str | None = None,
        unit_id: str | None = None,
        manager_id: str | None = None,
        status: MaintenanceStatus | None = None,
    ) -> list[MaintenanceRequest]:
        async with self._session_factory() as session:
            stmt = select(MaintenanceRequestRow)
            if manager_id:
                stmt = stmt.join(
                    PropertyRow,
                    MaintenanceRequestRow.property_id == PropertyRow.id,
                ).where(PropertyRow.manager_id == manager_id)
            if property_id:
                stmt = stmt.where(MaintenanceRequestRow.property_id == property_id)
            if unit_id:
                stmt = stmt.where(MaintenanceRequestRow.unit_id == unit_id)
            if status:
                stmt = stmt.where(MaintenanceRequestRow.status == status.value)
            result = await session.execute(stmt)
            return [maintenance_from_row(r) for r in result.scalars().all()]

    async def upsert_maintenance_request(
        self,
        request: MaintenanceRequest,
    ) -> WriteResult[MaintenanceRequest]:
        async with self._session_factory() as session:
            existing = await session.get(MaintenanceRequestRow, request.id)
            if existing:
                if request.content_hash and existing.content_hash == request.content_hash:
                    return WriteResult(
                        entity=maintenance_from_row(existing),
                        outcome=WriteOutcome.NOOP,
                    )
                apply_merge(existing, request)
                session.add(existing)
                await session.commit()
                await session.refresh(existing)
                return WriteResult(
                    entity=maintenance_from_row(existing),
                    outcome=WriteOutcome.UPDATED,
                )
            session.add(maintenance_to_row(request))
            await session.commit()
            return WriteResult(entity=request, outcome=WriteOutcome.CREATED)

    async def delete_maintenance_request(self, request_id: str) -> bool:
        async with self._session_factory() as session:
            row = await session.get(MaintenanceRequestRow, request_id)
            if not row:
                return False
            await session.delete(row)
            await session.commit()
            return True

    # -- Owners ---------------------------------------------------------------

    async def get_owner(self, owner_id: str) -> Owner | None:
        async with self._session_factory() as session:
            row = await session.get(OwnerRow, owner_id)
            return owner_from_row(row) if row else None

    async def list_owners(self) -> list[Owner]:
        async with self._session_factory() as session:
            result = await session.execute(select(OwnerRow))
            return [owner_from_row(r) for r in result.scalars().all()]

    async def upsert_owner(self, owner: Owner) -> WriteResult[Owner]:
        async with self._session_factory() as session:
            existing = await session.get(OwnerRow, owner.id)
            if existing:
                if owner.content_hash and existing.content_hash == owner.content_hash:
                    return WriteResult(entity=owner_from_row(existing), outcome=WriteOutcome.NOOP)
                apply_merge(existing, owner)
                session.add(existing)
                await session.commit()
                await session.refresh(existing)
                return WriteResult(entity=owner_from_row(existing), outcome=WriteOutcome.UPDATED)
            session.add(owner_to_row(owner))
            await session.commit()
            return WriteResult(entity=owner, outcome=WriteOutcome.CREATED)

    # -- Vendors --------------------------------------------------------------

    async def get_vendor(self, vendor_id: str) -> Vendor | None:
        async with self._session_factory() as session:
            row = await session.get(VendorRow, vendor_id)
            return vendor_from_row(row) if row else None

    async def list_vendors(
        self,
        *,
        category: TradeCategory | None = None,
        is_internal: bool | None = None,
    ) -> list[Vendor]:
        async with self._session_factory() as session:
            stmt = select(VendorRow)
            if category:
                stmt = stmt.where(VendorRow.category == category.value)
            if is_internal is not None:
                stmt = stmt.where(VendorRow.is_internal == is_internal)
            result = await session.execute(stmt)
            return [vendor_from_row(r) for r in result.scalars().all()]

    async def upsert_vendor(self, vendor: Vendor) -> WriteResult[Vendor]:
        async with self._session_factory() as session:
            existing = await session.get(VendorRow, vendor.id)
            if existing:
                if vendor.content_hash and existing.content_hash == vendor.content_hash:
                    return WriteResult(entity=vendor_from_row(existing), outcome=WriteOutcome.NOOP)
                apply_merge(existing, vendor)
                session.add(existing)
                await session.commit()
                await session.refresh(existing)
                return WriteResult(entity=vendor_from_row(existing), outcome=WriteOutcome.UPDATED)
            session.add(vendor_to_row(vendor))
            await session.commit()
            return WriteResult(entity=vendor, outcome=WriteOutcome.CREATED)

    # -- Action Items -------------------------------------------------------

    async def get_action_item(self, item_id: str) -> ActionItem | None:
        async with self._session_factory() as session:
            row = await session.get(ActionItemRow, item_id)
            return action_item_from_row(row) if row else None

    async def list_action_items(
        self,
        *,
        manager_id: str | None = None,
        property_id: str | None = None,
        tenant_id: str | None = None,
        status: ActionItemStatus | None = None,
    ) -> list[ActionItem]:
        async with self._session_factory() as session:
            stmt = select(ActionItemRow)
            if manager_id:
                stmt = stmt.where(ActionItemRow.manager_id == manager_id)
            if property_id:
                stmt = stmt.where(ActionItemRow.property_id == property_id)
            if tenant_id:
                stmt = stmt.where(ActionItemRow.tenant_id == tenant_id)
            if status:
                stmt = stmt.where(ActionItemRow.status == status.value)
            result = await session.execute(stmt)
            return [action_item_from_row(r) for r in result.scalars().all()]

    async def upsert_action_item(self, item: ActionItem) -> WriteResult[ActionItem]:
        async with self._session_factory() as session:
            existing = await session.get(ActionItemRow, item.id)
            if existing:
                apply_merge(existing, item)
                session.add(existing)
                await session.commit()
                await session.refresh(existing)
                return WriteResult(
                    entity=action_item_from_row(existing),
                    outcome=WriteOutcome.UPDATED,
                )
            session.add(action_item_to_row(item))
            await session.commit()
            return WriteResult(entity=item, outcome=WriteOutcome.CREATED)

    async def delete_action_item(self, item_id: str) -> bool:
        async with self._session_factory() as session:
            row = await session.get(ActionItemRow, item_id)
            if not row:
                return False
            await session.delete(row)
            await session.commit()
            return True

    # -- Notes ----------------------------------------------------------------

    async def get_note(self, note_id: str) -> Note | None:
        async with self._session_factory() as session:
            row = await session.get(NoteRow, note_id)
            return note_from_row(row) if row else None

    async def list_notes(
        self,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
        provenance: NoteProvenance | None = None,
    ) -> list[Note]:
        async with self._session_factory() as session:
            stmt = select(NoteRow)
            if entity_type:
                stmt = stmt.where(NoteRow.entity_type == entity_type)
            if entity_id:
                stmt = stmt.where(NoteRow.entity_id == entity_id)
            if provenance:
                stmt = stmt.where(NoteRow.provenance == provenance.value)
            result = await session.execute(stmt)
            return [note_from_row(r) for r in result.scalars().all()]

    async def upsert_note(self, note: Note) -> WriteResult[Note]:
        async with self._session_factory() as session:
            existing = await session.get(NoteRow, note.id)
            if existing:
                apply_merge(existing, note)
                session.add(existing)
                await session.commit()
                await session.refresh(existing)
                return WriteResult(entity=note_from_row(existing), outcome=WriteOutcome.UPDATED)
            session.add(note_to_row(note))
            await session.commit()
            return WriteResult(entity=note, outcome=WriteOutcome.CREATED)

    async def delete_note(self, note_id: str) -> bool:
        async with self._session_factory() as session:
            row = await session.get(NoteRow, note_id)
            if not row:
                return False
            await session.delete(row)
            await session.commit()
            return True

    # -- Meeting Briefs (in-memory; PG table not yet migrated) -----------------

    async def list_meeting_briefs(
        self,
        *,
        manager_id: str | None = None,
        limit: int = 20,
    ) -> list[MeetingBrief]:
        briefs = list(self._pg_meeting_briefs.values())
        if manager_id:
            briefs = [b for b in briefs if b.manager_id == manager_id]
        briefs.sort(key=lambda b: b.generated_at, reverse=True)
        return briefs[:limit]

    async def upsert_meeting_brief(
        self,
        brief: MeetingBrief,
    ) -> WriteResult[MeetingBrief]:
        self._pg_meeting_briefs[brief.id] = brief
        return WriteResult(entity=brief, outcome=WriteOutcome.CREATED)

    # -- Documents ------------------------------------------------------------

    async def get_document(self, doc_id: str) -> Document | None:
        async with self._session_factory() as session:
            row = await session.get(AppDocumentRow, doc_id)
            return document_from_row(row) if row else None

    async def list_documents(
        self,
        *,
        unit_id: str | None = None,
        property_id: str | None = None,
        manager_id: str | None = None,
        lease_id: str | None = None,
        document_type: DocumentType | None = None,
    ) -> list[Document]:
        async with self._session_factory() as session:
            stmt = select(AppDocumentRow)
            if unit_id:
                stmt = stmt.where(AppDocumentRow.unit_id == unit_id)
            if property_id:
                stmt = stmt.where(AppDocumentRow.property_id == property_id)
            if manager_id:
                stmt = stmt.where(AppDocumentRow.manager_id == manager_id)
            if lease_id:
                stmt = stmt.where(AppDocumentRow.lease_id == lease_id)
            if document_type:
                stmt = stmt.where(AppDocumentRow.document_type == document_type.value)
            result = await session.execute(stmt)
            return [document_from_row(r) for r in result.scalars().all()]

    async def find_by_content_hash(self, content_hash: str) -> Document | None:
        if not content_hash:
            return None
        async with self._session_factory() as session:
            stmt = select(AppDocumentRow).where(AppDocumentRow.content_hash == content_hash)
            result = await session.execute(stmt)
            row = result.scalars().first()
            return document_from_row(row) if row else None

    async def upsert_document(self, doc: Document) -> WriteResult[Document]:
        async with self._session_factory() as session:
            existing = await session.get(AppDocumentRow, doc.id)
            if existing:
                apply_merge(existing, doc)
                session.add(existing)
                await session.commit()
                await session.refresh(existing)
                return WriteResult(entity=document_from_row(existing), outcome=WriteOutcome.UPDATED)
            session.add(document_to_row(doc))
            await session.commit()
            return WriteResult(entity=doc, outcome=WriteOutcome.CREATED)

    async def delete_document(self, doc_id: str) -> bool:
        async with self._session_factory() as session:
            row = await session.get(AppDocumentRow, doc_id)
            if not row:
                return False
            await session.delete(row)
            await session.commit()
            return True

    # -- BalanceObservation ---------------------------------------------------

    async def list_balance_observations(
        self,
        *,
        tenant_id: str | None = None,
        property_id: str | None = None,
    ) -> list[BalanceObservation]:
        async with self._session_factory() as session:
            stmt = select(BalanceObservationRow)
            if tenant_id:
                stmt = stmt.where(BalanceObservationRow.tenant_id == tenant_id)
            if property_id:
                stmt = stmt.where(BalanceObservationRow.property_id == property_id)
            stmt = stmt.order_by(BalanceObservationRow.observed_at.desc())  # type: ignore[attr-defined]
            result = await session.execute(stmt)
            return [balance_observation_from_row(r) for r in result.scalars().all()]

    async def insert_balance_observation(
        self, obs: BalanceObservation
    ) -> WriteResult[BalanceObservation]:
        async with self._session_factory() as session:
            existing = await session.get(BalanceObservationRow, obs.id)
            if existing:
                return WriteResult(
                    entity=balance_observation_from_row(existing), outcome=WriteOutcome.NOOP
                )
            session.add(balance_observation_to_row(obs))
            await session.commit()
            return WriteResult(entity=obs, outcome=WriteOutcome.CREATED)
