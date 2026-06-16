import type { MarketState } from "./types";
import { toOffsetDate } from "./time";

export function getMarketState(now: Date, utcOffset: number): MarketState {
  const shifted = toOffsetDate(now, utcOffset);
  const weekday = shifted.getUTCDay();
  const minutes = shifted.getUTCHours() * 60 + shifted.getUTCMinutes();

  if (weekday === 0 || weekday === 6) {
    return { label: "Market closed (weekend)", tone: "gray" };
  }

  if (minutes >= 10 * 60 && minutes < 18 * 60) {
    return { label: "Market - Tradable", tone: "green" };
  }

  return { label: "Market - Not tradable (low liquidity)", tone: "red" };
}
