import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Citation, bootstrapSession, deleteSession, streamChat } from "./api";
import { copy, languages, Locale, suggestions } from "./i18n";
import { PrivacyPolicy } from "./PrivacyPolicy";
import { ReviewForm } from "./ReviewForm";
import { useRoute } from "./router";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  quickReplies?: string[];
  citations?: Citation[];
  confidenceBand?: "high" | "medium" | "low" | null;
  answerStrategy?: string;
  externalSearchConsentRequired?: boolean;
};
type PendingMessage = { content: string; translationConsent: boolean | null };
const id = () => crypto.randomUUID();

export function App() {
  const [route, goToRoute] = useRoute();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [language, setLanguage] = useState(() => {
    const saved = localStorage.getItem("icivi_locale") as Locale | null;
    return languages.find((item) => item.code === saved) ?? languages[0];
  });
  const [menuOpen, setMenuOpen] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [sessionReady, setSessionReady] = useState(true);
  const [switchingLanguage, setSwitchingLanguage] = useState(false);
  const [reviewTab, setReviewTab] = useState(false);
  const [activeFormCode, setActiveFormCode] = useState<string | null>(null);
  const [formCodePending, setFormCodePending] = useState(false);
  const [externalSearchConsent, setExternalSearchConsent] = useState<boolean | null>(null);
  const [translationConsent, setTranslationConsent] = useState<boolean | null>(null);
  const [pendingTranslation, setPendingTranslation] = useState<string | null>(null);
  const [translationProvider, setTranslationProvider] = useState("AI");
  const [notice, setNotice] = useState<string | null>(null);
  const [pendingMessage, setPendingMessage] = useState<PendingMessage | null>(null);
  const [pendingExternalSearchMessage, setPendingExternalSearchMessage] = useState<string | null>(null);
  const streamRef = useRef<HTMLDivElement>(null);
  const languageMenuRef = useRef<HTMLDivElement>(null);
  const bootstrappedRef = useRef(false);
  const isChatting = messages.length > 0;
  const text = copy[language.code];

  useEffect(() => {
    if (route !== "app" || bootstrappedRef.current) return;
    bootstrappedRef.current = true;
    void bootstrapSession().catch(() => setNotice(text.connectionError));
  }, [route]);

  useEffect(() => {
    const stream = streamRef.current;
    if (stream) stream.scrollTop = stream.scrollHeight;
  }, [messages, streaming]);

  useEffect(() => {
    localStorage.setItem("icivi_locale", language.code);
  }, [language.code]);

  useEffect(() => {
    if (!menuOpen) return;

    function closeWhenClickingOutside(event: PointerEvent) {
      if (!languageMenuRef.current?.contains(event.target as Node)) setMenuOpen(false);
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuOpen(false);
    }

    document.addEventListener("pointerdown", closeWhenClickingOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeWhenClickingOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [menuOpen]);

  async function requestTranslationConsent(message: string) {
    try {
      await streamChat(message, language.code, null, externalSearchConsent, (event) => {
        if (event.type === "translation.consent_required") {
          setTranslationProvider(event.provider);
          setPendingTranslation(message);
        }
      });
    } catch {
      setNotice(text.connectionError);
    }
  }

  async function send(textToSend = input, confirmedTranslationConsent = translationConsent) {
    const message = textToSend.trim();
    if (!message || streaming) return;
    if (!sessionReady) {
      setPendingMessage({ content: message, translationConsent: confirmedTranslationConsent });
      return;
    }
    if (language.code !== "vi" && confirmedTranslationConsent !== true) {
      await requestTranslationConsent(message);
      return;
    }
    const assistantId = id();
    setMessages((current) => [
      ...current,
      { id: id(), role: "user", content: message },
      { id: assistantId, role: "assistant", content: "" },
    ]);
    setInput("");
    setStreaming(true);
    try {
      await streamChat(message, language.code, confirmedTranslationConsent, externalSearchConsent, (event) => {
        if (event.type === "message.delta") {
          setMessages((current) => current.map((item) => item.id === assistantId ? { ...item, content: item.content + event.text } : item));
        }
        if (event.type === "message.complete") {
          setMessages((current) => current.map((item) => item.id === assistantId ? {
            ...item,
            quickReplies: event.quickReplies,
            citations: event.citations,
            confidenceBand: event.confidenceBand,
            answerStrategy: event.answerStrategy,
            externalSearchConsentRequired: event.externalSearchConsentRequired,
          } : item));
          if (event.externalSearchConsentRequired) setPendingExternalSearchMessage(message);
          if (event.formCode) {
            setActiveFormCode(event.formCode);
            setFormCodePending(true);
          }
        }
        if (event.type === "translation.consent_required") {
          setTranslationProvider(event.provider);
          setPendingTranslation(message);
        }
        if (event.type === "error") setMessages((current) => current.map((item) => item.id === assistantId ? { ...item, content: text.error } : item));
      });
    } catch (error) {
      const fallback = error instanceof Error ? error.message : text.error;
      setMessages((current) => current.map((item) => item.id === assistantId ? { ...item, content: fallback } : item));
    } finally {
      setStreaming(false);
    }
  }

  useEffect(() => {
    if (!sessionReady || !pendingMessage) return;
    setPendingMessage(null);
    void send(pendingMessage.content, pendingMessage.translationConsent);
  }, [sessionReady, pendingMessage]);

  function submit(event: FormEvent) {
    event.preventDefault();
    void send();
  }

  async function reset() {
    await deleteSession();
    await bootstrapSession();
    setMessages([]);
    setReviewTab(false);
    setActiveFormCode(null);
    setFormCodePending(false);
    setExternalSearchConsent(null);
    setTranslationConsent(null);
    setPendingExternalSearchMessage(null);
  }

  async function changeLanguage(nextLanguage: Locale) {
    if (nextLanguage === language.code || streaming || switchingLanguage) {
      setMenuOpen(false);
      return;
    }

    const selectedLanguage = languages.find((item) => item.code === nextLanguage);
    if (!selectedLanguage) return;

    setMenuOpen(false);
    setSwitchingLanguage(true);
    setSessionReady(false);
    setLanguage(selectedLanguage);
    setMessages([]);
    setInput("");
    setReviewTab(false);
    setActiveFormCode(null);
    setFormCodePending(false);
    setExternalSearchConsent(null);
    setTranslationConsent(null);
    setPendingTranslation(null);
    setTranslationProvider("AI");
    setPendingMessage(null);
    setPendingExternalSearchMessage(null);
    setNotice(null);
    try {
      await deleteSession();
      await bootstrapSession();
      setSessionReady(true);
    } catch {
      setNotice(copy[selectedLanguage.code].connectionError);
    } finally {
      setSwitchingLanguage(false);
    }
  }

  function allowTranslation() {
    setTranslationConsent(true);
    const message = pendingTranslation;
    setPendingTranslation(null);
    if (message) void send(message, true);
  }

  function declineTranslation() {
    setPendingTranslation(null);
    setNotice(text.translationDeclined);
  }

  const consumeActiveFormCode = useCallback(() => setFormCodePending(false), []);

  if (route === "privacy") {
    return (
      <PrivacyPolicy
        locale={language.code}
        languages={languages}
        onSelectLocale={setLanguage}
        onBack={() => goToRoute("app")}
      />
    );
  }

  return (
    <div className="app-shell">
      <div className="app-chrome">
        <header className="site-header">
          <div className="header-rail">
            <div className="brand">
              <span className="logo" aria-hidden="true">&#10022;</span>
              <div>
                <h1>ICIVI <span>· {text.product}</span></h1>
                <div className="meta-row">
                  <div className="language" ref={languageMenuRef}>
                    <button
                      aria-controls="language-menu"
                      aria-expanded={menuOpen}
                      aria-haspopup="listbox"
                      aria-label={`${text.selectLanguage}, ${language.label}`}
                      className="language-button"
                      onClick={() => setMenuOpen((open) => !open)}
                      disabled={streaming || switchingLanguage}
                      type="button"
                    >
                      <span className="language-current">{language.label}</span>
                      <svg aria-hidden="true" className="language-chevron" viewBox="0 0 16 16">
                        <path d="m4 6 4 4 4-4" />
                      </svg>
                    </button>
                    {menuOpen && <div aria-label={text.languageList} className="language-menu" id="language-menu" role="listbox">
                      {languages.map((item) => <button aria-selected={item.code === language.code} className={item.code === language.code ? "selected" : ""} key={item.code} onClick={() => void changeLanguage(item.code)} role="option" type="button"><span className="language-code">{item.code}</span>{item.label}</button>)}
                    </div>}
                  </div>
                  <span className="status">{text.online}</span>
                </div>
              </div>
            </div>
            <div className="session-meta">{text.session}: #ADM-8829<br /><strong>{text.sessionStatus}</strong></div>
          </div>
        </header>

        <nav className="tabs" aria-label="ICIVI">
          <div className="tabs-line">
            <div className="tabs-rail">
              <button className={!reviewTab ? "active" : ""} onClick={() => setReviewTab(false)}>💬 {text.chat}</button>
              <button className={reviewTab ? "active" : ""} onClick={() => setReviewTab(true)}>📄 {text.review}{formCodePending && <span className="tab-badge" aria-label={text.newForm} />}</button>
            </div>
            <a
              className="privacy-link"
              href="/privacy"
              onClick={(event) => {
                event.preventDefault();
                goToRoute("privacy");
              }}
            >
              {text.privacyLinkLabel}
            </a>
          </div>
        </nav>
      </div>

      {reviewTab ? <main className="review-panel"><ReviewForm activeFormCode={activeFormCode} locale={language.code} onFormCodeConsumed={consumeActiveFormCode} /></main> : <main className="conversation">
        {!isChatting ? <section className="welcome"><span className="mascot" aria-hidden="true">✦</span><h2>{text.welcome} <em>ICIVI</em> 👋</h2><p>{text.welcomeBody}</p><form className="input-wrap welcome-input" onSubmit={submit}><input aria-label={text.send} value={input} onChange={(event) => setInput(event.target.value)} placeholder={text.welcomeInput} /><button aria-label={text.send} type="submit">➤</button></form><div className="suggestions">{suggestions(language.code).map((item, index) => <button className={index === 0 ? "primary" : ""} key={item} onClick={() => void send(item)}>{item}</button>)}</div>{notice && <p className="notice" role="status">{notice}</p>}<p className="privacy">🔒 {text.privacy}</p></section> : <><button className="back" onClick={() => void reset()}>← {text.newSession}</button><section className="stream" ref={streamRef} data-testid="message-stream" aria-live="polite">{messages.map((message) => <article key={message.id} className={`message ${message.role}`}><div className="speaker">{message.role === "assistant" ? `✦ ${text.assistant}` : text.you}</div><p>{message.content || ""}</p>{message.confidenceBand && <p className={`confidence ${message.confidenceBand}`}>{text.confidence}: {text[message.confidenceBand]}</p>}{message.citations && message.citations.length > 0 && <ol className="citations" aria-label={text.citations}>{message.citations.map((citation) => <li key={citation.citation_id}><strong>[{citation.citation_id}]</strong> {citation.source_status === "snapshot" ? text.snapshot : text.verified} {citation.source_url ? <a href={citation.source_url} rel="noreferrer" target="_blank">{citation.source_title}</a> : citation.source_title}{citation.procedure_code ? ` (${text.sourceCode} ${citation.procedure_code})` : ""}{citation.document_number ? ` — ${citation.document_number}` : ""}{citation.section_reference ? ` — ${citation.section_reference}` : ""}{citation.crawled_at ? ` — ${new Date(citation.crawled_at).toLocaleDateString(language.dateLocale)}` : ""}</li>)}</ol>}{message.externalSearchConsentRequired && pendingExternalSearchMessage && <button onClick={() => { setExternalSearchConsent(true); setPendingExternalSearchMessage(null); void send(pendingExternalSearchMessage); }}>{text.externalSearch}</button>}{message.quickReplies && message.quickReplies.length > 0 && <div className="quick-replies">{message.quickReplies.map((reply) => <button key={reply} onClick={() => void send(reply)}>{reply}</button>)}</div>}</article>)}{streaming && <div className="typing" aria-label={text.typing}><i /><i /><i /></div>}</section><form className="input-bar" onSubmit={submit}><div className="input-wrap"><input aria-label={text.input} value={input} onChange={(event) => setInput(event.target.value)} placeholder={text.input} disabled={streaming} /><button aria-label={text.send} type="submit" disabled={streaming}>➤</button></div></form></>}
      </main>}
      {pendingTranslation && <div className="consent-backdrop" role="presentation"><section aria-labelledby="translation-title" aria-modal="true" className="consent-dialog" role="dialog"><h2 id="translation-title">{text.translationTitle}</h2><p>{text.translationBody.replace("{provider}", translationProvider)}</p><div><button onClick={declineTranslation} type="button">{text.decline}</button><button className="primary" onClick={allowTranslation} type="button">{text.allow}</button></div></section></div>}
    </div>
  );
}
