# Plan 3 - RAG Vertical Slice Cho Dang Ky Khai Sinh

## Muc tieu

Hoan thien mot vertical slice cho dang ky khai sinh: nguon chinh phu da review
va publish, structured/hybrid retrieval, citation backend xac thuc, SSE/UI co
confidence band va fallback an toan. Day la dieu kien truoc khi mo rong sang
thuong tru, giay phep xay dung hoac crawler tu dong.

## Pham vi va thu tu thuc hien

### 1. Schema va du lieu khai sinh

- Tao migration `procedure_fact` versioned: `procedure_version_id`,
  `fact_type`, `value`, `jurisdiction_scope`, `administrative_area_id`,
  `effective_from`, `effective_to`, `legal_source_version_id`, `status` va
  metadata provenance. Chi fact `published`, con hieu luc va dung jurisdiction
  duoc structured query tra ve.
- Mo rong manifest/import voi `scenario_code`, jurisdiction va fact provenance;
  giu raw snapshot, checksum va source version hien co.
- Operator/reviewer chon va review nguon quoc gia khai sinh truoc khi import;
  publish chi sau khi metadata citation, checksum, embedding va effective date
  hop le.
- Seed fact chuan hoa toi thieu: doi tuong, co quan tiep nhan, trinh tu, ho so,
  thoi han, le phi va can cu phap ly. Fact phap ly phai tham chieu legal-source
  version da publish.

### 2. Procedure resolver va structured query

- Thay trigger tu khoa khai sinh trong graph bang output co schema:
  `procedure_code`, `scenario_code`, `claim_types`, `jurisdiction_required` va
  `retrieval_paths`. V1 chi resolve `BIRTH_REGISTRATION`; intent chua ro phai
  hoi lam ro hoac tra out-of-scope.
- Tao `StructuredQuerySpec` Pydantic voi resource `procedure_fact`, select,
  filter, sort va limit thuoc allowlist. LLM khong sinh raw SQL.
- Compiler dung bind parameters va tu them filter published/effective/language/
  jurisdiction. Tu choi column, operator, join, subquery va limit ngoai policy.
- Structured result phai duoc chuan hoa thanh government evidence cung contract
  voi RAG result de dung chung scoring va citation verifier.

### 3. Government hybrid retrieval

- Sua `RagService` de nhan procedure/scenario/jurisdiction context, sua RRF
  query va giu exact document number, full-text, vector retrieval trong tap da
  metadata-filter.
- Rerank theo exact match, procedure/scenario, jurisdiction, effective version,
  source priority va section. Tang diem `decree` chi voi legal basis/condition;
  khong bo qua van ban duoc tham chieu truc tiep hoac van ban cap cao hon.
- Mo rong evidence voi `source_type`, scores, source/version IDs, jurisdiction,
  effective dates va claim IDs. Government citation chi do backend tao tu
  metadata retrieval.
- Citation verifier loai legal claim khong co government evidence. Khi khong co
  evidence dung, graph tra `unable_to_verify`, khong de LLM tu suy dien.

### 4. Confidence, external adapter va graph

- Tinh `confidence_score` tu claim coverage, authority, retrieval quality,
  jurisdiction, freshness/version va consistency. Luu score, band va reasons
  trong graph/session state; khong luu raw external page hay PII.
- Routing: `high` chi dung government evidence; `medium` va `low` co the yeu
  cau external search; no-result hoac user tu choi consent tra
  `unable_to_verify`.
- Them `ExternalSearchAdapter` protocol, fake adapter cho test, feature flag
  mac dinh tat, allowlist, timeout va result limit tu config server-side. Plan
  nay khong tich hop provider that.
- Them `external_search_consent` rieng trong Redis, tach voi
  `external_llm_consent`. Adapter khong duoc goi khi chua co consent va raw
  result khong duoc persistence/cache qua request.

### 5. SSE va frontend

- Mo rong `message.complete` voi `answer_strategy`, `confidence_score`,
  `confidence_band`, `confidence_reasons`, grouped citations,
  `external_search_used` va `external_search_consent_required`.
- Cap nhat API types/parser frontend. Chi hoi consent external search khi server
  yeu cau, khong dung browser confirm truoc cau hoi government-only.
- Hien band thay cho score thap phan; tach “Nguon chinh thuc” va “Tham khao ben
  ngoai”; hien warning bat buoc cho `low` va `unable_to_verify`.
- External citation phai co nhan tham khao. UI khong duoc trinh bay external
  evidence nhu can cu phap ly.

## Test va verify

### Unit va integration backend

- Test migration/schema `procedure_fact`, manifest provenance va publish guard.
- Test `StructuredQuerySpec` allowlist, parameterized SQL, status/effective/
  jurisdiction filters va tu choi request khong hop le.
- Test exact/keyword/vector RRF, procedure/scenario resolution, national
  fallback va cam locality khac.
- Test evidence/citation verifier, confidence threshold/reason va High/Medium/
  Low/`unable_to_verify` routing.
- Test fake external adapter: High khong goi adapter; Medium/Low yeu cau
  consent; tu choi consent/no-result abstain; raw external content khong nam
  trong Redis state.
- Test FastAPI SSE tra day du response metadata va citation group.

### Frontend va data verification

- Vitest cho consent theo server response, band/warning, grouped citations va
  external evidence khong duoc hien thi nhu legal authority.
- Chay manifest validate/import/publish tren PostgreSQL integration database;
  verify checksum, provenance, effective date va published-only retrieval.
- Tao golden cases khai sinh cho exact document number, paraphrase, thieu dia
  ban, wrong version, evidence day du, evidence thieu va no evidence.

### Lenh bat buoc

```bash
cd be && uv run pytest
cd fe && npm run test && npm run build
cd be && alembic upgrade head
cd .. && uv run --with pymarkdownlnt pymarkdownlnt scan plan_3.md
```

Chi chuyen sang Plan 4 khi cac lenh tren pass va golden cases khai sinh co zero
missing official citation, zero wrong locality/version va zero legal claim
khong grounded.

## Gia dinh

- Operator va reviewer nghiep vu cung cap nguon phap ly/thu tuc khai sinh truoc
  khi seed; Plan 3 khong tu dong tim hoac import nguon moi.
- External adapter fake va feature flag la contract bat buoc; provider that
  duoc cau hinh trong dot sau.
- Pham vi chi la dang ky khai sinh; cac package thu tuc khac thuoc sau quality
  gate cua Plan 4.
