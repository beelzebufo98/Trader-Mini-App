export type Impact = "HIGH" | "MEDIUM" | "LOW" | "HOLIDAY";
export type NewsWindow = "24H" | "48H" | "THIS_WEEK";
export type CurrencyCode = "USD" | "EUR" | "GBP" | "JPY" | "AUD" | "CAD" | "CHF" | "NZD";
export type AppLanguage = "auto" | "en" | "ru" | "es" | "pt" | "tr" | "ar";
export type MarketType = "FOREX" | "OTC";

export type UserSettings = {
  telegram_id: number;
  username?: string | null;
  first_name?: string | null;
  utc_offset: number;
  impacts: Impact[];
  currencies: string[];
  news_window: NewsWindow;
  language: AppLanguage;
  market: MarketType;
};
