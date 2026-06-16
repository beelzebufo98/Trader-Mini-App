import { Bell, ChevronDown, Newspaper, Settings } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { fetchHighImpactEvents, fetchUserSettings, saveUserSettings } from "./api";
import { getMarketState } from "./marketState";
import { mockEvents } from "./mockEvents";
import { buildTimelineSessions, buildTimeTicks, TIMELINE_HOURS, PX_PER_HOUR } from "./sessions";
import { formatEventDate, formatTopTime, formatUtcLabel } from "./time";
import { timezoneOptions } from "./timezones";
import type { Impact, NewsEvent } from "./types";

const impactOptions: Impact[] = ["HIGH", "MEDIUM"];

export function App() {
  const [now, setNow] = useState(() => new Date());
  const [utcOffset, setUtcOffset] = useState(3);
  const [selectedImpacts, setSelectedImpacts] = useState<Impact[]>(["HIGH"]);
  const [events, setEvents] = useState<NewsEvent[]>(mockEvents);
  const [eventsStatus, setEventsStatus] = useState<"loading" | "ready" | "fallback" | "empty">("loading");
  const [settingsStatus, setSettingsStatus] = useState<"local" | "loading" | "synced" | "unavailable">("local");
  const [isTimezoneOpen, setTimezoneOpen] = useState(false);
  const [isNewsOpen, setNewsOpen] = useState(() => new URLSearchParams(window.location.search).get("news") === "1");
  const [isSettingsHintOpen, setSettingsHintOpen] = useState(false);

  useEffect(() => {
    window.Telegram?.WebApp?.ready();
    window.Telegram?.WebApp?.expand();
    window.Telegram?.WebApp?.setHeaderColor?.("#101113");
    window.Telegram?.WebApp?.setBackgroundColor?.("#101113");

    const timerId = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timerId);
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    async function loadSettings() {
      setSettingsStatus("loading");

      try {
        const settings = await fetchUserSettings(controller.signal);
        if (!settings) {
          setSettingsStatus("local");
          return;
        }

        setUtcOffset(settings.utc_offset);
        setSelectedImpacts(settings.impacts.length > 0 ? settings.impacts : ["HIGH"]);
        setSettingsStatus("synced");
      } catch (error) {
        if (controller.signal.aborted) return;
        setSettingsStatus("unavailable");
      }
    }

    loadSettings();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    async function loadEvents() {
      setEventsStatus("loading");

      try {
        const loadedEvents = await fetchHighImpactEvents(new Date(), utcOffset, selectedImpacts, controller.signal);
        setEvents(loadedEvents.length > 0 ? loadedEvents : []);
        setEventsStatus(loadedEvents.length > 0 ? "ready" : "empty");
      } catch (error) {
        if (controller.signal.aborted) return;

        setEvents(mockEvents);
        setEventsStatus("fallback");
      }
    }

    loadEvents();

    return () => controller.abort();
  }, [utcOffset, selectedImpacts]);

  async function updatePreferences(next: { utcOffset?: number; impacts?: Impact[] }) {
    const nextUtcOffset = next.utcOffset ?? utcOffset;
    const nextImpacts = next.impacts ?? selectedImpacts;

    setUtcOffset(nextUtcOffset);
    setSelectedImpacts(nextImpacts);

    try {
      const saved = await saveUserSettings({
        utc_offset: nextUtcOffset,
        impacts: nextImpacts
      });
      if (saved) setSettingsStatus("synced");
    } catch (error) {
      setSettingsStatus("unavailable");
    }
  }

  const marketState = useMemo(() => getMarketState(now, utcOffset), [now, utcOffset]);
  const timelineSessions = useMemo(() => buildTimelineSessions(now), [now]);
  const timeTicks = useMemo(() => buildTimeTicks(now, utcOffset), [now, utcOffset]);

  return (
    <main className="app-shell">
      <header className="top-bar">
        <button className="market-state" type="button" aria-label={marketState.label}>
          <span className={`market-dot ${marketState.tone}`} />
          <span>{marketState.label}</span>
        </button>

        <button className="icon-button" type="button" onClick={() => setSettingsHintOpen((value) => !value)}>
          <Settings size={18} />
        </button>
      </header>

      {isSettingsHintOpen && (
        <div className="settings-panel">
          <div className="settings-panel-row">
            <span>Impact</span>
            <div className="segmented-control">
              {impactOptions.map((impact) => {
                const isActive = selectedImpacts.includes(impact);
                return (
                  <button
                    className={isActive ? "segment active" : "segment"}
                    key={impact}
                    type="button"
                    onClick={() => {
                      const nextImpacts = isActive
                        ? selectedImpacts.filter((item) => item !== impact)
                        : [...selectedImpacts, impact];
                      updatePreferences({ impacts: nextImpacts.length > 0 ? nextImpacts : ["HIGH"] });
                    }}
                  >
                    {impact}
                  </button>
                );
              })}
            </div>
          </div>
          <div className={`settings-sync ${settingsStatus}`}>{settingsStatus === "synced" ? "Saved" : "Local"}</div>
        </div>
      )}

      <section className="time-panel" aria-label="Current time">
        <div className="time-readout">{formatTopTime(now, utcOffset)}</div>
        <div className="timezone-wrap">
          <button className="timezone-trigger" type="button" onClick={() => setTimezoneOpen((value) => !value)}>
            <span>{formatUtcLabel(utcOffset)}</span>
            <ChevronDown size={16} />
          </button>

          {isTimezoneOpen && (
            <div className="timezone-menu">
              {timezoneOptions.map((option) => (
                <button
                  className={option.offset === utcOffset ? "timezone-option active" : "timezone-option"}
                  key={option.offset}
                  type="button"
                  onClick={() => {
                    updatePreferences({ utcOffset: option.offset });
                    setTimezoneOpen(false);
                  }}
                >
                  <span>{`(${formatUtcLabel(option.offset)})`}</span>
                  <span>{option.label}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="timeline" aria-label="Trading sessions timeline">
        <div className="timeline-stage" style={{ width: `${TIMELINE_HOURS * PX_PER_HOUR}px` }}>
          {timelineSessions.map((session) => (
            <div
              className="session-band"
              key={session.key}
              style={{
                left: `calc(50% + ${session.left}px)`,
                width: `${session.width}px`,
                backgroundColor: session.color
              }}
            >
              <span>{session.name}</span>
              <small>session</small>
            </div>
          ))}

          {timeTicks.map((tick) => (
            <div className="time-tick" key={tick.key} style={{ left: `calc(50% + ${tick.left}px)` }}>
              <span />
              <small>{tick.label}</small>
            </div>
          ))}
        </div>

        <div className="now-line" />
        <div className="now-arrow" />

        <button className="news-toggle" type="button" onClick={() => setNewsOpen((value) => !value)}>
          <Newspaper size={22} />
        </button>

        {isNewsOpen && (
          <aside className="news-drawer" aria-label="High impact news">
            <div className="news-header">
              <Bell size={16} />
              <span>High impact news</span>
            </div>

            <div className={`news-status ${eventsStatus}`}>
              {eventsStatus === "loading" && "Loading events..."}
              {eventsStatus === "ready" && "Events updated"}
              {eventsStatus === "fallback" && "Showing sample events"}
              {eventsStatus === "empty" && "No selected events in the selected window"}
            </div>

            <div className="news-list">
              {events.map((event) => (
                <article className="news-card" key={event.id}>
                  <div>
                    <h2>{event.title}</h2>
                    <p>{event.currency} · {event.impact}</p>
                  </div>
                  <time>{formatEventDate(event.datetimeUtc, utcOffset)}</time>
                </article>
              ))}
            </div>
          </aside>
        )}
      </section>
    </main>
  );
}
