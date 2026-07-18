# Plan 5 - Trusted Form PDF Source Registry And Crawler

## Muc tieu

Ingest bo PDF trong `docs/form_data/` thanh trusted V1 form corpus. Moi PDF co
source trust `operator_verified_primary`; catalog la inventory, bundle la cross
check va khong duoc publish nhu mot form rieng.

## Form corpus

- Primary forms: khai sinh, CT01 thuong tru va don cap phep xay dung nha o rieng
  le. Don xay dung chi trich section 4.4 nha o rieng le.
- Reference-support forms: cam doan viec sinh, xac nhan nguoi lam chung, dong y
  dang ky thuong tru va cam ket an toan cong trinh lien ke.
- High trust giu nguyen nhan primary/reference cua PDF; support form khong tu
  dong thanh giay to bat buoc.

## Implementation

- Tao `source_registry`, `form_template`, `form_version`, `form_section`,
  `form_field` va `form_conditional_document` trong PostgreSQL.
- Inspector luu checksum, page count, native text quality, source tier, parser
  profile, expected marker va form role; OCR chi la fallback khi native extract
  khong dat quality.
- Tao canonical field draft co provenance cho child/parent, CT01 household and
  repeated members, va detached-house construction details.
- Conditional document links luon `draft` cho den khi co legal rule publish.
- Khong build PDF fill/export mapping trong plan nay; export can visual mapping
  va review rieng.

## Quality va verify

```bash
cd be
uv run python -m app.form_cli --source-dir ../docs/form_data
uv run python -m app.form_cli --source-dir ../docs/form_data --import-db
uv run python -m app.form_cli --publish BIRTH_REGISTRATION_FORM
uv run pytest
docker compose run --rm --volume "$(pwd):/app" \
  --env DATABASE_URL=postgresql+asyncpg://icivi:icivi_dev_only@postgres:5432/\
icivi \
  backend uv run alembic upgrade head
```

- Test tat ca 9 PDF: page count, checksum, extraction quality, marker, trust
  tier va primary/reference role.
- Test field snapshots cho ba form chinh, bundle/catalog duplicate handling, va
  conditional document khong the tu dong tro thanh mandatory.
- Publish bi chan khi page/marker/scope sai, extraction can OCR, hoac source
  khong thuoc trusted corpus.
- Moi lan checksum thay doi se tao source va form-version `in_review` moi; ban
  da publish khong bi sua. External runtime search khong the import, embed hay
  publish bat ky PDF nao trong corpus nay.
