# Plan 1 - Nen tang chat CIVI

## Muc tieu

Khoi tao MVP chat theo phien voi React/Vite, FastAPI, LangGraph, Redis va
PostgreSQL. MVP dung UI CIVI de nguoi dung bat dau hoi dap, nhung chua co RAG,
du lieu thu tuc, form, validation hay PDF export.

## Quyet dinh ky thuat

- Frontend duoc build thu cong bang `npm run build` thanh `fe/dist`.
- `be/docker-compose.yml` chay backend FastAPI, PostgreSQL 16 co pgvector va
  Redis 7.
- Nginx phuc vu static files, proxy `/api` va `/health` toi backend; development
  chua dung TLS.
- Backend dat cookie phien HttpOnly, SameSite Lax; Redis luu history, ngon ngu
  va intent trong 30 phut.
- LangGraph chi dieu phoi guard, xu ly intent/phan hoi LLM va luu state; khong
  co tool call, RAG hay citation.
- LLM su dung endpoint OpenAI-compatible qua bien moi truong. Khi thieu cau
  hinh hoac provider loi, backend tra mock response an toan.
- Backend dung `be/.env`; PostgreSQL dung `be/.db.env`; frontend dung
  `fe/.env` khi build static files.
- Nginx chay tren host, phuc vu `icivi.online` tu `/var/www/icivi.online` va
  proxy API toi `127.0.0.1:8000`.

## API MVP

- `GET /health`: kiem tra Redis va trang thai backend.
- `POST /api/v1/sessions`: tao hoac lam moi phien, chi dat cookie HttpOnly.
- `DELETE /api/v1/sessions/current`: xoa Redis state va cookie phien.
- `POST /api/v1/chat/stream`: nhan `message` va `language_code`; stream SSE
  `message.delta`, `message.complete` hoac `error`.

## Chay development

1. Tao `be/.env` tu `be/.env.example` va `be/.db.env` tu
   `be/.db.env.example`.
2. Tao `fe/.env` tu `fe/.env.example`, sau do chay `npm install` va
   `npm run build` trong `fe/`.
3. Chay `docker compose up --build` trong `be/` de khoi dong backend,
   PostgreSQL va Redis.
4. Cau hinh host Nginx voi `nginx/icivi.online.bootstrap.conf`, sau do cap
   Let's Encrypt certificate va kich hoat `nginx/icivi.online.conf`.

## Tieu chi nghiem thu

- Compose khoi dong Nginx, backend, PostgreSQL va Redis; PostgreSQL/Redis khong
  bind cong ra host.
- Frontend co man hinh chao, chips, chat streaming, quick replies, ngon ngu,
  reset phien va tab ra soat dang cho.
- Cookie khong co trong JavaScript response body; xoa phien xoa Redis state.
- Backend fallback mock van cho phep luong chat hoat dong khi chua cau hinh LLM.
- Test backend/frontend, type check, Compose config va Markdown lint deu pass.

## Trien khai Nginx

1. Tao DNS A record `icivi.online` tro toi `136.112.135.233`.
2. Copy static bundle toi `/var/www/icivi.online` tren server.
3. Dung bootstrap config de Certbot cap certificate cho `icivi.online`.
4. Kich hoat HTTPS config va dat `CORS_ORIGIN=https://icivi.online` cung
   `SESSION_COOKIE_SECURE=true` trong `be/.env`.
