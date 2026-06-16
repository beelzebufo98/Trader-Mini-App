import type { ApiEventsResponse, NewsEvent } from "./types";
import { getTodayAndTomorrowWindowUtc } from "./time";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function toApiDate(date: Date) {
  return date.toISOString();
}

function mapApiEvent(event: ApiEventsResponse["events"][number]): NewsEvent {
  return {
    id: String(event.id),
    title: event.title,
    currency: event.currency,
    impact: "HIGH",
    datetimeUtc: event.datetime_utc
  };
}

export async function fetchHighImpactEvents(now: Date, utcOffset: number, signal?: AbortSignal): Promise<NewsEvent[]> {
  const { from, to } = getTodayAndTomorrowWindowUtc(now, utcOffset);
  const params = new URLSearchParams({
    from: toApiDate(from),
    to: toApiDate(to),
    impact: "HIGH",
    limit: "20"
  });

  const response = await fetch(`${API_BASE_URL}/api/v1/events/?${params.toString()}`, { signal });

  if (!response.ok) {
    throw new Error(`Events request failed: ${response.status}`);
  }

  const data = (await response.json()) as ApiEventsResponse;
  return data.events.filter((event) => event.impact === "HIGH").map(mapApiEvent);
}
