import type { UserSettings } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const TELEGRAM_INIT_DATA = window.Telegram?.WebApp?.initData ?? "";

function telegramHeaders(): Record<string, string> {
  return TELEGRAM_INIT_DATA ? { Authorization: `tma ${TELEGRAM_INIT_DATA}` } : {};
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

export async function saveUserSettings(
  payload: Partial<Pick<UserSettings, "utc_offset" | "impacts" | "currencies" | "news_window" | "language" | "market">>
) {
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
