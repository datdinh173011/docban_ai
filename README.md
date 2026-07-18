# ICIVI

ICIVI is an AI chatbot that helps Vietnamese citizens understand and prepare for
administrative procedures using natural language. It is **not** a government
service portal and does not submit applications on the user's behalf. It is a
support layer that sits *before* submission, helping people get it right.

## Production

Use ICIVI at [https://icivi.online/](https://icivi.online/).

## Problem it solves

When dealing with administrative procedures, citizens commonly struggle with:

- Not knowing which procedure applies to their situation.
- Not knowing which documents or forms they need to prepare.
- Not understanding how to fill in specific fields on a form.
- Missing errors, wrong formats, or contradictions before submitting.
- Dense legal/administrative language that's hard to parse.
- Additional language barriers for ethnic minority language speakers.

ICIVI reduces how often people need to search multiple sources or visit an
office in person just to ask a question.

## Key features (Version 1 scope)

- **Public, session-based chat** — no login or account required. Each visit
  creates an anonymous `chat_session` that expires after 30 minutes of
  inactivity or is deleted on request. No long-term memory exists across
  sessions.
- **Procedure & form identification** — users describe their needs in natural
  language; the chatbot identifies a matching procedure or form and asks
  clarifying questions when needed.
- **Procedure Q&A** — answers questions about eligibility, documents,
  submission, time, and fees with cited sources.
- **Guided form filling** — field-by-field explanations include meaning, who
  fills the field, expected format, requirement status, and an example.
- **Pre-submission validation** — reports use `blocking_error`, `warning`,
  `suggestion`, or `unable_to_verify`. Configured schema and rules perform the
  deterministic checks; an AI second pass adds further findings on top (never
  dropping or overriding a rule result) to catch issues fixed rules can't
  express, such as an implausible name or address.
- **PDF export with preview** — V1 supports three standardized published
  forms (birth registration, permanent residence, construction permit). Users
  confirm dynamic-form data before export, can preview the exact generated
  PDF in-browser before downloading it, and files stream for download and are
  never persisted.
- **Multilingual UI** — Vietnamese, English, Hmong Daw, and Khmer are live
  today across the chat, form, and legal pages, with an architecture that
  supports adding further languages.
- **Terms & Privacy page** — a dedicated `/privacy` page with the platform's
  terms of use and privacy policy, reachable from the header and translated
  into all supported languages.

## Out of scope for Version 1

- User accounts, login, or profile management.
- VNeID authentication or population database integration.
- Automatic retrieval of personal data.
- Long-term storage of application data across sessions.
- Direct submission of applications to government portals.
- Fee payment or digital signatures.
- Tracking application processing status.
- PDF export for forms without a published template/field mapping.

## Architecture overview

Version 1 is designed to run entirely on an internal LAN server via Docker Compose

```text
Public Chat UI
      |
      v
Session API
      |
      v
Conversation Orchestrator (LangGraph)
      |
      +--> Intent & Procedure Selection
      +--> Guided Intake
      +--> Legal and Procedure RAG
      +--> Form Guidance Service
      +--> Application Validation Engine
      +--> Form PDF Export Service
      |
      v
Response Generator
```

### Tech stack

| Layer | Technology | Role |
|---|---|---|
| Frontend | React + TypeScript + Vite | Chat UI, forms, and guidance |
| Backend | FastAPI + Python 3.12 | API, sessions, and orchestration |
| Workflow | LangGraph | Conversation state orchestration |
| PDF export | ReportLab + pypdf | Unicode overlay and PDF merge |
| Session/cache | Redis | TTL, cache, rate limits, and stream state |
| Application data | PostgreSQL | Procedures, forms, and metadata |
| Vector retrieval | pgvector (in PostgreSQL) | Semantic search for RAG |
| File storage | Local filesystem | PDFs, DOCX, source JSON, processed files |
| Reverse proxy | Nginx or Caddy | HTTPS, routing, and request limits |
| LLM | Local model or external API | NLU and structured explanations |
| Container runtime | Docker Compose | Runs components on one machine |

### Key architectural principles

- **Deterministic rules are always authoritative and never overridden.** The
  Validation Engine's schema-driven checks run first and are never dropped or
  replaced. An AI pass adds further, equally-weighted findings on top —
  including issues that can block PDF export — but every AI-origin issue is
  tagged for traceability, and the AI pass degrades cleanly to rule-only
  results if the LLM is unavailable.
- **Schema-driven, not form-specific.** Each form is configuration with fields,
  requirements, instructions, examples, rules, and an effective version.
- **Session-based, no accounts.** Sessions are anonymous, expire after 30
  minutes of inactivity, and hold no persistent user identity.
- **Internal/LAN-first.** Only the reverse proxy is exposed; HTTPS/TLS is
  required whenever the system is reachable over LAN or a public URL.

## Repository structure

```text
be/       Backend and Docker Compose stack (FastAPI, Python 3.12)
fe/       Frontend (React + TypeScript + Vite)
nginx/    Reverse proxy configuration
docs/     Design and architecture documentation
  00-overview.md      Product scope, user flows, data groups
  01-architecture.md  Technical architecture, stack, deployment, ADRs
  02-schema.md        Detailed data/schema and validation rule design
  03-data-crawler.md  Source registry and data ingestion for the RAG base
  04-rag-pipeline.md  Retrieval pipeline design and confidence scoring
  05-scenario.md      Plain-language sample user flow walkthroughs
  06-whats-new.md     Latest shipped features: business value and tech notes
```

For full detail, read `docs/00-overview.md` for product scope,
`docs/01-architecture.md` for architecture, and `docs/06-whats-new.md` for
the latest shipped features.

## Getting started

The backend owns the Docker Compose stack in `be/docker-compose.yml`; frontend
builds and deployment remain in `fe/`. See `be/README.md` and `fe/README.md`
for service-specific setup and run instructions.
