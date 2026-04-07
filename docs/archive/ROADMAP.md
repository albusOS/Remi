# REMI Roadmap

## Current State

REMI operates as a director-level intelligence tool. The director uploads AppFolio report exports manually, REMI ingests them into the knowledge graph, runs the entailment engine to produce signals, and provides AI agents (director for Q&A, researcher for deep analysis) for investigation and action planning. One role, one portal, manual ingestion.

**What works today:**
- AppFolio report ingestion (property directory, rent roll, delinquency, lease expiration)
- Entailment engine producing 12 atomic signals + 3 compositions
- Director agent (fast Q&A with structured data tools)
- Researcher agent (deep statistical analysis with sandbox Python)
- REST API (17 route groups) + WebSocket (chat + events)
- Next.js frontend (dashboard, chat, delinquency, vacancies, leases, documents, performance, property/manager detail)
- Textual TUI dashboard
- Full CLI for ontology operations, traces, seeding, benchmarks

---

## Phase: RBAC & Property Manager Portal

**Prerequisite for email triage.** Before REMI can route tenant requests to individual property managers, managers need their own accounts and views.

- **Role-based access control** — Director, PropertyManager, (eventually Tenant)
- **Manager portal** — a PM sees only their portfolio: their properties, their signals, their maintenance queue, their tenant communications
- **Director retains admin-level view** — cross-portfolio, cross-manager oversight

This phase defines the routing targets that the email triage system needs.

---

## Phase: REMI Email — AI-Owned Mailbox

REMI gets its own email address (`remi@yourcompany.com`) — not as a narrow integration, but as an employee-grade mailbox. One address, one inbound endpoint, a classifier that grows over time.

### Architecture

```
remi@yourcompany.com
       │
       ▼
  /api/v1/email/inbound  (webhook from SendGrid / Mailgun / SES)
       │
       ▼
  EmailService.classify()  (LLM-backed, domain.yaml rules as context)
       │
       ├── appfolio_report    → extract attachment → DocumentIngestService
       ├── tenant_maintenance → resolve tenant → create MaintenanceRequest → triage
       ├── tenant_inquiry     → resolve tenant → log → draft response for PM review
       ├── manager_forward    → ingest as context → link to entities
       ├── director_query     → route to director agent (email as chat transport)
       └── unknown            → log + notify admin + learn
```

### Capabilities (in dependency order)

1. **Automated Report Ingestion** — Can build now, no new roles needed. AppFolio scheduled email reports → existing ingestion pipeline.
2. **Tenant Maintenance Triage** — Requires RBAC. Tenants email maintenance requests → classified, triaged, routed to PM queue.
3. **General Tenant Communication** — Requires RBAC. Lease inquiries, rent questions, move-out notices → drafted responses for PM review.
4. **Manager/Director Communication** — Requires RBAC. CC remi@ on conversations → knowledge graph observations. Director emails questions → agent via email transport.
5. **Confidence-Gated Auto-Response** — Requires trust data from capabilities 2-4. Graduated from PM-approved to auto-sent based on approval rates.

---

## Dependency Chain

```
Current state (director-only, manual upload)
    │
    ├── Email Capability 1: Report Ingestion ← can build now
    │
    ▼
RBAC + Property Manager Portal
    │
    ├── Email Capability 2: Maintenance Triage
    ├── Email Capability 3: Tenant Communication
    ├── Email Capability 4: Manager/Director Email
    │
    ▼
Email Capability 5: Auto-Response
```
