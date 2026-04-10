---
name: rent-roll
description: Rent roll analysis — owner names, management percentages, vacancy status, and commission verification. Sorted by unit status.
tags: [rent-roll, commissions, vacancies, owners, management-fee]
scope: entity
trigger: on_demand
required_capabilities: [query]
---

# Rent Roll Review

Use this when asked about the rent roll, commission sheets, owner names,
management percentages, unit statuses, or vacancy checking via rent roll.

## How the Director Uses the Rent Roll

The director built the rent roll with two primary use cases:

**1. Commission sheet verification**
The rent roll is the source of truth for checking commission sheets.
Key fields: **owner names** and **management percentage** (the management fee rate
charged per property). When reviewing commissions, surface these fields
prominently for each property.

**2. Vacancy checking**
The director sorts the rent roll by **status** to quickly identify vacant units.
When answering rent roll questions about vacancies, group or sort by status
so occupied, vacant, and notice-given units are clearly separated.

## Reports are pulled per property manager

The director always scopes rent roll pulls to a specific manager (by tag),
not combined across the whole portfolio. Scope queries by manager unless
explicitly asked for portfolio-wide.

## Key Fields

- **Owner name** — the property owner (not the PM)
- **Management percentage** — fee rate for this property
- **Unit status** — occupied / vacant / notice / month-to-month
- **Monthly rent** — scheduled rent for the unit
- **Tenant name** — current occupant (if any)

## Commands

1. **Pull rent roll for a property**:

```
query(operation="rent_roll", property_id="<id>")
```

2. **List properties for a manager** to find property IDs:

```
query(operation="properties", manager_id="<name or slug>")
```

3. **Pull vacancies** (faster than scanning rent roll for vacant units):

```
query(operation="vacancies", manager_id="<name or slug>")
```

## What to Report

- When checking commissions: surface owner name and management percentage for each unit/property
- When checking vacancies: group by status (vacant first, then notice-given, then occupied)
- Flag any units where management percentage looks anomalous vs other units in the same portfolio
- Month-to-month units appear on the rent roll — cross-reference with lease-risk review for follow-up
