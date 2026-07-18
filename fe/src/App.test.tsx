import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

vi.mock("./api", () => ({
  bootstrapSession: vi.fn().mockResolvedValue(undefined),
  deleteSession: vi.fn().mockResolvedValue(undefined),
  streamChat: vi.fn().mockImplementation(async (_message, _language, _searchConsent, onEvent) => {
    onEvent({ type: "message.delta", text: "Phản hồi thử nghiệm" });
    onEvent({ type: "message.complete", intent: "general", quickReplies: ["Hỏi thêm"], citations: [{ citation_id: "CIT-1", source_code: "LAW", source_title: "Luật Hộ tịch", document_number: "60/2014/QH13", section_reference: "Điều 16", source_url: "https://example.test/source", effective_from: "2016-01-01", jurisdiction_scope: "national", administrative_area_code: null, quote_preview: "Trích dẫn", source_type: "government" }], answerStrategy: "high", confidenceBand: "high", confidenceReasons: [], externalSearchUsed: false, externalSearchConsentRequired: false, formCode: null });
  }),
  getFormSchema: vi.fn().mockResolvedValue({ form_code: "BIRTH_REGISTRATION_FORM", title_vi: "Tờ khai đăng ký khai sinh", groups: [], fields: [] }),
  getFormDraft: vi.fn().mockResolvedValue({ form_code: "BIRTH_REGISTRATION_FORM", fields: {}, updated_at: null }),
  updateFormDraft: vi.fn().mockResolvedValue({ form_code: "BIRTH_REGISTRATION_FORM", fields: {}, updated_at: null }),
  validateForm: vi.fn(),
  exportFormPdf: vi.fn(),
}));

describe("App", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("starts a chat from a suggested request", async () => {
    render(<App />);
    fireEvent.click(screen.getByText("Tôi muốn đăng ký khai sinh cho bé"));
    expect(await screen.findByText("Phản hồi thử nghiệm")).toBeInTheDocument();
    expect(screen.getByText("Hỏi thêm")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Luật Hộ tịch" })).toHaveAttribute("href", "https://example.test/source");
  });

  it("keeps the message stream at its newest content", async () => {
    render(<App />);
    fireEvent.click(screen.getByText("Tôi muốn đăng ký khai sinh cho bé"));

    const stream = await screen.findByTestId("message-stream");
    Object.defineProperty(stream, "scrollHeight", { configurable: true, value: 720 });
    stream.scrollTop = 0;

    fireEvent.click(screen.getByText("Hỏi thêm"));

    await waitFor(() => expect(stream.scrollTop).toBe(720));
  });

  it("shows the form picker when no form is active yet", async () => {
    render(<App />);
    fireEvent.click(screen.getByText(/Rà soát & Kiểm tra đơn/));
    expect(await screen.findByText("Chọn mẫu đơn để rà soát")).toBeInTheDocument();
  });

  it("updates the selected language and closes the menu", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /chọn ngôn ngữ/i }));
    fireEvent.click(screen.getByRole("option", { name: /english/i }));

    expect(screen.getByRole("button", { name: /hiện tại english/i })).toBeInTheDocument();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("closes the language menu when clicking outside or pressing Escape", () => {
    render(<App />);
    const languageButton = screen.getByRole("button", { name: /chọn ngôn ngữ/i });

    fireEvent.click(languageButton);
    expect(screen.getByRole("listbox")).toBeInTheDocument();
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();

    fireEvent.click(languageButton);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });
});
