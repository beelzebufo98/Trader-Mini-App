export type MarketState = {
  label: string;
  tone: "green" | "red" | "gray";
};

export type TradingSession = {
  name: string;
  startMinuteUtcPlus3: number;
  endMinuteUtcPlus3: number;
  color: string;
};

export type TimelineSession = TradingSession & {
  key: string;
  left: number;
  width: number;
};

export type TimeTick = {
  key: number;
  left: number;
  label: string;
};

export type TimezoneOption = {
  offset: number;
  label: string;
};

export type NewsEvent = {
  id: string;
  title: string;
  currency: string;
  impact: Impact;
  datetimeUtc: string;
};

export type Impact = "HIGH" | "MEDIUM" | "LOW" | "HOLIDAY";

export type ApiEconomicEvent = {
  id: number | string;
  title: string;
  currency: string;
  impact: Impact;
  datetime_utc: string;
  is_all_day: boolean;
};

export type ApiEventsResponse = {
  events: ApiEconomicEvent[];
};

export type UserSettings = {
  telegram_id: number;
  username?: string | null;
  first_name?: string | null;
  utc_offset: number;
  impacts: Impact[];
  currencies: string[];
};
