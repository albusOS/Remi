---
name: delinquency-review
description: Detailed delinquency analysis — delinquent tenants sorted by balance, plan status, and recommended actions. Includes director-level review standards.
tags: [delinquency, collections, tenants]
scope: entity
trigger: on_demand
required_capabilities: [query]
---

# Delinquency Review

Use this when asked about delinquent tenants, overdue rent, collections
status, or anything related to accounts receivable.

## How the Director Reviews Delinquency

Reports are always pulled **per property manager** (by tag), not combined.
The director sorts by **highest amount owed to lowest**.

**The critical threshold is one month's rent.** Any tenant owing more than
one month's rent must have an active plan in place. When reviewing:

1. Sort by balance descending
2. For every tenant over one month's rent — check if a delinquency note or
   action item exists. If not, flag it and recommend one.
3. Tenants under one month's rent are monitored but do not require escalation yet.

**Blue Door** is the largest client and has special delinquency reports
reviewed separately. When a Blue Door delinquency question comes up, note
that a dedicated review exists and ask whether the user wants to pull it.

## Key Metrics

- **Total delinquent count** — number of tenants with past-due balances
- **Total balance** — aggregate amount owed
- **0-30 day balance** — recent delinquency, may self-resolve
- **30+ day balance** — chronic delinquency, needs active management
- **Plan coverage** — % of high-balance tenants with an active note or action item

## Commands

1. **Get delinquency board sorted by balance** (scoped to a manager):

```
query(operation="delinquency", manager_id="<name or slug>")
```

Or portfolio-wide by property:

```
query(operation="delinquency", group_by="property")
```

2. **Get delinquency trends** to understand direction:

```
query(operation="delinquency_trend", manager_id="<name or slug>")
```

3. **Search for tenant context** if a note or plan is expected:

```
query(operation="search", query="<tenant name>")
```

4. **Create an action item** for tenants without a follow-up plan:

```
assert_fact(entity_type="action", properties={"title": "...", "manager_id": "...", "tenant_id": "...", "priority": "high"})
```

## What to Flag

- Tenants owing more than one month's rent with no action item or delinquency note → create or recommend one
- 30+ day balances that are growing (check trend)
- Blue Door properties — note that a separate detailed report exists
- Any tenant with a large balance and no recent note (stale plan)
