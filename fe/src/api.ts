export type StreamEvent =
  | { type: "message.delta"; text: string }
  | { type: "translation.consent_required"; provider: string }
  | {
    type: "message.complete";
    intent: string;
    quickReplies: string[];
    citations: Citation[];
    answerStrategy: string;
    confidenceBand: "high" | "medium" | "low" | null;
    confidenceReasons: string[];
    externalSearchUsed: boolean;
    externalSearchConsentRequired: boolean;
    formCode: string | null;
  }
  | { type: "error"; message: string };

export type FormFieldSchema = {
  field_code: string;
  label_vi: string;
  group_code: string;
  data_type: "string" | "date" | "enum" | "number" | "table";
  required: boolean;
  enum_values: string[] | null;
};

export type FormGroupSchema = { group_code: string; label_vi: string; display_order: number };

export type FormSchemaResponse = {
  form_code: string;
  title_vi: string;
  groups: FormGroupSchema[];
  fields: FormFieldSchema[];
};

export type FormDraftResponse = {
  form_code: string;
  fields: Record<string, unknown>;
  updated_at: string | null;
};

export type ValidationIssue = {
  issue_code: string;
  rule_code: string;
  field_code: string | null;
  severity: "blocking_error" | "warning" | "suggestion" | "unable_to_verify";
  message_vi: string;
  suggestion_vi: string | null;
};

export type ValidationResult = {
  validation_id: string;
  form_code: string;
  input_hash: string;
  status: "valid" | "valid_with_warnings" | "invalid" | "unable_to_validate";
  summary: { blocking_error: number; warning: number; suggestion: number; unable_to_verify: number };
  issues: ValidationIssue[];
  validated_at: string;
};

export type Citation = {
  citation_id: string;
  source_code: string;
  source_title: string;
  document_number: string | null;
  section_reference: string | null;
  source_url: string | null;
  effective_from: string | null;
  jurisdiction_scope: string;
  administrative_area_code: string | null;
  quote_preview: string;
  source_type: "government" | "external";
  source_status?: "snapshot" | "reviewed";
  crawled_at?: string | null;
  procedure_code?: string | null;
  snapshot_path?: string | null;
};

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

export async function bootstrapSession(): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/v1/sessions`, { method: "POST", credentials: "include" });
  if (!response.ok) throw new Error("Không thể khởi tạo phiên trò chuyện.");
}

export async function deleteSession(): Promise<void> {
  await fetch(`${apiBaseUrl}/v1/sessions/current`, { method: "DELETE", credentials: "include" });
}

export async function streamChat(
  message: string,
  languageCode: string,
  translationConsent: boolean | null,
  externalSearchConsent: boolean | null,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/v1/chat/stream`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      language_code: languageCode,
      translation_consent: translationConsent,
      external_search_consent: externalSearchConsent,
    }),
  });
  if (!response.ok || !response.body) throw new Error("Không thể kết nối với trợ lý ICIVI.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    frames.forEach((frame) => {
      const event = frame.match(/^event: (.+)$/m)?.[1];
      const data = frame.match(/^data: (.+)$/m)?.[1];
      if (!event || !data) return;
      const payload = JSON.parse(data) as Record<string, unknown>;
      if (event === "message.delta") onEvent({ type: event, text: String(payload.text ?? "") });
      if (event === "translation.consent_required") onEvent({ type: event, provider: String(payload.provider ?? "AI") });
      if (event === "message.complete") onEvent({
        type: event,
        intent: String(payload.intent ?? "general"),
        quickReplies: (payload.quick_replies as string[]) ?? [],
        citations: (payload.citations as Citation[]) ?? [],
        answerStrategy: String(payload.answer_strategy ?? "unable_to_verify"),
        confidenceBand: (payload.confidence_band as "high" | "medium" | "low" | null) ?? null,
        confidenceReasons: (payload.confidence_reasons as string[]) ?? [],
        externalSearchUsed: Boolean(payload.external_search_used),
        externalSearchConsentRequired: Boolean(payload.external_search_consent_required),
        formCode: (payload.form_code as string | null) ?? null,
      });
      if (event === "error") onEvent({ type: event, message: String(payload.message ?? "Có lỗi xảy ra.") });
    });
  }
}

async function parseJsonOrThrow<T>(response: Response, errorMessage: string): Promise<T> {
  if (!response.ok) throw new Error(errorMessage);
  return (await response.json()) as T;
}

export async function getFormSchema(formCode: string): Promise<FormSchemaResponse> {
  const response = await fetch(`${apiBaseUrl}/v1/forms/${formCode}/schema`, { credentials: "include" });
  return parseJsonOrThrow(response, "Không thể tải cấu trúc biểu mẫu.");
}

export async function getFormDraft(formCode: string): Promise<FormDraftResponse> {
  const response = await fetch(`${apiBaseUrl}/v1/forms/${formCode}/draft`, { credentials: "include" });
  return parseJsonOrThrow(response, "Không thể tải dữ liệu đơn đã điền.");
}

export async function updateFormDraft(formCode: string, fields: Record<string, unknown>): Promise<FormDraftResponse> {
  const response = await fetch(`${apiBaseUrl}/v1/forms/${formCode}/draft`, {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields }),
  });
  return parseJsonOrThrow(response, "Không thể lưu dữ liệu đơn.");
}

export async function validateForm(formCode: string): Promise<ValidationResult> {
  const response = await fetch(`${apiBaseUrl}/v1/forms/${formCode}/validate`, { method: "POST", credentials: "include" });
  return parseJsonOrThrow(response, "Không thể thẩm định biểu mẫu.");
}

export async function exportFormPdf(formCode: string, validationId: string): Promise<Blob> {
  const response = await fetch(`${apiBaseUrl}/v1/forms/${formCode}/exports/pdf`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ validation_id: validationId }),
  });
  if (!response.ok) throw new Error("Không thể xuất PDF. Vui lòng thẩm định lại hồ sơ.");
  return response.blob();
}
