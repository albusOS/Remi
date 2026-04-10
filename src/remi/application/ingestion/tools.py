"""Ingestion tools — agent-callable operations for document entity extraction.

Six tools expose the ingestion pipeline to the agent:

  ``ingest_analyze``        — return column headers, metadata, and sample rows
  ``ingest_format_lookup``  — check format registry for a known column mapping
  ``ingest_resolve``        — batch-resolve addresses + manager tags against existing store
  ``ingest_run``            — run the map/validate/persist pipeline
  ``ingest_format_save``    — save a confirmed column mapping to the registry
  ``ingest_finalize``       — update document record and publish completion event

Happy path (known format): analyze → resolve → format_lookup (hit) → run → finalize.
New format: analyze → resolve → format_lookup (miss) → agent builds map → run → format_save → finalize.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from remi.agent.documents import ContentStore
from remi.agent.events import DomainEvent, EventBus
from remi.agent.types import ToolArg, ToolDefinition, ToolProvider, ToolRegistry
from remi.application.core.models import PropertyManager, ReportType
from remi.application.core.protocols import PropertyStore
from remi.application.core.rules import manager_name_from_tag
from remi.application.ingestion.formats import (
    FormatRegistry,
    IngestionFormat,
    column_signature,
    format_id,
)
from remi.application.core.rules import normalize_entity_name
from remi.application.ingestion.models import IngestionResult
from remi.application.ingestion.operations import run_deterministic_pipeline
from remi.application.ingestion.rules import (
    is_junk_property,
    is_manager_tag,
    normalize_address,
    property_name,
    resolve_manager_from_metadata,
)
from remi.types.identity import manager_id as _manager_id
from remi.types.identity import property_id as _property_id

_log = structlog.get_logger(__name__)


class IngestionToolProvider(ToolProvider):
    """Registers ingestion tools on the global agent tool registry."""

    def __init__(
        self,
        content_store: ContentStore,
        property_store: PropertyStore,
        event_bus: EventBus,
        format_registry: FormatRegistry | None = None,
    ) -> None:
        self._cs = content_store
        self._ps = property_store
        self._event_bus = event_bus
        self._format_registry = format_registry

    def register(self, registry: ToolRegistry) -> None:
        cs = self._cs
        ps = self._ps
        event_bus = self._event_bus

        # -- ingest_analyze ----------------------------------------------------

        async def ingest_analyze(args: dict[str, Any]) -> Any:
            doc_id = args.get("document_id", "")
            if not doc_id:
                return {"error": "document_id is required"}

            content = await cs.get(doc_id)
            if content is None:
                return {"error": f"Document {doc_id} not found in content store"}

            meta = content.metadata or {}
            manager_name, scope = resolve_manager_from_metadata(meta)

            return {
                "document_id": doc_id,
                "filename": content.filename,
                "row_count": content.row_count,
                "columns": content.column_names,
                "metadata": meta,
                "resolved_manager": manager_name,
                "resolved_scope": scope,
                "sample_rows": content.rows[:5],
            }

        registry.register(
            "ingest_analyze",
            ingest_analyze,
            ToolDefinition(
                name="ingest_analyze",
                description=(
                    "Analyze an uploaded document for ingestion. Returns column "
                    "headers, metadata, and 5 sample rows. Use this to understand "
                    "the document structure before building your column_map."
                ),
                args=[
                    ToolArg(
                        name="document_id",
                        description="ID of the uploaded document to analyze",
                        required=True,
                    ),
                ],
            ),
        )

        # -- ingest_format_lookup -----------------------------------------------

        fmt_registry = self._format_registry

        async def ingest_format_lookup(args: dict[str, Any]) -> Any:
            if fmt_registry is None:
                return {"match": False, "reason": "format registry not configured"}

            doc_id = args.get("document_id", "")
            manager_id_arg = args.get("manager_id", "")
            report_type_arg = args.get("report_type", "")

            if not manager_id_arg:
                resolved_mgr = args.get("resolved_manager", "")
                if resolved_mgr:
                    manager_id_arg = _manager_id(manager_name_from_tag(resolved_mgr))

            if not doc_id:
                return {"error": "document_id is required"}

            content = await cs.get(doc_id)
            if content is None:
                return {"error": f"Document {doc_id} not found"}

            col_sig = column_signature(content.column_names)

            def _format_hit(fmt: IngestionFormat, *, exact: bool = True) -> dict[str, Any]:
                return {
                    "match": True,
                    "exact": exact,
                    "format_id": fmt.id,
                    "column_map": fmt.column_map,
                    "primary_entity_type": fmt.primary_entity_type,
                    "scope": fmt.scope,
                    "platform": fmt.platform,
                    "report_type": fmt.report_type,
                    "manager_id": fmt.manager_id,
                    "use_count": fmt.use_count,
                    "confirmed_by_human": fmt.confirmed_by_human,
                }

            # Exact match: same manager + report_type + column shape.
            # Human-confirmed preferred; auto-saved from a previous successful
            # run is also valid — no human gate for autonomous operation.
            if manager_id_arg and report_type_arg:
                exact = await fmt_registry.lookup(
                    manager_id=manager_id_arg,
                    report_type=report_type_arg,
                    col_sig=col_sig,
                )
                if exact is not None:
                    await fmt_registry.record_use(exact.id)
                    return _format_hit(exact, exact=True)

            # Signature-only match: same column shape, any manager/type.
            # Prefer human-confirmed, then most-used auto-saved.
            by_sig = await fmt_registry.lookup_by_signature(col_sig)
            if by_sig:
                best = max(by_sig, key=lambda f: (f.confirmed_by_human, f.use_count))
                await fmt_registry.record_use(best.id)
                return _format_hit(best, exact=False)

            return {
                "match": False,
                "column_signature": col_sig,
                "columns": content.column_names,
            }

        registry.register(
            "ingest_format_lookup",
            ingest_format_lookup,
            ToolDefinition(
                name="ingest_format_lookup",
                description=(
                    "Check if a known column mapping exists for this document's format. "
                    "Returns a match when the same column shape was successfully ingested "
                    "before. Use the stored column_map directly — no LLM reasoning needed. "
                    "Call this after ingest_analyze with the manager_id and report_type "
                    "you identified from metadata."
                ),
                args=[
                    ToolArg(
                        name="document_id",
                        description="ID of the document to look up",
                        required=True,
                    ),
                    ToolArg(
                        name="manager_id",
                        description="Manager ID if known (for exact match)",
                    ),
                    ToolArg(
                        name="report_type",
                        description="Report type if known (for exact match)",
                    ),
                ],
            ),
        )

        # -- ingest_format_save ------------------------------------------------

        async def ingest_format_save(args: dict[str, Any]) -> Any:
            if fmt_registry is None:
                return {"error": "format registry not configured"}

            doc_id = args.get("document_id", "")
            manager_id_arg = args.get("manager_id", "")
            report_type_arg = args.get("report_type", "")

            if not manager_id_arg:
                resolved_mgr = args.get("resolved_manager", "")
                if resolved_mgr:
                    manager_id_arg = _manager_id(manager_name_from_tag(resolved_mgr))
            col_map = args.get("column_map")
            entity_type = args.get("primary_entity_type", "")
            confirmed = args.get("confirmed_by_human", False)

            if not all([doc_id, manager_id_arg, report_type_arg, col_map, entity_type]):
                return {"error": "document_id, manager_id, report_type, column_map, and primary_entity_type are required"}

            if isinstance(col_map, str):
                try:
                    col_map = json.loads(col_map)
                except json.JSONDecodeError:
                    return {"error": "column_map must be valid JSON"}

            content = await cs.get(doc_id)
            if content is None:
                return {"error": f"Document {doc_id} not found"}

            col_sig = column_signature(content.column_names)
            fid = format_id(manager_id_arg, report_type_arg, col_sig)

            fmt = IngestionFormat(
                id=fid,
                manager_id=manager_id_arg,
                report_type=report_type_arg,
                column_signature=col_sig,
                column_map=col_map,
                primary_entity_type=entity_type,
                scope=args.get("scope", "unknown"),
                platform=args.get("platform", "appfolio"),
                confirmed_by_human=bool(confirmed),
            )
            saved = await fmt_registry.save(fmt)
            _log.info(
                "format_saved",
                format_id=fid,
                manager_id=manager_id_arg,
                report_type=report_type_arg,
                confirmed=confirmed,
            )
            return {
                "format_id": saved.id,
                "status": "saved",
                "confirmed_by_human": saved.confirmed_by_human,
            }

        registry.register(
            "ingest_format_save",
            ingest_format_save,
            ToolDefinition(
                name="ingest_format_save",
                description=(
                    "Save a confirmed column mapping to the format registry. "
                    "Call this after a successful ingest_run when the human has "
                    "confirmed the mapping. Future uploads with the same column "
                    "shape will use this mapping automatically."
                ),
                args=[
                    ToolArg(
                        name="document_id",
                        description="ID of the document whose format to save",
                        required=True,
                    ),
                    ToolArg(
                        name="manager_id",
                        description="Manager ID this format belongs to",
                        required=True,
                    ),
                    ToolArg(
                        name="report_type",
                        description="Report type (e.g. rent_roll, delinquency)",
                        required=True,
                    ),
                    ToolArg(
                        name="column_map",
                        description="The confirmed column_map (header→field mapping)",
                        required=True,
                        type="object",
                    ),
                    ToolArg(
                        name="primary_entity_type",
                        description="Primary entity type (e.g. Unit, Tenant, Lease)",
                        required=True,
                    ),
                    ToolArg(
                        name="confirmed_by_human",
                        description="Whether a human confirmed this mapping",
                        type="boolean",
                    ),
                    ToolArg(
                        name="scope",
                        description="Report scope (manager_portfolio, portfolio_wide, etc.)",
                    ),
                    ToolArg(
                        name="platform",
                        description="Platform (appfolio, yardi, etc.)",
                    ),
                ],
            ),
        )

        # -- ingest_preview ----------------------------------------------------

        async def ingest_preview(args: dict[str, Any]) -> Any:
            """Dry-run the pipeline — map and validate without persisting."""
            doc_id = args.get("document_id", "")
            if not doc_id:
                return {"error": "document_id is required"}

            extract_data = args.get("extract_data")
            if not extract_data:
                return {"error": "extract_data is required"}

            if isinstance(extract_data, str):
                try:
                    extract_data = json.loads(extract_data)
                except json.JSONDecodeError:
                    return {"error": "extract_data must be valid JSON"}

            content = await cs.get(doc_id)
            if content is None:
                return {"error": f"Document {doc_id} not found"}

            from remi.application.ingestion.operations import apply_column_map, validate_rows

            column_map: dict[str, str] = extract_data.get("column_map", {})
            entity_type: str = extract_data.get("primary_entity_type", "")
            section_header: str | None = extract_data.get("section_header_column")

            mapped = apply_column_map(
                content.rows, column_map, entity_type,
                section_header_column=section_header,
            )

            result = IngestionResult(document_id=doc_id, report_type=ReportType.UNKNOWN)
            accepted = validate_rows(mapped, result)

            entity_types: dict[str, int] = {}
            properties: set[str] = set()
            for row in accepted:
                rt = row.get("type", "unknown")
                entity_types[rt] = entity_types.get(rt, 0) + 1
                addr = row.get("property_address", "")
                if addr:
                    properties.add(addr)

            return {
                "preview": True,
                "total_rows": len(content.rows),
                "mapped_rows": len(mapped),
                "accepted_rows": len(accepted),
                "rejected_rows": result.rows_rejected,
                "skipped_rows": result.rows_skipped,
                "entity_types": entity_types,
                "unique_properties": len(properties),
                "property_addresses": sorted(properties)[:20],
                "validation_warnings": [
                    f"row {w.row_index} ({w.row_type}).{w.field}: {w.issue}"
                    for w in result.validation_warnings[:10]
                ],
                "sample_mapped": [
                    {k: v for k, v in row.items() if not k.startswith("_")}
                    for row in accepted[:3]
                ],
            }

        registry.register(
            "ingest_preview",
            ingest_preview,
            ToolDefinition(
                name="ingest_preview",
                description=(
                    "Dry-run the ingestion pipeline: map columns and validate rows "
                    "without persisting anything. Returns a preview summary with "
                    "entity counts, property addresses, and sample mapped rows. "
                    "Use this to show the user what will be ingested before committing."
                ),
                args=[
                    ToolArg(
                        name="document_id",
                        description="ID of the document to preview",
                        required=True,
                    ),
                    ToolArg(
                        name="extract_data",
                        description=(
                            "JSON object with: report_type, primary_entity_type, "
                            "column_map (header→field), and optionally section_header_column"
                        ),
                        required=True,
                        type="object",
                    ),
                ],
            ),
        )

        # -- ingest_run --------------------------------------------------------

        async def ingest_run(args: dict[str, Any]) -> Any:
            doc_id = args.get("document_id", "")
            if not doc_id:
                return {"error": "document_id is required"}

            extract_data = args.get("extract_data")

            if isinstance(extract_data, str):
                try:
                    extract_data = json.loads(extract_data)
                except json.JSONDecodeError:
                    return {"error": "extract_data must be valid JSON"}

            if not extract_data:
                extract_data = {
                    k: args[k]
                    for k in (
                        "report_type", "primary_entity_type", "column_map",
                        "platform", "manager", "scope", "section_header_column",
                    )
                    if k in args
                }
            if not extract_data.get("column_map"):
                return {"error": "column_map is required (via extract_data or flat args)"}

            content = await cs.get(doc_id)
            if content is None:
                return {"error": f"Document {doc_id} not found in content store"}

            meta = content.metadata or {}
            resolved_mgr, resolved_scope = resolve_manager_from_metadata(meta)
            extract_data["manager"] = resolved_mgr
            extract_data["scope"] = resolved_scope

            result = IngestionResult(document_id=doc_id, report_type=ReportType.UNKNOWN)

            try:
                await run_deterministic_pipeline(
                    ps=ps,
                    doc_id=doc_id,
                    platform=extract_data.get("platform", "appfolio"),
                    result=result,
                    all_rows=content.rows,
                    extract_data=extract_data,
                )
            except Exception:
                _log.warning(
                    "ingest_run_failed", doc_id=doc_id, exc_info=True,
                )
                return {
                    "error": "Pipeline execution failed",
                    "entities_created": result.entities_created,
                    "rows_accepted": result.rows_accepted,
                    "rows_rejected": result.rows_rejected,
                }

            return {
                "entities_created": result.entities_created,
                "relationships_created": result.relationships_created,
                "rows_accepted": result.rows_accepted,
                "rows_rejected": result.rows_rejected,
                "rows_skipped": result.rows_skipped,
                "validation_warnings": [
                    f"row {w.row_index} ({w.row_type}).{w.field}: {w.issue}"
                    for w in result.validation_warnings
                ],
            }

        registry.register(
            "ingest_run",
            ingest_run,
            ToolDefinition(
                name="ingest_run",
                description=(
                    "Run the deterministic ingestion pipeline on a document. "
                    "Requires extract_data with report_type, primary_entity_type, "
                    "column_map, and optionally manager, scope, section_header_column. "
                    "Maps columns, validates rows, and persists entities."
                ),
                args=[
                    ToolArg(
                        name="document_id",
                        description="ID of the document to ingest",
                        required=True,
                    ),
                    ToolArg(
                        name="extract_data",
                        description=(
                            "JSON object with: report_type, primary_entity_type, "
                            "column_map (header→field), platform, manager (name or null), "
                            "scope (portfolio_wide/manager_portfolio/etc.), "
                            "section_header_column (or null)"
                        ),
                        required=True,
                        type="object",
                    ),
                ],
            ),
        )

        # -- ingest_resolve ----------------------------------------------------

        async def ingest_resolve(args: dict[str, Any]) -> Any:
            """Resolve property addresses and manager tags against the existing store."""
            doc_id = args.get("document_id", "")
            if not doc_id:
                return {"error": "document_id is required"}

            content = await cs.get(doc_id)
            if content is None:
                return {"error": f"Document {doc_id} not found"}

            column_map: dict[str, str] = args.get("column_map") or {}

            # Identify which raw column carries property addresses / manager tags.
            addr_col = next(
                (col for col, field in column_map.items() if field == "property_address"),
                None,
            )
            tag_cols = [
                col for col, field in column_map.items()
                if field in ("_manager_tag", "name", "site_manager_name")
            ]

            # Collect unique addresses and manager tags from rows.
            raw_addresses: dict[str, int] = {}
            raw_tags: dict[str, int] = {}

            for row in content.rows:
                addr = ""
                if addr_col:
                    addr = str(row.get(addr_col) or "").strip()
                if not addr:
                    for k, v in row.items():
                        if any(x in k.lower() for x in ("property", "address", "addr")):
                            candidate = str(v or "").strip()
                            if candidate:
                                addr = candidate
                                break

                if addr and not is_junk_property(addr.lower()):
                    norm = normalize_address(addr)
                    raw_addresses[norm] = raw_addresses.get(norm, 0) + 1

                for tc in tag_cols:
                    tag = str(row.get(tc) or "").strip()
                    if tag:
                        raw_tags[tag] = raw_tags.get(tag, 0) + 1

            all_props = await ps.list_properties()
            prop_by_id = {p.id: p for p in all_props}
            all_managers = await ps.list_managers()
            mgr_by_id = {m.id: m for m in all_managers}
            mgr_by_norm = {normalize_entity_name(m.name): m for m in all_managers}

            # Resolve property addresses.
            known_properties = []
            unknown_properties = []

            for raw_addr, count in sorted(raw_addresses.items()):
                name = property_name(raw_addr)
                pid = _property_id(name or raw_addr)
                if pid in prop_by_id:
                    prop = prop_by_id[pid]
                    known_properties.append({
                        "raw_address": raw_addr,
                        "property_id": prop.id,
                        "property_name": prop.name,
                        "manager_id": prop.manager_id,
                        "manager_name": mgr_by_id[prop.manager_id].name
                            if prop.manager_id and prop.manager_id in mgr_by_id else None,
                        "row_count": count,
                    })
                else:
                    unknown_properties.append({"raw_address": raw_addr, "row_count": count})

            # Resolve manager tags.
            known_managers = []
            unknown_tags = []

            for raw_tag, count in sorted(raw_tags.items()):
                parts = [p.strip() for p in raw_tag.split(",") if p.strip()]
                primary = parts[0] if parts else raw_tag
                if not is_manager_tag(primary):
                    continue
                display = manager_name_from_tag(primary)
                mid = _manager_id(display)
                if mid in mgr_by_id:
                    known_managers.append({
                        "raw_tag": raw_tag,
                        "manager_id": mgr_by_id[mid].id,
                        "manager_name": mgr_by_id[mid].name,
                        "match_type": "exact",
                        "row_count": count,
                    })
                else:
                    norm = normalize_entity_name(primary)
                    fuzzy = mgr_by_norm.get(norm)
                    if fuzzy:
                        known_managers.append({
                            "raw_tag": raw_tag,
                            "manager_id": fuzzy.id,
                            "manager_name": fuzzy.name,
                            "match_type": "normalized",
                            "row_count": count,
                        })
                    else:
                        unknown_tags.append({"raw_tag": raw_tag, "row_count": count})

            total = len(known_properties) + len(unknown_properties)
            summary_parts: list[str] = [
                f"{len(known_properties)}/{total} addresses match existing properties"
            ]
            if unknown_properties:
                examples = ", ".join(p["raw_address"] for p in unknown_properties[:3])
                summary_parts.append(f"{len(unknown_properties)} new: {examples}")
            if known_managers:
                names = ", ".join(m["manager_name"] for m in known_managers[:3])
                summary_parts.append(f"Managers: {names}")
            elif unknown_tags:
                examples = ", ".join(t["raw_tag"] for t in unknown_tags[:3])
                summary_parts.append(f"Unmatched tags: {examples}")
            else:
                summary_parts.append("No manager tags found in document")

            return {
                "known_properties": known_properties,
                "unknown_properties": unknown_properties,
                "known_managers": known_managers,
                "unknown_manager_tags": unknown_tags,
                "summary": ". ".join(summary_parts) + ".",
            }

        registry.register(
            "ingest_resolve",
            ingest_resolve,
            ToolDefinition(
                name="ingest_resolve",
                description=(
                    "Resolve property addresses and manager tags from a document against "
                    "the existing property store. Call this after ingest_analyze (and after "
                    "building a column_map if one is available) to see which properties and "
                    "managers are already known vs new before running ingest_run. "
                    "Returns known_properties, unknown_properties, known_managers, "
                    "unknown_manager_tags, and a summary string."
                ),
                args=[
                    ToolArg(
                        name="document_id",
                        description="ID of the document to resolve",
                        required=True,
                    ),
                    ToolArg(
                        name="column_map",
                        description=(
                            "Column map (header→field) from format_lookup or your own mapping. "
                            "Used to identify the property_address and manager tag columns. "
                            "If omitted, a heuristic column scan is used."
                        ),
                        type="object",
                    ),
                ],
            ),
        )

        # -- ingest_finalize ---------------------------------------------------

        async def ingest_finalize(args: dict[str, Any]) -> Any:
            doc_id = args.get("document_id", "")
            if not doc_id:
                return {"error": "document_id is required"}

            report_type_str = args.get("report_type", "unknown")
            manager_name = args.get("manager") or args.get("resolved_manager")
            entities_created = int(args.get("entities_created", 0))
            rows_accepted = int(args.get("rows_accepted", 0))
            rows_rejected = int(args.get("rows_rejected", 0))

            try:
                rt = ReportType(report_type_str)
            except ValueError:
                rt = ReportType.UNKNOWN

            doc_manager_id: str | None = None
            if manager_name:
                display = manager_name_from_tag(manager_name)
                mid = _manager_id(display)
                if await ps.get_manager(mid) is None:
                    await ps.upsert_manager(PropertyManager(id=mid, name=display))
                doc_manager_id = mid

            doc = await ps.get_document(doc_id)
            if doc is not None:
                updated = doc.model_copy(
                    update={
                        "report_type": rt,
                        "manager_id": doc_manager_id,
                        "report_manager": manager_name,
                    }
                )
                await ps.upsert_document(updated)

            try:
                await event_bus.publish(
                    DomainEvent(
                        topic="ingestion.complete",
                        source="ingestion.agent",
                        payload={
                            "document_id": doc_id,
                            "report_type": rt.value,
                            "entities_extracted": entities_created,
                            "rows_accepted": rows_accepted,
                            "rows_rejected": rows_rejected,
                            "graph_changed": entities_created > 0,
                        },
                    )
                )
            except Exception:
                _log.warning("event_publish_failed", topic="ingestion.complete", exc_info=True)

            return {
                "document_id": doc_id,
                "report_type": rt.value,
                "manager_id": doc_manager_id,
                "status": "complete",
            }

        registry.register(
            "ingest_finalize",
            ingest_finalize,
            ToolDefinition(
                name="ingest_finalize",
                description=(
                    "Finalize document ingestion: update the document record with "
                    "report type and manager, then publish the ingestion.complete event. "
                    "Call this after ingest_run succeeds."
                ),
                args=[
                    ToolArg(
                        name="document_id",
                        description="ID of the document to finalize",
                        required=True,
                    ),
                    ToolArg(
                        name="report_type",
                        description="Classified report type (e.g. rent_roll, delinquency)",
                        required=True,
                    ),
                    ToolArg(
                        name="manager",
                        description="Manager name if identified from document metadata",
                    ),
                    ToolArg(
                        name="entities_created",
                        description="Count of entities created by ingest_run",
                        type="integer",
                    ),
                    ToolArg(
                        name="rows_accepted",
                        description="Count of rows accepted by ingest_run",
                        type="integer",
                    ),
                    ToolArg(
                        name="rows_rejected",
                        description="Count of rows rejected by ingest_run",
                        type="integer",
                    ),
                ],
            ),
        )
