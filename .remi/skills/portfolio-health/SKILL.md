---
name: portfolio-health
description: Complete portfolio health check — red flags, occupancy, delinquency, vacancies, lease risk, worst-performing managers.
tags: [portfolio, dashboard, health, overview]
scope: global
trigger: on_demand
required_capabilities: [bash]
---

# Portfolio Health Check

Use this when asked about overall portfolio status, problems, or
"what needs attention." No parameters needed — this is a full sweep.

## Knowledge

Red flags to surface (in priority order):
- Portfolio occupancy below 90%
- Any delinquent tenants with no active plan (especially balances > 1 month's rent)
- Vacant units (count + monthly rent at risk)
- Leases expiring in 150 days without milestone action (see lease-risk skill for thresholds)
- Month-to-month leases that need renewal conversation or rent adjustment
- Managers with significantly worse metrics than portfolio average

The director's lease review window starts at **150 days** — use that, not 90,
when scanning for upcoming lease risk. The 90-day threshold is when notices
must be sent, but the conversation with owners starts at 150 days.

Present red flags first, then overview numbers, then the
worst-performing managers. Give the director an immediate
sense of what needs attention and who to talk to.

## Commands

1. **Dashboard overview** — top-level portfolio metrics:

```bash
remi intelligence dashboard
```

2. **Delinquency board** — all delinquent tenants:

```bash
remi operations delinquency
```

3. **Vacancies** — all vacant units:

```bash
remi intelligence vacancies
```

4. **Expiring leases** — use the director's full 150-day window:

```
query(operation="expiring_leases", days="150")
```

5. **Rank managers** by worst delinquency rate:

```bash
remi portfolio rankings --sort-by delinquency_rate --limit 5
```
