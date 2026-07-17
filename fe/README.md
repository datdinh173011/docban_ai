# ICIVI Frontend

## Requirements

- Node.js 22
- npm

## Configure Environment

Copy the build-time environment example:

```sh
cp .env.example .env
```

`VITE_API_BASE_URL=/api` keeps browser requests on the same public origin.
Do not put secrets in this file because Vite exposes `VITE_*` values in the
static bundle.

## Build Static Files

Install dependencies, run tests, and build the production bundle:

```sh
npm install
npm test
npm run build
```

Vite writes deployable files to `dist/`.

## Deploy To The Server

Build the frontend, then copy the contents of `dist/` to
`/var/www/icivi.online` on the target server:

```sh
npm ci
npm run build
sudo install -d -m 0755 /var/www/icivi.online
sudo cp -a dist/. /var/www/icivi.online/
```

The host Nginx vhost in `../nginx/icivi.online.conf` serves these files and
proxies `/api` to FastAPI on `127.0.0.1:8000`. Nginx runs directly on the host;
`../nginx/dev.conf` is only for Docker development.

For the initial HTTPS setup, install
`../nginx/icivi.online.bootstrap.conf` first. It serves the ACME challenge on
HTTP and redirects other traffic to HTTPS. After Certbot creates the
certificate, replace it with `../nginx/icivi.online.conf`, then validate and
reload Nginx:

```sh
sudo nginx -t
sudo systemctl reload nginx
```

Do not deploy `.env` because the frontend bundle already contains the required
public build-time values.
