import { ArrowLeft, BarChart3, ChevronDown, Globe2, Zap } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { fetchUserSettings, saveUserSettings } from "./api";
import { resolveLanguage } from "./i18n";
import type { AppLanguage, MarketType } from "./types";

const languageOptions: AppLanguage[] = ["ru", "en", "es", "pt", "tr", "ar"];

const localStorageKeys = {
  market: "paradox_fx_market",
  language: "paradox_fx_language"
};

function readLocalMarket(): MarketType {
  return localStorage.getItem(localStorageKeys.market) === "OTC" ? "OTC" : "FOREX";
}

function readLocalLanguage(): AppLanguage {
  const value = localStorage.getItem(localStorageKeys.language) as AppLanguage | null;
  return value && ["ru", "en", "es", "pt", "tr", "ar"].includes(value) ? value : "ru";
}

export function App() {
  const { t, i18n } = useTranslation();
  const [market, setMarket] = useState<MarketType>(() => readLocalMarket());
  const [language, setLanguage] = useState<AppLanguage>(() => readLocalLanguage());
  const [screen, setScreen] = useState<"start" | "dashboard">("start");
  const [isLanguageOpen, setLanguageOpen] = useState(false);
  const [settingsStatus, setSettingsStatus] = useState<"local" | "synced" | "unavailable">("local");

  useEffect(() => {
    window.Telegram?.WebApp?.ready();
    window.Telegram?.WebApp?.expand();
    window.Telegram?.WebApp?.setHeaderColor?.("#05070a");
    window.Telegram?.WebApp?.setBackgroundColor?.("#05070a");
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    async function loadSettings() {
      try {
        const settings = await fetchUserSettings(controller.signal);
        if (!settings) return;

        setMarket(settings.market);
        setLanguage(settings.language === "auto" ? resolveLanguage("auto") : settings.language);
        setSettingsStatus("synced");
      } catch (error) {
        if (!controller.signal.aborted) setSettingsStatus("unavailable");
      }
    }

    loadSettings();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const resolved = resolveLanguage(language);
    i18n.changeLanguage(resolved);
    document.documentElement.dir = resolved === "ar" ? "rtl" : "ltr";
    localStorage.setItem(localStorageKeys.language, language);
  }, [i18n, language]);

  useEffect(() => {
    localStorage.setItem(localStorageKeys.market, market);
  }, [market]);

  async function persistSelection(nextMarket = market, nextLanguage = language) {
    localStorage.setItem(localStorageKeys.market, nextMarket);
    localStorage.setItem(localStorageKeys.language, nextLanguage);

    try {
      const saved = await saveUserSettings({
        market: nextMarket,
        language: nextLanguage
      });
      if (saved) setSettingsStatus("synced");
    } catch (error) {
      setSettingsStatus("unavailable");
    }
  }

  async function handleContinue() {
    await persistSelection();
    setScreen("dashboard");
  }

  function handleMarketChange(nextMarket: MarketType) {
    setMarket(nextMarket);
    persistSelection(nextMarket, language);
  }

  function handleLanguageChange(nextLanguage: AppLanguage) {
    setLanguage(nextLanguage);
    setLanguageOpen(false);
    persistSelection(market, nextLanguage);
  }

  if (screen === "dashboard") {
    return (
      <main className="paradox-shell">
        <section className="dashboard-card">
          <button className="back-button" type="button" onClick={() => setScreen("start")}>
            <ArrowLeft size={18} />
            <span>{t("dashboard.back")}</span>
          </button>

          <div className="brand-block compact">
            <span>PARADOX <strong>FX</strong></span>
            <small>{t("intro.eyebrow")}</small>
          </div>

          <div className="dashboard-status">{t("dashboard.status")}</div>
          <h1>{t("dashboard.title")}</h1>
          <p>{t("dashboard.subtitle", { market })}</p>

          <div className="summary-grid">
            <div>
              <span>{t("dashboard.market")}</span>
              <strong>{market}</strong>
            </div>
            <div>
              <span>{t("dashboard.language")}</span>
              <strong>{t(`languages.${language}`)}</strong>
            </div>
          </div>

          <div className="empty-state">
            <Zap size={22} />
            <h2>{t("dashboard.emptyTitle")}</h2>
            <p>{t("dashboard.emptyText")}</p>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="paradox-shell">
      <section className="hero-card">
        <div className="phone-top">
          <span />
          <div>
            <strong>Paradox FX</strong>
            <small>{t("intro.eyebrow")}</small>
          </div>
          <span />
        </div>

        <div className="hero-visual" aria-hidden="true">
          <div className="brand-block">
            <span>PARADOX <strong>FX</strong></span>
            <small>{t("intro.eyebrow")}</small>
          </div>
          <div className="mountain" />
          <div className="chart-line left" />
          <div className="chart-line right" />
          <div className="candle-set">
            <i />
            <i />
            <i />
            <i />
            <i />
          </div>
        </div>

        <div className="choice-panel">
          <h1>{t("intro.cardTitle")}</h1>
          <p>{t("intro.subtitle")}</p>

          <div className="market-options" aria-label={t("intro.marketTitle")}>
            <button
              className={market === "FOREX" ? "market-choice active" : "market-choice"}
              type="button"
              onClick={() => handleMarketChange("FOREX")}
            >
              <BarChart3 size={22} />
              <span>{t("intro.forex")}</span>
            </button>

            <button
              className={market === "OTC" ? "market-choice active otc" : "market-choice otc"}
              type="button"
              onClick={() => handleMarketChange("OTC")}
            >
              <Zap size={21} />
              <span>{t("intro.otc")}</span>
            </button>
          </div>

          <div className="language-row">
            <span>
              <Globe2 size={18} />
              {t("intro.languageTitle")}
            </span>
            <div className="language-select-wrap">
              <button
                className="language-trigger"
                type="button"
                onClick={() => setLanguageOpen((value) => !value)}
                aria-expanded={isLanguageOpen}
              >
                <span>{t(`languages.${language}`)}</span>
                <ChevronDown size={16} />
              </button>

              {isLanguageOpen && (
                <div className="language-menu">
                {languageOptions.map((option) => (
                  <button
                    className={option === language ? "language-option active" : "language-option"}
                    key={option}
                    type="button"
                    onClick={() => handleLanguageChange(option)}
                  >
                    {t(`languages.${option}`)}
                  </button>
                ))}
                </div>
              )}
            </div>
          </div>
        </div>

        <button className="continue-button" type="button" onClick={handleContinue}>
          <Zap size={18} />
          <span>{t("intro.continue")}</span>
        </button>

        <div className={`sync-pill ${settingsStatus}`}>{settingsStatus}</div>
      </section>
    </main>
  );
}
