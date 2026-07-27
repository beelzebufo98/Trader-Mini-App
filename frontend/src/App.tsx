import {
  ArrowLeft,
  ArrowUpRight,
  BarChart3,
  Check,
  ChevronDown,
  Clock3,
  Globe2,
  Repeat2,
  RotateCcw,
  Search,
  Settings2,
  Star,
  TrendingDown,
  Zap
} from "lucide-react";
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
const modelOptions = ["AI Target", "FVG Imbalance", "Fractals", "Fibonacci", "RSI Model", "MACD Model"];
const expirationOptions = [
  { value: "1", shortLabel: "1m" },
  { value: "3", shortLabel: "3m" },
  { value: "5", shortLabel: "5m" },
  { value: "15", shortLabel: "15m" },
  { value: "30", shortLabel: "30m" }
];
const modelConfidenceFloor: Record<string, number> = {
  "AI Target": 82,
  "FVG Imbalance": 78,
  Fractals: 76,
  Fibonacci: 75,
  "RSI Model": 77,
  "MACD Model": 79
};
const analysisStages = [
  "\u0410\u043d\u0430\u043b\u0438\u0437 \u0440\u044b\u043d\u043a\u0430",
  "\u041f\u043e\u0438\u0441\u043a \u0441\u0435\u0442\u0430\u043f\u043e\u0432",
  "\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u043c\u043e\u0434\u0435\u043b\u0438",
  "\u0420\u0430\u0441\u0447\u0435\u0442 \u0432\u0435\u0440\u043e\u044f\u0442\u043d\u043e\u0441\u0442\u0438",
  "\u0424\u043e\u0440\u043c\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435 \u0441\u0438\u0433\u043d\u0430\u043b\u0430"
];

type SignalResult = {
  confidence: number;
  direction: "CALL" | "PUT";
  createdAt: string;
};

const localStorageKeys = {
  market: "paradox_fx_market",
  language: "paradox_fx_language",
  languageManual: "paradox_fx_language_manual",
  languageVersion: "paradox_fx_language_version",
  favoritePairs: "paradox_fx_favorite_pairs"
};

const languagePreferenceVersion = "2";

function readLocalMarket(): MarketType {
  return localStorage.getItem(localStorageKeys.market) === "OTC" ? "OTC" : "FOREX";
}

function readLocalLanguage(): AppLanguage {
  const hasCurrentManualPreference =
    localStorage.getItem(localStorageKeys.languageManual) === "1" &&
    localStorage.getItem(localStorageKeys.languageVersion) === languagePreferenceVersion;

  if (!hasCurrentManualPreference) {
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
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [analysisStageIndex, setAnalysisStageIndex] = useState(0);
  const [signalResult, setSignalResult] = useState<SignalResult | null>(null);
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
        const hasCurrentManualPreference =
          localStorage.getItem(localStorageKeys.languageManual) === "1" &&
          localStorage.getItem(localStorageKeys.languageVersion) === languagePreferenceVersion;

        if (settings.language && settings.language !== "auto") {
          setLanguage(normalizeLanguage(settings.language));
        } else if (hasCurrentManualPreference) {
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

  useEffect(() => {
    if (signalStatus !== "generating") return;

    const startedAt = Date.now();
    const durationMs = 3600;
    const progressTimer = window.setInterval(() => {
      const elapsed = Date.now() - startedAt;
      const progress = Math.min(99, Math.round((elapsed / durationMs) * 100));
      setAnalysisProgress(progress);
      setAnalysisStageIndex(Math.min(analysisStages.length - 1, Math.floor((progress / 100) * analysisStages.length)));
    }, 90);

    return () => window.clearInterval(progressTimer);
  }, [signalStatus]);

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
    resetSignalResult();
    persistSelection(nextMarket, language);
  }

  function handleLanguageChange(nextLanguage: AppLanguage) {
    const normalizedLanguage = normalizeLanguage(nextLanguage);
    setLanguage(normalizedLanguage);
    setLanguageOpen(false);
    localStorage.setItem(localStorageKeys.languageManual, "1");
    localStorage.setItem(localStorageKeys.languageVersion, languagePreferenceVersion);
    persistSelection(market, normalizedLanguage);
  }

  const languageLabel = t(`languages.${normalizeLanguage(language)}`);
  const isMarketMissing = !market;
  const isPairMissing = !tradingPair;
  const isModelMissing = !model;
  const isExpirationMissing = !expiration;
  const isSignalReady = !isMarketMissing && !isPairMissing && !isModelMissing && !isExpirationMissing;
  const availablePairs = market === "OTC" ? otcPairs : forexPairs;
  const filteredPairs = availablePairs
    .filter((pair) => pair.toLowerCase().includes(pairSearch.trim().toLowerCase()))
    .sort((first, second) => Number(favoritePairs.has(second)) - Number(favoritePairs.has(first)));
  const selectedExpiration = expirationOptions.find((option) => option.value === expiration);

  function getExpirationLabel(minutes: string) {
    const languageCode = resolveLanguage(language);
    if (languageCode === "ru") {
      if (minutes === "1") return "1 \u043c\u0438\u043d\u0443\u0442\u0430";
      if (minutes === "3") return "3 \u043c\u0438\u043d\u0443\u0442\u044b";
      if (minutes === "5") return "5 \u043c\u0438\u043d\u0443\u0442";
      if (minutes === "15") return "15 \u043c\u0438\u043d\u0443\u0442";
      if (minutes === "30") return "30 \u043c\u0438\u043d\u0443\u0442";
    }
    return `${minutes} min`;
  }

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

  function resetSignalResult() {
    setSignalStatus("idle");
    setAnalysisProgress(0);
    setAnalysisStageIndex(0);
    setSignalResult(null);
  }

  function handlePairSelect(nextPair: string) {
    setTradingPair(nextPair);
    setPairOpen(false);
    setPairSearch("");
    clearFieldError("pair");
    resetSignalResult();
  }

  function handleModelSelect(nextModel: string) {
    setModel(nextModel);
    setModelOpen(false);
    clearFieldError("model");
    resetSignalResult();
  }

  function handleExpirationSelect(nextExpiration: string) {
    setExpiration(nextExpiration);
    setExpirationOpen(false);
    clearFieldError("expiration");
    resetSignalResult();
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
    if (signalStatus === "generating") return;

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

    const confidenceFloor = modelConfidenceFloor[model] ?? 75;
    const confidence = confidenceFloor + Math.floor(Math.random() * (101 - confidenceFloor));
    const direction = Math.random() > 0.5 ? "CALL" : "PUT";

    setPairOpen(false);
    setModelOpen(false);
    setExpirationOpen(false);
    setSignalResult(null);
    setAnalysisProgress(0);
    setAnalysisStageIndex(0);
    setSignalStatus("generating");
    window.setTimeout(() => {
      setAnalysisProgress(100);
      setAnalysisStageIndex(analysisStages.length - 1);
      setSignalResult({
        confidence,
        direction,
        createdAt: new Date().toLocaleTimeString(resolveLanguage(language), {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit"
        })
      });
      setSignalStatus("ready");
    }, 3600);
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
                <div className="model-list">
                  {modelOptions.map((option) => (
                    <button
                      className={model === option ? "model-option active" : "model-option"}
                      key={option}
                      type="button"
                      onClick={() => handleModelSelect(option)}
                    >
                      <Settings2 size={17} />
                      <span>{option}</span>
                      <i />
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
                  <small>{selectedExpiration ? getExpirationLabel(selectedExpiration.value) : t("dashboard.expirationPlaceholder")}</small>
                </span>
                <ChevronDown size={18} />
              </button>

              {isExpirationOpen && (
                <div className="expiration-grid">
                  {expirationOptions.map((option) => (
                    <button
                      className={expiration === option.value ? "expiration-option active" : "expiration-option"}
                      key={option.value}
                      type="button"
                      onClick={() => handleExpirationSelect(option.value)}
                    >
                      <strong>{option.shortLabel}</strong>
                      <span>{getExpirationLabel(option.value)}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <button
              className={[
                "continue-button",
                "signal-button",
                isSignalReady ? "ready" : "pending",
                signalStatus === "generating" ? "generating" : ""
              ].join(" ")}
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

          {signalStatus === "generating" && (
            <div className="analysis-panel">
              <div className="analysis-radar">
                <span className="radar-ring" />
                <span className="radar-ring second" />
                <span className="radar-ring third" />
                <strong>{analysisProgress}%</strong>
                <small>{analysisStages[analysisStageIndex]}</small>
              </div>
              <p>{"\u0410\u043d\u0430\u043b\u0438\u0437\u0438\u0440\u0443\u0435\u043c \u0434\u0430\u043d\u043d\u044b\u0435 \u0440\u044b\u043d\u043a\u0430"}<br />{"\u0438 \u0438\u0449\u0435\u043c \u043b\u0443\u0447\u0448\u0438\u0435 \u0442\u043e\u0447\u043a\u0438 \u0432\u0445\u043e\u0434\u0430..."}</p>
              <div className="analysis-bars" aria-hidden="true">
                {analysisStages.map((stage, index) => (
                  <span className={index <= analysisStageIndex ? "active" : ""} key={stage} />
                ))}
              </div>
            </div>
          )}

          {signalStatus === "ready" && signalResult && (
            <div className={signalResult.direction === "CALL" ? "result-panel call" : "result-panel put"}>
              <div className="result-heading">
                <Check size={18} />
                <strong>{"\u0421\u0438\u0433\u043d\u0430\u043b \u0433\u043e\u0442\u043e\u0432"}</strong>
              </div>
              <p>{tradingPair} · {selectedExpiration?.shortLabel} · {model}</p>

              <div className="direction-card">
                {signalResult.direction === "CALL" ? <ArrowUpRight size={58} /> : <TrendingDown size={58} />}
                <span>
                  <strong>{signalResult.direction === "CALL" ? "\u0412\u0432\u0435\u0440\u0445" : "\u0412\u043d\u0438\u0437"}</strong>
                  <small>{signalResult.direction}</small>
                </span>
              </div>

              <div className="confidence-row">
                <span>{"\u0423\u0432\u0435\u0440\u0435\u043d\u043d\u043e\u0441\u0442\u044c"}</span>
                <strong>{signalResult.confidence}%</strong>
              </div>
              <div className="confidence-track">
                <span style={{ width: `${signalResult.confidence}%` }} />
              </div>

              <div className="result-time">
                <Clock3 size={17} />
                <span>{signalResult.createdAt}</span>
              </div>

              <button className="reset-signal-button" type="button" onClick={resetSignalResult}>
                <RotateCcw size={17} />
                <span>{"\u0421\u0431\u0440\u043e\u0441\u0438\u0442\u044c \u0441\u0438\u0433\u043d\u0430\u043b"}</span>
              </button>
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
