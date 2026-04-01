# REMI Frontend

Next.js 16 dashboard for REMI. Connects to the Python API server at `http://localhost:8000`.

## Stack

- **Next.js 16.2** with App Router
- **React 19.2**
- **Tailwind CSS 4**
- **Framer Motion** for animations
- **react-markdown** + **remark-gfm** for rendering agent responses

## Setup

```bash
npm install
npm run dev    # http://localhost:3000
```

Requires the API server running (`uv run remi serve --seed` from the project root).

## Pages

| Route | Description |
|-------|-------------|
| `/` | Home |
| `/dashboard` | Director dashboard — signals overview, portfolio health |
| `/ask` | Chat interface — director and researcher agents |
| `/delinquency` | Delinquency analysis and tracking |
| `/vacancies` | Vacancy monitoring |
| `/leases` | Lease expiration analysis |
| `/documents` | Document upload and management |
| `/performance` | Manager performance comparison |
| `/properties/[id]` | Property detail — units, rent roll, metrics |
| `/managers/[id]` | Manager detail — portfolio, signals, review |

## Structure

```
src/
  app/
    (shell)/           Shell layout with sidebar navigation
      layout.tsx       Shell layout
      page.tsx         Home
      dashboard/       Director dashboard
      ask/             Chat interface
      delinquency/     Delinquency view
      vacancies/       Vacancy view
      leases/          Lease view
      documents/       Document management
      performance/     Performance comparison
      properties/[id]/ Property detail
      managers/[id]/   Manager detail
    layout.tsx         Root layout
    not-found.tsx      404 page
  components/
    Shell.tsx          App shell with sidebar
    ui/                Shared UI components (MetricStrip, MetricCard, DataTable, PageContainer, Markdown, etc.)
    ask/               Chat components (AskView, SessionInput, SessionThread, SessionSidebar, etc.)
    dashboard/         Dashboard components
    delinquency/       Delinquency components
    documents/         Document components
    leases/            Lease components
    managers/          Manager components
    performance/       Performance components
    properties/        Property components
    vacancies/         Vacancy components
  hooks/
    useApiQuery.ts     Data fetching hook
    useAppOSEvents.ts  WebSocket event hook
    useSessions.ts     Chat session management
  lib/
    api.ts             API client
    format.ts          Formatting utilities
    types.ts           TypeScript types
```
