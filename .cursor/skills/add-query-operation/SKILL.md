---
name: add-query-operation
description: Add a new read operation to the unified query tool. Use when you need to expose new data to the LLM agent via the query tool — e.g. a new aggregate view, a new filter, or a new entity type lookup.
---

# Adding a Query Operation

The `query` tool is the single read surface for the agent. All operations
dispatch through one tool call: `query(operation="<name>", ...)`.

**All new read operations go here — not in separate tools.**

## The file

```
src/remi/application/tools/query.py
```

## Step 1 — Add the operation name to `_OPERATIONS`

At the top of `query.py`, `_OPERATIONS` is a comma-separated string that
drives the tool description the LLM sees. Add your new operation name:

```python
_OPERATIONS = (
    "dashboard, managers, manager_review, properties, rent_roll, rankings, "
    "delinquency, expiring_leases, vacancies, leases, maintenance, "
    "search, delinquency_trend, occupancy_trend, rent_trend, maintenance_trend, "
    "ontology_schema, entity_graph, data_coverage, entity_detail, "
    "your_new_operation"   # ← add here
)
```

## Step 2 — Add the handler method

Add a method on `QueryToolProvider`. Follow the existing pattern:
- `async def _your_op(self, args: dict[str, Any]) -> dict[str, Any]:`
- Use `args.get("manager_id")` / `args.get("property_id")` for scoping
- If the operation takes a manager name, pass it through `_resolve_manager_id` first
- Return a `dict` — call `.model_dump(mode="json")` on Pydantic results

```python
async def _your_op(self, args: dict[str, Any]) -> dict[str, Any]:
    raw = args.get("manager_id")
    mid = await self._resolve_manager_id(raw) if raw else None
    result = await self._some_resolver.some_method(manager_id=mid)
    return result.model_dump(mode="json")
```

## Step 3 — Add it to the dispatch dict in `register()`

```python
dispatch = {
    # existing entries ...
    "your_new_operation": self._your_op,   # ← add here
}
```

## Step 4 — Add ToolArg entries if the operation needs new parameters

In `register()`, in the `ToolDefinition(args=[...])` block, add any parameters
that your handler uses:

```python
ToolArg(
    name="your_param",
    description="What this param does and when to use it",
),
```

Only add parameters that your operation actually reads. The LLM sees all `ToolArg`
entries as optional unless `required=True`.

## Step 5 — If group-by aggregation is needed, add it to `aggregators.py`

Group-by transforms belong in:
```
src/remi/application/tools/aggregators.py
```

Keep them pure — no I/O, no async, just data transformation on result models.
Import and call from `_your_op`:

```python
from remi.application.tools.aggregators import group_something_by_manager

async def _your_op(self, args: dict[str, Any]) -> dict[str, Any]:
    result = await self._resolver.get_data(...)
    if args.get("group_by") == "manager":
        return group_something_by_manager(result)
    return result.model_dump(mode="json")
```

## Step 6 — If a 360° view is needed, add to `detail.py`

For entity detail views (parallel store fetches):
```
src/remi/application/tools/detail.py
```

Add a `_detail_<entity>(self, entity_id, *, fields)` method on `EntityDetailHandler`
and add a dispatch case in `resolve()`.

## Where the resolver lives

Operations pull data through resolver classes, never directly from `PropertyStore`.
Resolvers are in:

```
src/remi/application/portfolio/managers.py     # ManagerResolver
src/remi/application/portfolio/properties.py   # PropertyResolver
src/remi/application/portfolio/rent_roll.py    # RentRollResolver
src/remi/application/portfolio/dashboard.py    # DashboardBuilder
src/remi/application/operations/leases.py      # LeaseResolver
src/remi/application/operations/delinquency.py # DelinquencyResolver
src/remi/application/operations/maintenance.py # MaintenanceResolver
src/remi/application/operations/vacancies.py   # VacancyResolver
src/remi/application/intelligence/trends.py    # TrendResolver
src/remi/application/intelligence/search.py    # SearchService
```

If your operation needs a new resolver, create it in the appropriate slice,
then inject it into `QueryToolProvider.__init__` and wire it in `container.py`.

## Injecting a new resolver into the container

If you add a new resolver, wire it in `src/remi/shell/config/container.py`:

```python
# In Container.__init__:
self.your_resolver = YourResolver(property_store=self.property_store)

# Then pass it to QueryToolProvider:
QueryToolProvider(
    ...existing args...,
    your_resolver=self.your_resolver,
)
```

`QueryToolProvider.__init__` stores it as `self._your = your_resolver`.

## No YAML changes needed

Adding an operation to `query.py` requires no YAML changes. The `query` tool
is registered once; the `operation` parameter selects the handler at runtime.

## Error handling

The dispatch wrapper in `register()` already catches exceptions:
```python
except Exception as exc:
    _log.warning("query_error", operation=operation, exc_info=True)
    return {"error": f"{operation} failed: {exc}"}
```

Your handler doesn't need to catch errors — just let them propagate.
The wrapper logs them and returns an error dict the LLM can read and respond to.

## Example — complete minimal operation

```python
# In _OPERATIONS string:
"my_new_op"

# In dispatch dict:
"my_new_op": self._my_new_op,

# Handler method:
async def _my_new_op(self, args: dict[str, Any]) -> dict[str, Any]:
    raw = args.get("manager_id")
    mid = await self._resolve_manager_id(raw) if raw else None
    items = await self._ps.list_something(manager_id=mid)
    return {"items": [i.model_dump(mode="json") for i in items]}

# ToolArg (inside ToolDefinition args=[...]):
ToolArg(
    name="manager_id",
    description="Filter by manager — name or slug both accepted",
),
```
