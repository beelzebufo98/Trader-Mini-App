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
  impact: "HIGH";
  datetimeUtc: string;
};

export type ApiEconomicEvent = {
  id: number | string;
  title: string;
  currency: string;
  impact: "HIGH" | "MEDIUM" | "LOW" | "HOLIDAY";
  datetime_utc: string;
  is_all_day: boolean;
};

export type ApiEventsResponse = {
  events: ApiEconomicEvent[];
};
