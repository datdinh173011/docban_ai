import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { VoiceInput } from "./VoiceInput";
import { getVoiceStatus, transcribeAudio } from "./api";

vi.mock("./api", () => ({
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: string) {
      super(detail);
    }
  },
  getVoiceStatus: vi.fn(),
  transcribeAudio: vi.fn(),
}));

class FakeMediaRecorder {
  static isTypeSupported = vi.fn().mockReturnValue(true);
  mimeType: string;
  ondataavailable: ((event: BlobEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onstop: (() => void) | null = null;
  state: RecordingState = "inactive";

  constructor(_stream: MediaStream, options?: MediaRecorderOptions) {
    this.mimeType = options?.mimeType ?? "audio/webm";
  }

  start() {
    this.state = "recording";
  }

  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["audio"], { type: this.mimeType }) } as BlobEvent);
    this.onstop?.();
  }
}

describe("VoiceInput", () => {
  const stopTrack = vi.fn();
  const getUserMedia = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getVoiceStatus).mockResolvedValue({ available: true });
    vi.mocked(transcribeAudio).mockResolvedValue("tôi cần đăng ký khai sinh");
    getUserMedia.mockResolvedValue({ getTracks: () => [{ stop: stopTrack }] });
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia },
    });
    vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("stays hidden when the backend capability is unavailable", async () => {
    vi.mocked(getVoiceStatus).mockResolvedValue({ available: false });
    render(<VoiceInput onBusyChange={vi.fn()} onTranscript={vi.fn()} />);
    await waitFor(() => expect(getVoiceStatus).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: "Nhập bằng giọng nói" })).not.toBeInTheDocument();
  });

  it("records, uploads, and returns text without sending it", async () => {
    const onBusyChange = vi.fn();
    const onTranscript = vi.fn();
    render(<VoiceInput onBusyChange={onBusyChange} onTranscript={onTranscript} />);

    fireEvent.click(await screen.findByRole("button", { name: "Nhập bằng giọng nói" }));
    expect(await screen.findByRole("group", { name: "Trạng thái ghi âm" })).toHaveTextContent("Đang nghe");
    expect(screen.getByLabelText("Đã ghi 0 giây trên tổng số 60 giây")).toHaveTextContent("00:00 / 01:00");
    expect(await screen.findByRole("button", { name: "Dừng ghi âm" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Dừng ghi âm" }));

    await waitFor(() => expect(transcribeAudio).toHaveBeenCalledWith(expect.any(Blob)));
    expect(onTranscript).toHaveBeenCalledWith("tôi cần đăng ký khai sinh");
    expect(stopTrack).toHaveBeenCalled();
    expect(onBusyChange).toHaveBeenLastCalledWith(false);
    expect(screen.getByRole("status")).toHaveTextContent("kiểm tra trước khi gửi");
  });

  it("shows a processing bar until transcription finishes", async () => {
    let finishTranscription: (text: string) => void = () => undefined;
    vi.mocked(transcribeAudio).mockImplementationOnce(() => new Promise((resolve) => {
      finishTranscription = resolve;
    }));
    const onTranscript = vi.fn();
    render(<VoiceInput onBusyChange={vi.fn()} onTranscript={onTranscript} />);

    fireEvent.click(await screen.findByRole("button", { name: "Nhập bằng giọng nói" }));
    fireEvent.click(await screen.findByRole("button", { name: "Dừng ghi âm" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Đang chuyển giọng nói thành văn bản");
    expect(screen.queryByRole("button", { name: "Nhập bằng giọng nói" })).not.toBeInTheDocument();

    finishTranscription("nội dung đã nhận dạng");
    await waitFor(() => expect(onTranscript).toHaveBeenCalledWith("nội dung đã nhận dạng"));
    expect(await screen.findByRole("button", { name: "Nhập bằng giọng nói" })).toBeInTheDocument();
  });

  it("shows a clear permission error", async () => {
    getUserMedia.mockRejectedValue(new DOMException("denied", "NotAllowedError"));
    render(<VoiceInput onBusyChange={vi.fn()} onTranscript={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Nhập bằng giọng nói" }));
    expect(await screen.findByRole("status")).toHaveTextContent("chưa cho phép");
  });

  it("stops the microphone when unmounted during recording", async () => {
    const view = render(<VoiceInput onBusyChange={vi.fn()} onTranscript={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Nhập bằng giọng nói" }));
    expect(await screen.findByRole("button", { name: "Dừng ghi âm" })).toBeInTheDocument();
    view.unmount();
    expect(stopTrack).toHaveBeenCalled();
    expect(transcribeAudio).not.toHaveBeenCalled();
  });

  it("automatically stops after 60 seconds", async () => {
    vi.useFakeTimers();
    const onTranscript = vi.fn();
    render(<VoiceInput onBusyChange={vi.fn()} onTranscript={onTranscript} />);
    await act(async () => {
      await Promise.resolve();
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Nhập bằng giọng nói" }));
      await Promise.resolve();
    });
    expect(screen.getByRole("group", { name: "Trạng thái ghi âm" })).toBeInTheDocument();
    await act(async () => {
      vi.advanceTimersByTime(60_000);
      await Promise.resolve();
    });
    expect(transcribeAudio).toHaveBeenCalled();
    expect(onTranscript).toHaveBeenCalledWith("tôi cần đăng ký khai sinh");
  });

  it("warns clearly during the final 10 seconds", async () => {
    vi.useFakeTimers();
    render(<VoiceInput onBusyChange={vi.fn()} onTranscript={vi.fn()} />);
    await act(async () => {
      await Promise.resolve();
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Nhập bằng giọng nói" }));
      await Promise.resolve();
    });
    expect(screen.getByRole("group", { name: "Trạng thái ghi âm" })).toBeInTheDocument();
    await act(async () => {
      vi.advanceTimersByTime(50_000);
    });
    expect(screen.getByText("Sắp hết thời gian")).toBeInTheDocument();
    expect(screen.getByText("Còn 10 giây")).toBeInTheDocument();
    expect(screen.getByLabelText("Đã ghi 50 giây trên tổng số 60 giây")).toHaveTextContent("00:50");
  });
});
