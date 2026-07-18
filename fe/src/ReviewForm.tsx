import { useEffect, useState } from "react";
import {
  FormSchemaResponse,
  ValidationResult,
  exportFormPdf,
  getFormDraft,
  getFormSchema,
  updateFormDraft,
  validateForm,
} from "./api";

const KNOWN_FORM_CODES = ["BIRTH_REGISTRATION_FORM", "PERMANENT_RESIDENCE_CT01_FORM", "CONSTRUCTION_PERMIT_REQUEST_FORM"];

const STATUS_LABEL: Record<ValidationResult["status"], string> = {
  valid: "HỒ SƠ HỢP LỆ",
  valid_with_warnings: "HỒ SƠ HỢP LỆ, CÓ CẢNH BÁO",
  invalid: "HỒ SƠ CẦN SỬA",
  unable_to_validate: "CHƯA THỂ THẨM ĐỊNH",
};

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function FormPicker({ onPick }: { onPick: (formCode: string) => void }) {
  const [titles, setTitles] = useState<Record<string, string>>({});

  useEffect(() => {
    void Promise.all(
      KNOWN_FORM_CODES.map((code) => getFormSchema(code).then((schema) => [code, schema.title_vi] as const).catch(() => [code, code] as const)),
    ).then((entries) => setTitles(Object.fromEntries(entries)));
  }, []);

  return (
    <div className="review-empty">
      <span aria-hidden="true">📄</span>
      <h2>Chọn mẫu đơn để rà soát</h2>
      <p>Trò chuyện với ICIVI để được tự động điền, hoặc chọn thẳng một mẫu đơn dưới đây để tự điền.</p>
      <div className="form-picker">
        {KNOWN_FORM_CODES.map((code) => (
          <button key={code} onClick={() => onPick(code)}>{titles[code] ?? code}</button>
        ))}
      </div>
    </div>
  );
}

function ResultPanel({ validation, dirty, onExport, exporting }: { validation: ValidationResult | null; dirty: boolean; onExport: () => void; exporting: boolean }) {
  if (!validation) {
    return (
      <aside className="review-result-panel">
        <p className="result-placeholder">Nhấn <strong>Thẩm định &amp; Rà soát</strong> để hệ thống kiểm tra hồ sơ trước khi xuất PDF.</p>
      </aside>
    );
  }
  const canExport = validation.summary.blocking_error === 0 && !dirty;
  return (
    <aside className="review-result-panel">
      <p className="result-title">KẾT QUẢ KIỂM DUYỆT HỆ THỐNG</p>
      <div className={`result-stamp ${validation.status}`}>{STATUS_LABEL[validation.status]}</div>
      <ul className="result-summary">
        <li className="blocking_error">Lỗi cần sửa: {validation.summary.blocking_error}</li>
        <li className="warning">Cảnh báo: {validation.summary.warning}</li>
        <li className="suggestion">Gợi ý: {validation.summary.suggestion}</li>
      </ul>
      {validation.issues.length > 0 && (
        <ol className="result-issues">
          {validation.issues.map((issue) => (
            <li key={`${issue.field_code}-${issue.issue_code}`} className={issue.severity}>{issue.message_vi}</li>
          ))}
        </ol>
      )}
      {dirty && validation && <p className="result-stale">Hồ sơ đã thay đổi — hãy thẩm định lại trước khi xuất PDF.</p>}
      <button className="export-button" disabled={!canExport || exporting} onClick={onExport}>
        {exporting ? "Đang tạo PDF..." : "⬇ Tải PDF đã điền"}
      </button>
    </aside>
  );
}

export function ReviewForm({ activeFormCode, onFormCodeConsumed }: { activeFormCode: string | null; onFormCodeConsumed: () => void }) {
  const [formCode, setFormCode] = useState<string | null>(activeFormCode);
  const [schema, setSchema] = useState<FormSchemaResponse | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(false);
  const [validating, setValidating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (activeFormCode) {
      setFormCode(activeFormCode);
      onFormCodeConsumed();
    }
  }, [activeFormCode, onFormCodeConsumed]);

  useEffect(() => {
    if (!formCode) return;
    setLoading(true);
    setError(null);
    Promise.all([getFormSchema(formCode), getFormDraft(formCode)])
      .then(([schemaResponse, draftResponse]) => {
        setSchema(schemaResponse);
        setValues(draftResponse.fields as Record<string, string>);
        setValidation(null);
        setDirty(false);
      })
      .catch(() => setError("Không thể tải biểu mẫu. Vui lòng thử lại."))
      .finally(() => setLoading(false));
  }, [formCode]);

  function updateField(fieldCode: string, value: string) {
    setValues((current) => ({ ...current, [fieldCode]: value }));
    setDirty(true);
  }

  // Always sends the full local snapshot (never a single changed field): the backend
  // PUT does a read-merge-write on the session draft, so overlapping per-field saves
  // from fast sequential edits can race and silently drop an earlier field's value.
  // A self-contained snapshot on every save makes each write independent of write order.
  async function persistDraft() {
    if (!formCode) return;
    await updateFormDraft(formCode, values).catch(() => setError("Không thể lưu biểu mẫu vừa sửa."));
  }

  function handleSelectChange(fieldCode: string, value: string) {
    const next = { ...values, [fieldCode]: value };
    setValues(next);
    setDirty(true);
    if (formCode) void updateFormDraft(formCode, next).catch(() => setError("Không thể lưu biểu mẫu vừa sửa."));
  }

  async function runValidation() {
    if (!formCode) return;
    setValidating(true);
    setError(null);
    try {
      setValidation(await validateForm(formCode));
      setDirty(false);
    } catch {
      setError("Không thể thẩm định hồ sơ lúc này.");
    } finally {
      setValidating(false);
    }
  }

  async function runExport() {
    if (!formCode || !validation) return;
    setExporting(true);
    setError(null);
    try {
      downloadBlob(await exportFormPdf(formCode, validation.validation_id), `${formCode.toLowerCase()}.pdf`);
    } catch {
      setError("Không thể xuất PDF. Vui lòng thẩm định lại hồ sơ.");
    } finally {
      setExporting(false);
    }
  }

  if (!formCode) return <FormPicker onPick={setFormCode} />;
  if (loading || !schema) return <div className="review-empty"><span aria-hidden="true">📄</span><p>Đang tải biểu mẫu...</p></div>;

  const groups = [...schema.groups].sort((a, b) => a.display_order - b.display_order);

  return (
    <div className="review-form">
      <div className="review-form-main">
        <div className="review-form-header">
          <div>
            <h2>{schema.title_vi}</h2>
            <button className="link-button" onClick={() => { setFormCode(null); setSchema(null); }}>Đổi mẫu đơn khác</button>
          </div>
          <button className="primary-action" onClick={() => void runValidation()} disabled={validating}>
            {validating ? "Đang thẩm định..." : "Thẩm định & Rà soát"}
          </button>
        </div>
        {error && <p className="form-error">{error}</p>}
        {groups.map((group) => (
          <section key={group.group_code} className="field-group">
            <h3>{group.label_vi}</h3>
            <div className="field-grid">
              {schema.fields.filter((field) => field.group_code === group.group_code).map((field) => {
                const issue = validation?.issues.find((item) => item.field_code === field.field_code);
                return (
                  <label key={field.field_code} className="field">
                    <span className="field-label">{field.label_vi}{field.required && <span className="required">*</span>}</span>
                    {field.data_type === "enum" ? (
                      <select
                        value={values[field.field_code] ?? ""}
                        onChange={(event) => handleSelectChange(field.field_code, event.target.value)}
                        className={issue ? issue.severity : ""}
                      >
                        <option value="">-- Chọn --</option>
                        {field.enum_values?.map((option) => <option key={option} value={option}>{option}</option>)}
                      </select>
                    ) : field.data_type === "table" ? (
                      <textarea
                        value={values[field.field_code] ?? ""}
                        onChange={(event) => updateField(field.field_code, event.target.value)}
                        onBlur={() => void persistDraft()}
                        className={issue ? issue.severity : ""}
                        rows={2}
                      />
                    ) : (
                      <input
                        type={field.data_type === "date" ? "date" : field.data_type === "number" ? "number" : "text"}
                        value={values[field.field_code] ?? ""}
                        onChange={(event) => updateField(field.field_code, event.target.value)}
                        onBlur={() => void persistDraft()}
                        className={issue ? issue.severity : ""}
                      />
                    )}
                    {issue && <span className={`field-issue ${issue.severity}`}>{issue.message_vi}</span>}
                  </label>
                );
              })}
            </div>
          </section>
        ))}
      </div>
      <ResultPanel validation={validation} dirty={dirty} onExport={() => void runExport()} exporting={exporting} />
    </div>
  );
}
