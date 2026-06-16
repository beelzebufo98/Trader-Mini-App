import type { TimeTick, TimelineSession, TradingSession } from "./types";
import { DAY_MS, HOUR_MS, localDayStartUtc, MINUTE_MS, pad, toOffsetDate } from "./time";

export const PX_PER_HOUR = 54;
export const TIMELINE_HOURS = 36;

export const sessions: TradingSession[] = [
  { name: "Asia", startMinuteUtcPlus3: 2 * 60, endMinuteUtcPlus3: 10 * 60, color: "#2f80ed" },
  { name: "Frankfurt", startMinuteUtcPlus3: 10 * 60, endMinuteUtcPlus3: 11 * 60, color: "#f2c94c" },
  { name: "London", startMinuteUtcPlus3: 11 * 60, endMinuteUtcPlus3: 16 * 60, color: "#27ae60" },
  { name: "New York", startMinuteUtcPlus3: 16 * 60, endMinuteUtcPlus3: 20 * 60, color: "#eb5757" },
  { name: "Overlap", startMinuteUtcPlus3: 20 * 60, endMinuteUtcPlus3: 26 * 60, color: "#9b51e0" }
];

function sessionRangeUtc(dayStartUtc: number, session: TradingSession) {
  const startUtc = dayStartUtc + (session.startMinuteUtcPlus3 - 3 * 60) * MINUTE_MS;
  const endUtc = dayStartUtc + (session.endMinuteUtcPlus3 - 3 * 60) * MINUTE_MS;

  return { startUtc, endUtc };
}

export function buildTimelineSessions(now: Date): TimelineSession[] {
  const centerTime = now.getTime();
  const currentUtcPlus3DayStart = localDayStartUtc(now, 3);
  const days = [-1, 0, 1, 2];

  return days.flatMap((dayOffset) =>
    sessions.map((session) => {
      const { startUtc, endUtc } = sessionRangeUtc(currentUtcPlus3DayStart + dayOffset * DAY_MS, session);
      const left = ((startUtc - centerTime) / HOUR_MS) * PX_PER_HOUR;
      const width = Math.max(18, ((endUtc - startUtc) / HOUR_MS) * PX_PER_HOUR);

      return {
        key: `${session.name}-${dayOffset}`,
        ...session,
        left,
        width
      };
    })
  );
}

export function buildTimeTicks(now: Date, utcOffset: number): TimeTick[] {
  const ticks: TimeTick[] = [];
  const rounded = Math.floor(now.getTime() / HOUR_MS) * HOUR_MS;

  for (let i = -18; i <= 18; i += 3) {
    const tickDate = new Date(rounded + i * HOUR_MS);
    const shifted = toOffsetDate(tickDate, utcOffset);
    ticks.push({
      key: i,
      left: ((tickDate.getTime() - now.getTime()) / HOUR_MS) * PX_PER_HOUR,
      label: `${pad(shifted.getUTCHours())}:00`
    });
  }

  return ticks;
}
