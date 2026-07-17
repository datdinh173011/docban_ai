export type StreamEvent =
  | { type: "message.delta"; text: string }
  | { type: "message.complete"; intent: string; quickReplies: string[] }
  | { type: "error"; message: string };

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
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/v1/chat/stream`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, language_code: languageCode }),
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
      if (event === "message.complete") onEvent({ type: event, intent: String(payload.intent ?? "general"), quickReplies: (payload.quick_replies as string[]) ?? [] });
      if (event === "error") onEvent({ type: event, message: String(payload.message ?? "Có lỗi xảy ra.") });
    });
  }
}
