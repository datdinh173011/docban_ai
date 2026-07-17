import { FormEvent, useEffect, useRef, useState } from "react";
import { bootstrapSession, deleteSession, streamChat } from "./api";

type Message = { id: string; role: "user" | "assistant"; content: string; quickReplies?: string[] };
type Language = { code: string; label: string };

const languages: Language[] = [
  { code: "vi", label: "Tiếng Việt" },
  { code: "en", label: "English" },
  { code: "hmn", label: "Tiếng H'Mông" },
  { code: "km", label: "Tiếng Khmer" },
];

const suggestions = [
  "Tôi muốn đăng ký khai sinh cho bé",
  "Tôi muốn đăng ký cho con vào lớp 1",
  "Tôi muốn xin giấy phép xây dựng nhà",
  "Tôi muốn đăng ký thường trú",
];

const id = () => crypto.randomUUID();

export function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [language, setLanguage] = useState(languages[0]);
  const [menuOpen, setMenuOpen] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [reviewTab, setReviewTab] = useState(false);
  const streamRef = useRef<HTMLDivElement>(null);
  const isChatting = messages.length > 0;

  useEffect(() => {
    void bootstrapSession().catch(() => undefined);
  }, []);

  useEffect(() => {
    const stream = streamRef.current;
    if (stream) stream.scrollTop = stream.scrollHeight;
  }, [messages, streaming]);

  async function send(text = input) {
    const message = text.trim();
    if (!message || streaming) return;
    const assistantId = id();
    setMessages((current) => [
      ...current,
      { id: id(), role: "user", content: message },
      { id: assistantId, role: "assistant", content: "" },
    ]);
    setInput("");
    setStreaming(true);
    try {
      await streamChat(message, language.code, (event) => {
        if (event.type === "message.delta") {
          setMessages((current) => current.map((item) => item.id === assistantId ? { ...item, content: item.content + event.text } : item));
        }
        if (event.type === "message.complete") {
          setMessages((current) => current.map((item) => item.id === assistantId ? { ...item, quickReplies: event.quickReplies } : item));
        }
        if (event.type === "error") {
          setMessages((current) => current.map((item) => item.id === assistantId ? { ...item, content: event.message } : item));
        }
      });
    } catch (error) {
      const fallback = error instanceof Error ? error.message : "Có lỗi xảy ra.";
      setMessages((current) => current.map((item) => item.id === assistantId ? { ...item, content: fallback } : item));
    } finally {
      setStreaming(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void send();
  }

  async function reset() {
    await deleteSession();
    await bootstrapSession();
    setMessages([]);
    setReviewTab(false);
  }

  return (
    <div className="app-shell">
      <div className="app-chrome">
        <header className="site-header">
          <div className="header-rail">
            <div className="brand">
              <span className="logo" aria-hidden="true">&#10022;</span>
              <div>
                <h1>CIVI <span>· Trợ lý Hành chính công AI</span></h1>
                <div className="meta-row">
                  <div className="language">
                    <button className="language-button" aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}>
                      🌐 {language.label} <span>⌄</span>
                    </button>
                    {menuOpen && <div className="language-menu" role="listbox">
                      {languages.map((item) => <button key={item.code} className={item.code === language.code ? "selected" : ""} onClick={() => { setLanguage(item); setMenuOpen(false); }}>{item.label}</button>)}
                    </div>}
                  </div>
                  <span className="status">Hệ thống trực tuyến 24/7</span>
                </div>
              </div>
            </div>
            <div className="session-meta">Phiên làm việc: #ADM-8829<br /><strong>Trạng thái: Trực tuyến</strong></div>
          </div>
        </header>

        <nav className="tabs" aria-label="Chức năng CIVI">
          <div className="tabs-rail">
            <button className={!reviewTab ? "active" : ""} onClick={() => setReviewTab(false)}>💬 Trò chuyện &amp; Khai đơn</button>
            <button className={reviewTab ? "active" : ""} onClick={() => setReviewTab(true)}>📄 Rà soát &amp; Kiểm tra đơn</button>
          </div>
        </nav>
      </div>

      {reviewTab ? <main className="review-placeholder"><span aria-hidden="true">📄</span><h2>Rà soát đơn đang được chuẩn bị</h2><p>Tính năng kiểm tra biểu mẫu và tài liệu chính thức sẽ được bổ sung trong giai đoạn tiếp theo.</p><button onClick={() => setReviewTab(false)}>Quay lại trò chuyện</button></main> : <main className="conversation">
        {!isChatting ? <section className="welcome"><span className="mascot" aria-hidden="true">✦</span><h2>Xin chào! Tôi là <em>CIVI</em> 👋</h2><p>Tôi giúp bạn bắt đầu tìm hiểu thủ tục hành chính bằng ngôn ngữ tự nhiên.</p><form className="input-wrap welcome-input" onSubmit={submit}><input aria-label="Nội dung cần hỗ trợ" value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ví dụ: Tôi muốn đăng ký cho con vào lớp 1..." /><button aria-label="Gửi yêu cầu" type="submit">➤</button></form><div className="suggestions">{suggestions.map((item, index) => <button className={index === 0 ? "primary" : ""} key={item} onClick={() => void send(item)}>{item}</button>)}</div><p className="privacy">🔒 Nội dung chỉ được dùng trong phiên hiện tại.</p></section> : <><button className="back" onClick={() => void reset()}>← Bắt đầu phiên mới</button><section className="stream" ref={streamRef} data-testid="message-stream" aria-live="polite">{messages.map((message) => <article key={message.id} className={`message ${message.role}`}><div className="speaker">{message.role === "assistant" ? "✦ Trợ lý CIVI" : "Bạn"}</div><p>{message.content || ""}</p>{message.quickReplies && message.quickReplies.length > 0 && <div className="quick-replies">{message.quickReplies.map((reply) => <button key={reply} onClick={() => void send(reply)}>{reply}</button>)}</div>}</article>)}{streaming && <div className="typing" aria-label="CIVI đang trả lời"><i /><i /><i /></div>}</section><form className="input-bar" onSubmit={submit}><div className="input-wrap"><input aria-label="Nhập câu hỏi" value={input} onChange={(event) => setInput(event.target.value)} placeholder="Nhập câu trả lời hoặc đặt câu hỏi..." disabled={streaming} /><button aria-label="Gửi tin nhắn" type="submit" disabled={streaming}>➤</button></div></form></>}
      </main>}
    </div>
  );
}
