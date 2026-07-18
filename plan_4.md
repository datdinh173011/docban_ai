# Plan 4 - Production Quality Gate Cho RAG Khai Sinh

## Muc tieu

Tao quality gate deterministic cho package dang ky khai sinh truoc khi mo rong
sang thuong tru hoac giay phep xay dung. Framework chay duoc voi fixture, nhung
production gate chi mo khi reviewer cung cap 70 case va source snapshot da duyet.

## Evaluation contract

- `EvaluationCase` khai bao procedure/scenario/jurisdiction, retrieval path,
  confidence band, evidence/citation/fact bat buoc, claim cam, warning,
  external-search behavior, criticality va reviewed status.
- `EvaluationObservation` la ket qua runtime da chuan hoa: evidence/citation,
  answer facts, answer strategy, confidence score va warning.
- JSONL dataset chua cap `case` va `observation`; fixture nam trong
  `be/evaluation/datasets/`, con production dataset do reviewer cung cap.
- Production dataset co 70 case reviewed: 35 High, 18 Medium va 17 Low hoac
  `unable_to_verify`.

## Metric va release gate

- Runner tinh recall@5, citation coverage, groundedness, confidence-band
  accuracy, Brier score va ECE; failure duoc phan loai data, retrieval,
  citation, confidence, groundedness, warning hoac external authority.
- Critical citation coverage, wrong locality/version, missing warning, external
  source dung lam legal authority va blocking hallucination deu phai bang khong.
- Gate production: recall@5 `>= 95%`, groundedness `>= 95%`, band accuracy
  `>= 90%`, Brier `<= 0.10`, ECE `<= 0.05`.
- CLI tao JSON/Markdown report va exit nonzero khi gate fail. Sua loi bang draft
  knowledge version moi, them regression case va chay lai full suite.

## Chay va verify

```bash
cd be
uv run python -m app.evaluation.run \
  --package BIRTH_REGISTRATION \
  --dataset evaluation/datasets/birth_registration.fixture.jsonl
uv run pytest
cd ../fe && npm run test && npm run build
```

Dung `--strict` voi dataset 70 case da reviewed de chay production gate. Fixture
khong duoc dung de mo rong procedure hoac publish package production.
