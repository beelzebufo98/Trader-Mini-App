import { useEffect, useMemo, useRef } from "react";
import type { AppLanguage } from "./types";

declare global {
  interface Window {
    TradingView?: {
      widget: new (config: Record<string, unknown>) => unknown;
    };
  }
}

const tradingViewScriptId = "tradingview-widget-script";

function toTradingViewSymbol(pair: string) {
  const normalized = pair.replace(/\s+OTC$/i, "").replace("/", "").trim().toUpperCase();
  return normalized ? `FX:${normalized}` : "FX:EURUSD";
}

function toTradingViewLocale(language: AppLanguage) {
  if (language === "ru") return "ru";
  if (language === "es") return "es";
  if (language === "pt") return "br";
  if (language === "tr") return "tr";
  if (language === "ar") return "ar_AE";
  return "en";
}

type TradingViewWidgetProps = {
  pair: string;
  language: AppLanguage;
};

export function TradingViewWidget({ pair, language }: TradingViewWidgetProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const containerId = useMemo(() => `tradingview_${Math.random().toString(36).slice(2)}`, []);
  const symbol = useMemo(() => toTradingViewSymbol(pair), [pair]);

  useEffect(() => {
    let isMounted = true;

    function renderWidget() {
      if (!isMounted || !window.TradingView || !containerRef.current) return;

      containerRef.current.innerHTML = "";
      const widgetRoot = document.createElement("div");
      widgetRoot.id = containerId;
      widgetRoot.className = "tradingview-widget-container__widget";
      containerRef.current.appendChild(widgetRoot);

      new window.TradingView.widget({
        autosize: true,
        symbol,
        interval: "1",
        timezone: "Etc/UTC",
        theme: "dark",
        style: "1",
        locale: toTradingViewLocale(language),
        enable_publishing: false,
        allow_symbol_change: true,
        hide_side_toolbar: false,
        withdateranges: true,
        details: true,
        hotlist: false,
        calendar: false,
        support_host: "https://www.tradingview.com",
        container_id: containerId
      });
    }

    if (window.TradingView) {
      renderWidget();
    } else {
      let script = document.getElementById(tradingViewScriptId) as HTMLScriptElement | null;
      if (!script) {
        script = document.createElement("script");
        script.id = tradingViewScriptId;
        script.src = "https://s3.tradingview.com/tv.js";
        script.async = true;
        document.body.appendChild(script);
      }

      script.addEventListener("load", renderWidget);
      return () => {
        isMounted = false;
        script?.removeEventListener("load", renderWidget);
        if (containerRef.current) containerRef.current.innerHTML = "";
      };
    }

    return () => {
      isMounted = false;
      if (containerRef.current) containerRef.current.innerHTML = "";
    };
  }, [containerId, language, symbol]);

  return <div className="tradingview-widget-container" ref={containerRef} />;
}
