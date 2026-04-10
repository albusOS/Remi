# REMI Frontend

## Stack
Next.js 16 (App Router) · React 19 · Tailwind 4 · TanStack Query 5 · Recharts 3

## Architecture

### Three-layer model
1. **Primitives** — reusable visual components in `src/components/ui/`
2. **Static surfaces** — pages and views that consume primitives, no AI cost
3. **AI-generated UI** — agent returns ephemeral components via `ToolResultCard`, using the same primitives

### Routes
```
/                → Ask REMI (AI agent — the product home)
/managers        → Manager list + portfolio summary
/managers/[id]   → Manager detail (Overview · Rent Roll · Leases · Trends · Meeting Prep)
/properties      → Property list + portfolio summary
/properties/[id] → Property detail (Rent Roll · Leases · Maintenance · Activity · Notes)
/properties/[id]/units/[unitId] → Unit detail
/documents       → Document management
```

## Visualization Rules

### Tables are forbidden except for
- Rent roll (unit-by-unit line items)
- Lease lists (individual lease records)
- Maintenance work orders
- Document records

**Everything else uses visual components.** No flat tables for entity lists, portfolio summaries, or overviews.

### Primitive library — always use these, never inline

| Component | Use for |
|---|---|
| `HealthRing` | Occupancy rate — SVG donut, always visual |
| `StatHero` | Prominent single metric with supporting stats |
| `PipelineStrip` | Sequential stage visualization (collections, etc.) |
| `TimelineBuckets` | Time-bucketed bar viz (lease expirations) |
| `AlertFeed` | Actionable signal list |
| `ManagerHealthCard` | Manager entity card |
| `PropertyHealthCard` | Property entity card |

### Data binding rules
- **Never recalculate metrics the API already computes.** Use `data.occupancy_rate`, `data.occupied`, `data.total_units` directly from the response — do not re-derive them from sub-arrays.
- `useApiQuery` deps array must include a **semantic string key** as the first element to prevent cache collisions: `["managers_list"]`, `["properties_list", managerId]`, `["manager_detail", managerId]`, etc.

## Layout Patterns

### List pages (`/managers`, `/properties`)
- `HealthRing` portfolio summary at top — uses API-level aggregate values
- `PropertyHealthCard` / `ManagerHealthCard` grid below
- **Empty state shows the structural skeleton** (dashed placeholder cards), never an error message

### Detail pages
- Breadcrumb back to list
- Tabbed layout — tabs lazy-render (only mount on selection)
- "Ask REMI" deep-link button in header (links to `/?q=...`)

### Empty states
Show the framework structure, not absence. Dashed placeholder cards communicate what will live there once data is ingested.

## Query Cache Keys

Every `useApiQuery` call must have a unique semantic key:

```ts
useApiQuery(fn, ["managers_list"])
useApiQuery(fn, ["properties_list", managerId])
useApiQuery(fn, ["manager_detail", managerId])
useApiQuery(fn, ["manager_rent_roll", managerId])
useApiQuery(fn, ["manager_leases_full", managerId])
useApiQuery(fn, ["director_surface"])
```

Sharing keys across components causes cache collisions and type errors at runtime.
