---
name: lease-risk
description: Lease expiration and renewal pipeline — milestone-based review at 150/120/90/60 days, month-to-month management, and vacancy risk.
tags: [leases, vacancies, risk, revenue, renewals]
scope: entity
trigger: on_demand
required_capabilities: [query]
---

# Lease Risk Review

Use this when asked about lease expirations, renewal pipeline,
month-to-month leases, vacancy exposure, or revenue at risk.

## How the Director Reviews Lease Expirations

The director uses a **milestone-based framework**. Each distance threshold
has a specific expected action. When reviewing expiring leases, check
whether the PM has hit these milestones:

| Days to Expiry | What Should Be Happening |
|---|---|
| **≥ 150 days** | PM has started the conversation with the **owner** about renewal terms |
| **≥ 120 days** | PM has started the conversation with the **tenant** about renewal or non-renewal |
| **≥ 90 days** | Renewal or non-renewal notice has been **sent** |
| **60 days** | Director checks to know what's going on — awareness, not action threshold |

**A lease at 90 days without a sent notice is the critical failure state.**
Flag it. Surface who the PM is and what property is at risk.

## Month-to-Month Leases

Expired leases still active month-to-month require special attention.
These tenants can leave with 30 days notice. The director monitors whether:
- The PM should get them onto a yearly lease
- Their rent should be bumped (market conditions may have changed since signing)

When surfacing month-to-month leases, note how long they've been month-to-month
and flag any where rent may be significantly below current market.

## Revenue Risk Components

- **Expiring leases** — active leases ending in N days. Revenue at risk = sum of monthly rents
- **Current vacancies** — already empty units losing market rent daily
- **Month-to-month** — can leave on 30 days notice; treated as soft risk

Prioritize by highest rent at risk first.

## Commands

1. **Pull expiring leases** at the director's full 150-day horizon:

```
query(operation="expiring_leases", days="150")
```

Or scoped to a manager:

```
query(operation="expiring_leases", days="150", manager_id="<name or slug>")
```

2. **Pull current vacancies**:

```
query(operation="vacancies", manager_id="<name or slug>")
```

3. **Get the full lease list** to identify month-to-month leases:

```
query(operation="leases", property_id="<id>")
```

4. **Check occupancy trends** for context:

```
query(operation="occupancy_trend")
```

## What to Report

- Leases expiring within 150 days — grouped by milestone (≥150, ≥120, ≥90, ≥60)
- For each: PM name, property, tenant, expiry date, monthly rent, and whether a note/action exists
- **Flag at 90 days**: any lease without a sent renewal/non-renewal notice
- Month-to-month leases: how many, total rent at risk, how long overdue for renewal
- Current vacancies and market rent being lost
- Combined monthly revenue exposure across all categories
