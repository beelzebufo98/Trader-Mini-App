import type { ApiEventsResponse, Impact, NewsEvent, UserSettings } from "./types";
import { getTodayAndTomorrowWindowUtc } from "./time";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const TELEGRAM_INIT_DATA = window.Telegram?.WebApp?.initData ?? "";

function toApiDate(date: Date) {
  return date.toISOString();
}

function mapApiEvent(event: ApiEventsResponse["events"][number]): NewsEvent {
  return {
    id: String(event.id),
    title: event.title,
    currency: event.currency,
    impact: event.impact,
    datetimeUtc: event.datetime_utc
  };
}

function telegramHeaders(): Record<string, string> {
  return TELEGRAM_INIT_DATA ? { Authorization: `tma ${TELEGRAM_INIT_DATA}` } : {};
}

export async function fetchHighImpactEvents(
  now: Date,
  utcOffset: number,
  impacts: Impact[] = ["HIGH"],
  signal?: AbortSignal
): Promise<NewsEvent[]> {
  const { from, to } = getTodayAndTomorrowWindowUtc(now, utcOffset);
  const params = new URLSearchParams({
    from: toApiDate(from),
    to: toApiDate(to),
    impact: impacts.join(","),
    limit: "50"
  });

  const response = await fetch(`${API_BASE_URL}/api/v1/events/?${params.toString()}`, { signal });

  if (!response.ok) {
    throw new Error(`Events request failed: ${response.status}`);
  }

  const data = (await response.json()) as ApiEventsResponse;
  return data.events.filter((event) => impacts.includes(event.impact)).map(mapApiEvent);
}

export async function fetchUserSettings(signal?: AbortSignal): Promise<UserSettings | null> {
  if (!TELEGRAM_INIT_DATA) return null;

  const response = await fetch(`${API_BASE_URL}/api/v1/me/settings`, {
    headers: telegramHeaders(),
    signal
  });

  if (!response.ok) {
    throw new Error(`Settings request failed: ${response.status}`);
  }

  return (await response.json()) as UserSettings;
}

export async function saveUserSettings(payload: Partial<Pick<UserSettings, "utc_offset" | "impacts" | "currencies">>) {
  if (!TELEGRAM_INIT_DATA) return null;

  const response = await fetch(`${API_BASE_URL}/api/v1/me/settings`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...telegramHeaders()
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Settings save failed: ${response.status}`);
  }

  return (await response.json()) as UserSettings;
}
