import { useEffect, useRef, useState } from "react";

import { ApiError, getVoiceStatus, transcribeAudio } from "./api";

const MAX_RECORDING_MS = 60_000;

type VoicePhase = "idle" | "recording" | "transcribing";

type VoiceInputProps = {
  disabled?: boolean;
  onBusyChange: (busy: boolean) => void;
  onTranscript: (text: string) => void;
};

function preferredMimeType(): string | undefined {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/ogg;codecs=opus",
    "audio/mp4",
  ];
  return candidates.find((type) => MediaRecorder.isTypeSupported(type));
}

function errorMessage(error: unknown): string {
  if (error instanceof DOMException && error.name === "NotAllowedError") {
    return "Bạn chưa cho phép trình duyệt sử dụng micro.";
  }
  if (error instanceof ApiError) {
    if (error.status === 413) return "Bản ghi quá lớn. Vui lòng ghi lại câu ngắn hơn.";
    if (error.status === 503) return "Nhận dạng giọng nói hiện không khả dụng.";
    if (error.detail === "audio_too_long") return "Bản ghi vượt quá giới hạn 60 giây.";
    if (error.detail === "transcript_empty") return "Không nhận diện được lời nói trong bản ghi.";
    return "Không thể xử lý bản ghi âm. Vui lòng thử lại.";
  }
  return "Không thể truy cập hoặc xử lý âm thanh từ micro.";
}

export function VoiceInput({ disabled = false, onBusyChange, onTranscript }: VoiceInputProps) {
  const [available, setAvailable] = useState(false);
  const [phase, setPhase] = useState<VoicePhase>("idle");
  const [feedback, setFeedback] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    const mediaDevices = navigator.mediaDevices as MediaDevices | undefined;
    const browserSupported = Boolean(
      typeof mediaDevices?.getUserMedia === "function" && typeof window.MediaRecorder !== "undefined",
    );
    if (browserSupported) {
      void getVoiceStatus()
        .then((status) => {
          if (mountedRef.current) setAvailable(status.available);
        })
        .catch(() => undefined);
    }

    return () => {
      mountedRef.current = false;
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
      const recorder = recorderRef.current;
      if (recorder && recorder.state !== "inactive") {
        recorder.ondataavailable = null;
        recorder.onstop = null;
        recorder.stop();
      }
      streamRef.current?.getTracks().forEach((track) => track.stop());
      onBusyChange(false);
    };
  }, [onBusyChange]);

  function releaseStream() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }

  function stopRecording(automatic = false) {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (automatic) setFeedback("Đã đạt giới hạn 60 giây, đang xử lý bản ghi...");
    const recorder = recorderRef.current;
    if (recorder?.state !== "inactive") recorder?.stop();
  }

  async function startRecording() {
    setFeedback(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mountedRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      chunksRef.current = [];
      const mimeType = preferredMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onerror = () => {
        if (timerRef.current !== null) {
          window.clearTimeout(timerRef.current);
          timerRef.current = null;
        }
        recorder.onstop = null;
        if (recorder.state !== "inactive") recorder.stop();
        recorderRef.current = null;
        releaseStream();
        if (mountedRef.current) {
          setPhase("idle");
          setFeedback("Không thể ghi âm từ micro. Vui lòng thử lại.");
          onBusyChange(false);
        }
      };
      recorder.onstop = () => {
        recorderRef.current = null;
        releaseStream();
        if (!mountedRef.current) return;
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        setPhase("transcribing");
        void transcribeAudio(blob)
          .then((text) => {
            if (!mountedRef.current) return;
            onTranscript(text);
            setFeedback("Đã chuyển giọng nói thành văn bản. Bạn có thể kiểm tra trước khi gửi.");
          })
          .catch((error: unknown) => {
            if (mountedRef.current) setFeedback(errorMessage(error));
          })
          .finally(() => {
            if (!mountedRef.current) return;
            setPhase("idle");
            onBusyChange(false);
          });
      };
      recorder.start();
      setPhase("recording");
      onBusyChange(true);
      timerRef.current = window.setTimeout(() => stopRecording(true), MAX_RECORDING_MS);
    } catch (error) {
      releaseStream();
      setPhase("idle");
      setFeedback(errorMessage(error));
      onBusyChange(false);
    }
  }

  if (!available) return null;

  const recording = phase === "recording";
  const label = recording
    ? "Dừng ghi âm"
    : phase === "transcribing"
      ? "Đang chuyển giọng nói thành văn bản"
      : "Nhập bằng giọng nói";

  return (
    <div className="voice-control">
      <button
        aria-label={label}
        className={`voice-button ${recording ? "recording" : ""}`}
        disabled={disabled || phase === "transcribing"}
        onClick={() => recording ? stopRecording() : void startRecording()}
        title={label}
        type="button"
      >
        {recording ? <span className="recording-dot" /> : (
          <svg aria-hidden="true" viewBox="0 0 24 24">
            <path d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Z" />
            <path d="M19 11v1a7 7 0 0 1-14 0v-1M12 19v3M8 22h8" />
          </svg>
        )}
      </button>
      {feedback && <span className="voice-feedback" role="status">{feedback}</span>}
    </div>
  );
}
