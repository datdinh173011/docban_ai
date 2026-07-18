import { useEffect, useRef, useState } from "react";
import { copy, Language, Locale } from "./i18n";
import { privacyContent, privacyIntro, privacyMeta } from "./privacyContent";

type Props = {
  locale: Locale;
  languages: Language[];
  onSelectLocale: (language: Language) => void;
  onBack: () => void;
};

export function PrivacyPolicy({ locale, languages, onSelectLocale, onBack }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const text = copy[locale];
  const currentLanguage = languages.find((item) => item.code === locale) ?? languages[0];

  useEffect(() => {
    if (!menuOpen) return;

    function closeWhenClickingOutside(event: PointerEvent) {
      if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false);
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

  return (
    <div className="app-shell">
      <div className="app-chrome">
        <header className="site-header">
          <div className="header-rail">
            <div className="brand">
              <span className="logo" aria-hidden="true">&#10022;</span>
              <div>
                <h1>ICIVI <span>· {text.privacyPageTitle}</span></h1>
                <div className="meta-row">
                  <div className="language" ref={menuRef}>
                    <button
                      aria-controls="privacy-language-menu"
                      aria-expanded={menuOpen}
                      aria-haspopup="listbox"
                      aria-label={`${text.selectLanguage}, ${currentLanguage.label}`}
                      className="language-button"
                      onClick={() => setMenuOpen((open) => !open)}
                      type="button"
                    >
                      <span className="language-current">{currentLanguage.label}</span>
                      <svg aria-hidden="true" className="language-chevron" viewBox="0 0 16 16">
                        <path d="m4 6 4 4 4-4" />
                      </svg>
                    </button>
                    {menuOpen && (
                      <div aria-label={text.languageList} className="language-menu" id="privacy-language-menu" role="listbox">
                        {languages.map((item) => (
                          <button
                            aria-selected={item.code === locale}
                            className={item.code === locale ? "selected" : ""}
                            key={item.code}
                            onClick={() => {
                              onSelectLocale(item);
                              setMenuOpen(false);
                            }}
                            role="option"
                            type="button"
                          >
                            <span className="language-code">{item.code}</span>
                            {item.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
            <a
              className="back-to-chat-link"
              href="/"
              onClick={(event) => {
                event.preventDefault();
                onBack();
              }}
            >
              ← {text.backToChat}
            </a>
          </div>
        </header>
      </div>

      <main className="privacy-content">
        <h2>{text.privacyDocTitle}</h2>
        <p className="privacy-updated">{text.privacyUpdatedLabel}: {privacyMeta.lastUpdated}</p>
        {privacyIntro[locale].map((paragraph, index) => <p key={index}>{paragraph}</p>)}
        {privacyContent[locale].map((section) => (
          <section key={section.heading}>
            <h3>{section.heading}</h3>
            {section.blocks.map((block, index) =>
              "items" in block ? (
                <ul key={index}>
                  {block.items.map((item, itemIndex) => <li key={itemIndex}>{item}</li>)}
                </ul>
              ) : (
                <p key={index}>{block.text}</p>
              ),
            )}
          </section>
        ))}
      </main>
    </div>
  );
}
