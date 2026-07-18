# Plan 2 - RAG Backend Cho Dang Ky Khai Sinh

## Muc tieu

Trien khai RAG cho thu tuc dang ky khai sinh tren backend ICIVI. He thong chi
tra loi noi dung hanh chinh khi truy xuat duoc nguon chinh thuc da publish va
con hieu luc, kem citation do backend tao.

## Pham vi

- Corpus pilot national: Luat Ho tich, nghi dinh huong dan con hieu luc va
  trang thu tuc chinh thuc tren Cong Dich vu cong.
- Knowledge Domain versioned tren PostgreSQL voi pgvector 1536 dimensions.
- CLI noi bo de validate, import va publish manifest da duoc operator duyet.
- Hybrid retrieval: exact document number, full-text va semantic RRF.
- Consent mot lan moi session truoc khi gui cau hoi den embedding/LLM provider
  ngoai; khong co consent hoac khong du evidence thi khong tra loi phap ly.
- Citation `[CIT-n]` trong cau tra loi va danh sach nguon o cuoi message chat.

## Van hanh

1. Operator tao manifest JSON co URL nguon chinh thuc, metadata hieu luc va
   file local hoac URL chinh xac.
2. Chay `python -m app.knowledge_cli validate <manifest>`.
3. Chay `python -m app.knowledge_cli import <manifest>` de luu raw file,
   normalized text, chunks va embeddings dang draft.
4. Kiem tra provenance/checksum, sau do chay
   `python -m app.knowledge_cli publish <document_code>`.

Publish la atomic va tu choi file checksum sai, metadata citation thieu, tai
lieu het hieu luc hoac chunk chua co embedding. Khong co API quan tri cong khai
trong dot nay.

## Cau hinh

- `DATABASE_URL`: ket noi PostgreSQL async.
- `KNOWLEDGE_DATA_DIR`: root local cho raw va normalized source files.
- `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL`: provider
  OpenAI-compatible; model mac dinh la `text-embedding-3-small`.
- `EMBEDDING_DIMENSIONS=1536`: khoa dimension cua migration nay.

## Nghiem thu

- Migration tao pgvector, schema Knowledge Domain va cac index retrieval.
- Retrieval chi dung record published/con hieu luc, dung thu tuc/ngon ngu va
  fallback national; khong bao gio thay bang noi dung dia phuong khac.
- SSE `message.complete` chua citation backend da xac thuc; UI render ma va
  link nguon.
- Test bao phu chunking, manifest, citation token, session consent va chat
  fallback an toan.
