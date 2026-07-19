import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { bootstrapSession, deleteSession, streamChat } from "./api";

vi.mock("./api", () => ({
  bootstrapSession: vi.fn().mockResolvedValue(undefined),
  deleteSession: vi.fn().mockResolvedValue(undefined),
  streamChat: vi.fn().mockImplementation(async (_message, language, translationConsent, _searchConsent, onEvent) => {
    if (language !== "vi" && !translationConsent) {
      onEvent({ type: "translation.consent_required", provider: "OpenRouter" });
      return;
    }
    onEvent({ type: "message.delta", text: "Phản hồi thử nghiệm" });
    onEvent({ type: "message.complete", intent: "general", quickReplies: ["Hỏi thêm"], citations: [{ citation_id: "CIT-1", source_code: "LAW", source_title: "Luật Hộ tịch", document_number: "60/2014/QH13", section_reference: "Điều 16", source_url: "https://example.test/source", effective_from: "2016-01-01", jurisdiction_scope: "national", administrative_area_code: null, quote_preview: "Trích dẫn", source_type: "government" }], answerStrategy: "high", confidenceBand: "high", confidenceReasons: [], externalSearchUsed: false, externalSearchConsentRequired: false, formCode: null });
  }),
  getFormSchema: vi.fn().mockResolvedValue({ form_code: "BIRTH_REGISTRATION_FORM", title_vi: "Tờ khai đăng ký khai sinh", groups: [], fields: [] }),
  getFormDraft: vi.fn().mockResolvedValue({ form_code: "BIRTH_REGISTRATION_FORM", fields: {}, updated_at: null }),
  updateFormDraft: vi.fn().mockResolvedValue({ form_code: "BIRTH_REGISTRATION_FORM", fields: {}, updated_at: null }),
  validateForm: vi.fn(),
  exportFormPdf: vi.fn(),
}));

vi.mock("./VoiceInput", () => ({
  VoiceInput: () => <button type="button">Micro thử nghiệm</button>,
}));

describe("App", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
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

  it("starts a clean English session when changing languages", async () => {
    render(<App />);
    fireEvent.click(screen.getByText("Tôi muốn đăng ký khai sinh cho bé"));
    expect(await screen.findByText("Phản hồi thử nghiệm")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /chọn ngôn ngữ/i }));
    fireEvent.click(screen.getByRole("option", { name: /english/i }));

    await waitFor(() => expect(deleteSession).toHaveBeenCalledTimes(1));
    expect(bootstrapSession).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("button", { name: /select language, english/i })).toBeInTheDocument();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(screen.queryByText("Tôi muốn đăng ký khai sinh cho bé")).not.toBeInTheDocument();
    expect(screen.getByText("I want to register my child's birth")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Micro thử nghiệm" })).not.toBeInTheDocument();
  });

  it("offers voice input only for Vietnamese", () => {
    render(<App />);
    expect(screen.getByRole("button", { name: "Micro thử nghiệm" })).toBeInTheDocument();
  });

  it("requests translation consent before sending a non-Vietnamese chat", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /chọn ngôn ngữ/i }));
    fireEvent.click(screen.getByRole("option", { name: /english/i }));
    await waitFor(() => expect(bootstrapSession).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByText("I want to register my child's birth"));

    expect(await screen.findByRole("dialog")).toHaveTextContent("OpenRouter");
    fireEvent.click(screen.getByRole("button", { name: /allow and continue/i }));
    expect(await screen.findByText("Phản hồi thử nghiệm")).toBeInTheDocument();
  });

  it("sends an English question selected while its new session is still starting", async () => {
    let finishSessionBootstrap: () => void = () => undefined;
    render(<App />);
    await waitFor(() => expect(bootstrapSession).toHaveBeenCalledTimes(1));
    vi.mocked(bootstrapSession).mockImplementationOnce(() => new Promise<void>((resolve) => {
        finishSessionBootstrap = resolve;
      }));

    fireEvent.click(screen.getByRole("button", { name: /chọn ngôn ngữ/i }));
    fireEvent.click(screen.getByRole("option", { name: /english/i }));
    fireEvent.click(screen.getByText("I want to register my child's birth"));

    await waitFor(() => expect(bootstrapSession).toHaveBeenCalledTimes(2));
    finishSessionBootstrap();
    expect(await screen.findByRole("dialog")).toHaveTextContent("OpenRouter");
  });

  it("disables the language selector while a response is streaming", async () => {
    let finishStreaming: () => void = () => undefined;
    vi.mocked(streamChat).mockImplementationOnce(async (_message, _language, _translationConsent, _searchConsent, onEvent) => {
      onEvent({ type: "message.delta", text: "Đang trả lời" });
      await new Promise<void>((resolve) => {
        finishStreaming = resolve;
      });
    });
    render(<App />);

    fireEvent.click(screen.getByText("Tôi muốn đăng ký khai sinh cho bé"));
    const languageButton = screen.getByRole("button", { name: /chọn ngôn ngữ/i });
    expect(languageButton).toBeDisabled();

    finishStreaming();
    await waitFor(() => expect(languageButton).not.toBeDisabled());
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
