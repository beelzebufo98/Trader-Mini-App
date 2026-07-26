import { ArrowLeft, BarChart3, ChevronDown, Clock3, Globe2, Repeat2, Search, Settings2, Star, Zap } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { fetchUserSettings, saveUserSettings } from "./api";
import { detectAppLanguage, resolveLanguage } from "./i18n";
import type { AppLanguage, MarketType } from "./types";

const languageOptions: AppLanguage[] = ["ru", "en", "es", "pt", "tr", "ar"];
const languageOptionValues = new Set<string>(languageOptions);
const forexPairs = [
  "GBP/JPY", "EUR/JPY", "AUD/CAD", "AUD/CHF", "AUD/JPY", "AUD/USD", "CAD/CHF", "CHF/JPY",
  "EUR/AUD", "EUR/CAD", "EUR/CHF", "EUR/USD", "GBP/AUD", "GBP/CAD", "GBP/CHF", "USD/CAD",
  "USD/CHF", "USD/JPY", "CAD/JPY", "EUR/GBP", "GBP/USD"
];
const otcPairs = [
  "AED/CNY OTC", "AUD/CAD OTC", "AUD/NZD OTC", "AUD/USD OTC", "BHD/CNY OTC", "CAD/CHF OTC",
  "CAD/JPY OTC", "CHF/JPY OTC", "CHF/NOK OTC", "EUR/CHF OTC", "EUR/NZD OTC", "EUR/TRY OTC",
  "JOD/CNY OTC", "KES/USD OTC", "NZD/USD OTC", "OMR/CNY OTC", "SAR/CNY OTC", "UAH/USD OTC",
  "USD/ARS OTC", "USD/BRL OTC", "USD/DZD OTC", "USD/EGP OTC", "USD/INR OTC", "USD/MXN OTC",
  "USD/MYR OTC", "USD/PKR OTC", "USD/VND OTC", "ZAR/USD OTC", "EUR/USD OTC", "MAD/USD OTC",
  "EUR/GBP OTC", "EUR/RUB OTC", "EUR/HUF OTC", "EUR/JPY OTC", "NGN/USD OTC", "TND/USD OTC",
  "USD/IDR OTC", "QAR/CNY OTC", "USD/CLP OTC", "USD/SGD OTC", "USD/PHP OTC", "USD/BDT OTC",
  "USD/CAD OTC", "USD/CHF OTC", "USD/THB OTC", "AUD/JPY OTC", "GBP/USD OTC", "GBP/AUD OTC",
  "USD/RUB OTC", "USD/COP OTC", "AUD/CHF OTC", "USD/CNH OTC", "USD/JPY OTC", "GBP/JPY OTC",
  "YER/USD OTC", "NZD/JPY OTC", "LBP/USD OTC"
];
const modelOptions = ["Paradox Classic", "Impulse", "Reversal", "Trend Flow"];
const expirationOptions = ["1 min", "3 min", "5 min", "15 min"];

const localStorageKeys = {
  market: "paradox_fx_market",
  language: "paradox_fx_language",
  languageManual: "paradox_fx_language_manual",
  favoritePairs: "paradox_fx_favorite_pairs"
};

function readLocalMarket(): MarketType {
  return localStorage.getItem(localStorageKeys.market) === "OTC" ? "OTC" : "FOREX";
}

function readLocalLanguage(): AppLanguage {
  if (localStorage.getItem(localStorageKeys.languageManual) !== "1") {
    return detectAppLanguage();
  }

  const value = localStorage.getItem(localStorageKeys.language) as AppLanguage | null;
  return normalizeLanguage(value);
}

function normalizeLanguage(value: unknown): AppLanguage {
  return typeof value === "string" && languageOptionValues.has(value) ? (value as AppLanguage) : "ru";
}

function normalizeMarket(value: unknown): MarketType {
  return value === "OTC" ? "OTC" : "FOREX";
}

export function App() {
  const { t, i18n } = useTranslation();
  const [market, setMarket] = useState<MarketType>(() => readLocalMarket());
  const [language, setLanguage] = useState<AppLanguage>(() => readLocalLanguage());
  const [screen, setScreen] = useState<"start" | "dashboard">("start");
  const [isLanguageOpen, setLanguageOpen] = useState(false);
  const [isMarketOpen, setMarketOpen] = useState(false);
  const [isPairOpen, setPairOpen] = useState(false);
  const [isModelOpen, setModelOpen] = useState(false);
  const [isExpirationOpen, setExpirationOpen] = useState(false);
  const [pairSearch, setPairSearch] = useState("");
  const [favoritePairs, setFavoritePairs] = useState<Set<string>>(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem(localStorageKeys.favoritePairs) || "[]"));
    } catch {
      return new Set();
    }
  });
  const [tradingPair, setTradingPair] = useState("");
  const [model, setModel] = useState("");
  const [expiration, setExpiration] = useState("");
  const [touchedFields, setTouchedFields] = useState<Set<string>>(() => new Set());
  const [signalStatus, setSignalStatus] = useState<"idle" | "invalid" | "generating" | "ready">("idle");
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

        setMarket(normalizeMarket(settings.market));
        if (localStorage.getItem(localStorageKeys.languageManual) === "1") {
          setLanguage(normalizeLanguage(settings.language === "auto" ? resolveLanguage("auto") : settings.language));
        } else {
          setLanguage(detectAppLanguage());
        }
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

  useEffect(() => {
    localStorage.setItem(localStorageKeys.favoritePairs, JSON.stringify([...favoritePairs]));
  }, [favoritePairs]);

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
    setTradingPair("");
    setPairSearch("");
    setMarketOpen(false);
    setPairOpen(false);
    persistSelection(nextMarket, language);
  }

  function handleLanguageChange(nextLanguage: AppLanguage) {
    const normalizedLanguage = normalizeLanguage(nextLanguage);
    setLanguage(normalizedLanguage);
    setLanguageOpen(false);
    localStorage.setItem(localStorageKeys.languageManual, "1");
    persistSelection(market, normalizedLanguage);
  }

  const languageLabel = t(`languages.${normalizeLanguage(language)}`);
  const isMarketMissing = !market;
  const isPairMissing = !tradingPair;
  const isModelMissing = !model;
  const isExpirationMissing = !expiration;
  const availablePairs = market === "OTC" ? otcPairs : forexPairs;
  const filteredPairs = availablePairs
    .filter((pair) => pair.toLowerCase().includes(pairSearch.trim().toLowerCase()))
    .sort((first, second) => Number(favoritePairs.has(second)) - Number(favoritePairs.has(first)));

  function markField(field: string) {
    setTouchedFields((current) => {
      const next = new Set(current);
      next.add(field);
      return next;
    });
  }

  function clearFieldError(field: string) {
    setTouchedFields((current) => {
      const next = new Set(current);
      next.delete(field);
      return next;
    });
  }

  function handlePairSelect(nextPair: string) {
    setTradingPair(nextPair);
    setPairOpen(false);
    setPairSearch("");
    clearFieldError("pair");
  }

  function handleModelSelect(nextModel: string) {
    setModel(nextModel);
    setModelOpen(false);
    clearFieldError("model");
  }

  function handleExpirationSelect(nextExpiration: string) {
    setExpiration(nextExpiration);
    setExpirationOpen(false);
    clearFieldError("expiration");
  }

  function toggleFavoritePair(pair: string) {
    setFavoritePairs((current) => {
      const next = new Set(current);
      if (next.has(pair)) {
        next.delete(pair);
      } else {
        next.add(pair);
      }
      return next;
    });
  }

  function handleGenerateSignal() {
    const missingFields = [
      ["market", isMarketMissing],
      ["pair", isPairMissing],
      ["model", isModelMissing],
      ["expiration", isExpirationMissing]
    ].filter(([, missing]) => missing).map(([field]) => String(field));

    if (missingFields.length > 0) {
      setTouchedFields(new Set(missingFields));
      setSignalStatus("invalid");
      return;
    }

    setSignalStatus("generating");
    window.setTimeout(() => setSignalStatus("ready"), 1100);
  }

  if (screen === "dashboard") {
    return (
      <main className="paradox-shell">
        <section className="dashboard-card">
          <button className="back-button" type="button" onClick={() => setScreen("start")}>
            <ArrowLeft size={18} />
            <span>{t("dashboard.back")}</span>
          </button>

          <div className="dashboard-title">
            <strong>Paradox FX</strong>
            <span>{t("intro.eyebrow")}</span>
          </div>

          <div className="signal-form">
            <div className="select-stack">
              <button
                className={market === "OTC" ? "market-select-card otc" : "market-select-card"}
                type="button"
                onClick={() => setMarketOpen((value) => !value)}
              >
                {market === "OTC" ? <Zap size={20} /> : <BarChart3 size={20} />}
                <span>{market === "OTC" ? t("intro.otc") : t("intro.forex")}</span>
                <ChevronDown size={18} />
              </button>

              {isMarketOpen && (
                <div className="option-menu compact">
                  <button
                    className={market === "FOREX" ? "option-row active" : "option-row"}
                    type="button"
                    onClick={() => handleMarketChange("FOREX")}
                  >
                    <BarChart3 size={17} />
                    <span>{t("intro.forex")}</span>
                  </button>
                  <button
                    className={market === "OTC" ? "option-row active" : "option-row"}
                    type="button"
                    onClick={() => handleMarketChange("OTC")}
                  >
                    <Zap size={17} />
                    <span>{t("intro.otc")}</span>
                  </button>
                </div>
              )}
            </div>

            <div className="form-info-row">
              <span>
                <Globe2 size={18} />
                {t("dashboard.language")}
              </span>
              <strong>{languageLabel}</strong>
            </div>

            <div className="pair-picker">
              <button
                className={touchedFields.has("pair") && isPairMissing ? "field-card invalid" : "field-card"}
                type="button"
                onClick={() => {
                  markField("pair");
                  setPairOpen((value) => !value);
                }}
              >
                <Repeat2 size={20} />
                <span>
                  <strong>{t("dashboard.pair")}</strong>
                  <small>{tradingPair || t("dashboard.pairPlaceholder")}</small>
                </span>
                <ChevronDown size={18} />
              </button>

              {isPairOpen && (
                <div className="pair-menu">
                  <label className="pair-search">
                    <Search size={16} />
                    <input
                      value={pairSearch}
                      onChange={(event) => setPairSearch(event.target.value)}
                      placeholder={t("dashboard.pairSearch")}
                    />
                  </label>

                  <div className="pair-list">
                    {filteredPairs.map((pair) => (
                      <button
                        className={pair === tradingPair ? "pair-option active" : "pair-option"}
                        key={pair}
                        type="button"
                        onClick={() => handlePairSelect(pair)}
                      >
                        <span>{pair}</span>
                        <span
                          className={favoritePairs.has(pair) ? "favorite-button active" : "favorite-button"}
                          role="button"
                          tabIndex={0}
                          onClick={(event) => {
                            event.stopPropagation();
                            toggleFavoritePair(pair);
                          }}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              event.stopPropagation();
                              toggleFavoritePair(pair);
                            }
                          }}
                          aria-label={`Favorite ${pair}`}
                        >
                          <Star size={17} />
                        </span>
                      </button>
                    ))}

                    {filteredPairs.length === 0 && <div className="pair-empty">{t("dashboard.noPairs")}</div>}
                  </div>
                </div>
              )}
            </div>

            <div className="select-stack">
              <button
                className={touchedFields.has("model") && isModelMissing ? "field-card invalid" : "field-card"}
                type="button"
                onClick={() => {
                  markField("model");
                  setModelOpen((value) => !value);
                }}
              >
                <Settings2 size={20} />
                <span>
                  <strong>{t("dashboard.model")}</strong>
                  <small>{model || t("dashboard.modelPlaceholder")}</small>
                </span>
                <ChevronDown size={18} />
              </button>

              {isModelOpen && (
                <div className="option-menu">
                  {modelOptions.map((option) => (
                    <button
                      className={model === option ? "option-row active" : "option-row"}
                      key={option}
                      type="button"
                      onClick={() => handleModelSelect(option)}
                    >
                      <Settings2 size={17} />
                      <span>{option}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="select-stack">
              <button
                className={touchedFields.has("expiration") && isExpirationMissing ? "field-card invalid" : "field-card"}
                type="button"
                onClick={() => {
                  markField("expiration");
                  setExpirationOpen((value) => !value);
                }}
              >
                <Clock3 size={20} />
                <span>
                  <strong>{t("dashboard.expiration")}</strong>
                  <small>{expiration || t("dashboard.expirationPlaceholder")}</small>
                </span>
                <ChevronDown size={18} />
              </button>

              {isExpirationOpen && (
                <div className="option-menu compact">
                  {expirationOptions.map((option) => (
                    <button
                      className={expiration === option ? "option-row active" : "option-row"}
                      key={option}
                      type="button"
                      onClick={() => handleExpirationSelect(option)}
                    >
                      <Clock3 size={17} />
                      <span>{option}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <button
              className={signalStatus === "generating" ? "continue-button signal-button generating" : "continue-button signal-button"}
              type="button"
              onClick={handleGenerateSignal}
            >
              <Zap size={18} />
              <span>{signalStatus === "generating" ? t("dashboard.generating") : t("dashboard.getSignal")}</span>
            </button>
          </div>

          {signalStatus === "invalid" && (
            <div className="validation-note invalid">
              <span>×</span>
              <strong>{t("dashboard.errorTitle")}</strong>
              <small>{t("dashboard.errorText")}</small>
            </div>
          )}

          {signalStatus === "ready" && (
            <div className="validation-note ready">
              <span>✓</span>
              <strong>{t("dashboard.readyTitle")}</strong>
              <small>{t("dashboard.readyText")}</small>
            </div>
          )}
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
                <span>{languageLabel}</span>
                <ChevronDown size={16} />
              </button>
            </div>
          </div>

          {isLanguageOpen && (
            <div className="language-menu">
              {languageOptions.map((option) => (
                <button
                  className={option === normalizeLanguage(language) ? "language-option active" : "language-option"}
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

        <button className="continue-button" type="button" onClick={handleContinue}>
          <Zap size={18} />
          <span>{t("intro.continue")}</span>
        </button>

        <div className={`sync-pill ${settingsStatus}`}>{settingsStatus}</div>
      </section>
    </main>
  );
}
