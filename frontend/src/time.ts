export const HOUR_MS = 60 * 60 * 1000;
export const MINUTE_MS = 60 * 1000;
export const DAY_MS = 24 * HOUR_MS;

export function pad(value: number) {
  return String(value).padStart(2, "0");
}

export function formatUtcLabel(offset: number) {
  if (offset === 0) return "UTC";
  return `UTC${offset > 0 ? "+" : ""}${offset}`;
}

export function toOffsetDate(date: Date, utcOffset: number) {
  return new Date(date.getTime() + utcOffset * HOUR_MS);
}

export function formatTopTime(now: Date, utcOffset: number) {
  const shifted = toOffsetDate(now, utcOffset);
  const weekday = shifted.toLocaleDateString("en-US", { weekday: "long", timeZone: "UTC" });

  return `${pad(shifted.getUTCHours())}:${pad(shifted.getUTCMinutes())}:${pad(shifted.getUTCSeconds())} ${formatUtcLabel(
    utcOffset
  )} | ${pad(shifted.getUTCDate())}/${pad(shifted.getUTCMonth() + 1)}/${shifted.getUTCFullYear()} ${weekday}`;
}

export function formatEventDate(datetimeUtc: string, utcOffset: number) {
  const shifted = toOffsetDate(new Date(datetimeUtc), utcOffset);
  return `${pad(shifted.getUTCDate())}/${pad(shifted.getUTCMonth() + 1)}/${shifted.getUTCFullYear()} ${pad(
    shifted.getUTCHours()
  )}:${pad(shifted.getUTCMinutes())}`;
}

export function localDayStartUtc(date: Date, utcOffset: number) {
  const shifted = toOffsetDate(date, utcOffset);
  return Date.UTC(shifted.getUTCFullYear(), shifted.getUTCMonth(), shifted.getUTCDate()) - utcOffset * HOUR_MS;
}

export function getTodayAndTomorrowWindowUtc(date: Date, utcOffset: number) {
  const start = localDayStartUtc(date, utcOffset);

  return {
    from: new Date(start),
    to: new Date(start + 2 * DAY_MS - 1)
  };
}

export function getEventsWindowUtc(date: Date, utcOffset: number, window: "24H" | "48H" | "THIS_WEEK") {
  if (window === "24H") {
    return {
      from: date,
      to: new Date(date.getTime() + DAY_MS)
    };
  }

  if (window === "48H") {
    return {
      from: date,
      to: new Date(date.getTime() + 2 * DAY_MS)
    };
  }

  const dayStart = localDayStartUtc(date, utcOffset);
  const shifted = toOffsetDate(date, utcOffset);
  const mondayOffset = (shifted.getUTCDay() + 6) % 7;
  const weekStart = dayStart - mondayOffset * DAY_MS;

  return {
    from: new Date(weekStart),
    to: new Date(weekStart + 7 * DAY_MS - 1)
  };
}
