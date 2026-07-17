import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

vi.mock("./api", () => ({
  bootstrapSession: vi.fn().mockResolvedValue(undefined),
  deleteSession: vi.fn().mockResolvedValue(undefined),
  streamChat: vi.fn().mockImplementation(async (_message, _language, onEvent) => {
    onEvent({ type: "message.delta", text: "Phản hồi thử nghiệm" });
    onEvent({ type: "message.complete", intent: "general", quickReplies: ["Hỏi thêm"] });
  }),
}));

describe("App", () => {
  beforeEach(() => vi.clearAllMocks());

  it("starts a chat from a suggested request", async () => {
    render(<App />);
    fireEvent.click(screen.getByText("Tôi muốn đăng ký khai sinh cho bé"));
    expect(await screen.findByText("Phản hồi thử nghiệm")).toBeInTheDocument();
    expect(screen.getByText("Hỏi thêm")).toBeInTheDocument();
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

  it("shows the review placeholder", () => {
    render(<App />);
    fireEvent.click(screen.getByText(/Rà soát & Kiểm tra đơn/));
    expect(screen.getByText("Rà soát đơn đang được chuẩn bị")).toBeInTheDocument();
  });
});
