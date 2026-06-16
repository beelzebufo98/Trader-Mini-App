import { Bell, ChevronDown, Newspaper, Settings, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { fetchHighImpactEvents, fetchUserSettings, saveUserSettings } from "./api";
import { getMarketState } from "./marketState";
import { mockEvents } from "./mockEvents";
import { buildTimelineSessions, buildTimeTicks, TIMELINE_HOURS, PX_PER_HOUR } from "./sessions";
import { formatEventDate, formatTopTime, formatUtcLabel, HOUR_MS } from "./time";
import { timezoneOptions } from "./timezones";
import type { CurrencyCode, Impact, NewsEvent, NewsWindow } from "./types";

const impactOptions: Impact[] = ["HIGH", "MEDIUM", "LOW"];
const currencyOptions: CurrencyCode[] = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"];
const newsWindowOptions: { value: NewsWindow; label: string }[] = [
  { value: "24H", label: "24h" },
  { value: "48H", label: "48h" },
  { value: "THIS_WEEK", label: "Week" }
];

export function App() {
  const [now, setNow] = useState(() => new Date());
  const [utcOffset, setUtcOffset] = useState(3);
  const [selectedImpacts, setSelectedImpacts] = useState<Impact[]>(["HIGH"]);
  const [selectedCurrencies, setSelectedCurrencies] = useState<CurrencyCode[]>([]);
  const [newsWindow, setNewsWindow] = useState<NewsWindow>("48H");
  const [events, setEvents] = useState<NewsEvent[]>(mockEvents);
  const [eventsStatus, setEventsStatus] = useState<"loading" | "ready" | "fallback" | "empty">("loading");
  const [settingsStatus, setSettingsStatus] = useState<"local" | "loading" | "synced" | "unavailable">("local");
  const [isTimezoneOpen, setTimezoneOpen] = useState(false);
  const [isNewsOpen, setNewsOpen] = useState(() => new URLSearchParams(window.location.search).get("news") === "1");
  const [isSettingsHintOpen, setSettingsHintOpen] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<NewsEvent | null>(null);

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
        setSelectedCurrencies(settings.currencies as CurrencyCode[]);
        setNewsWindow(settings.news_window);
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
        const loadedEvents = await fetchHighImpactEvents(
          new Date(),
          utcOffset,
          selectedImpacts,
          selectedCurrencies,
          newsWindow,
          controller.signal
        );
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
  }, [utcOffset, selectedImpacts, selectedCurrencies, newsWindow]);

  async function updatePreferences(next: {
    utcOffset?: number;
    impacts?: Impact[];
    currencies?: CurrencyCode[];
    newsWindow?: NewsWindow;
  }) {
    const nextUtcOffset = next.utcOffset ?? utcOffset;
    const nextImpacts = next.impacts ?? selectedImpacts;
    const nextCurrencies = next.currencies ?? selectedCurrencies;
    const nextNewsWindow = next.newsWindow ?? newsWindow;

    setUtcOffset(nextUtcOffset);
    setSelectedImpacts(nextImpacts);
    setSelectedCurrencies(nextCurrencies);
    setNewsWindow(nextNewsWindow);

    try {
      const saved = await saveUserSettings({
        utc_offset: nextUtcOffset,
        impacts: nextImpacts,
        currencies: nextCurrencies,
        news_window: nextNewsWindow
      });
      if (saved) setSettingsStatus("synced");
    } catch (error) {
      setSettingsStatus("unavailable");
    }
  }

  const marketState = useMemo(() => getMarketState(now, utcOffset), [now, utcOffset]);
  const timelineSessions = useMemo(() => buildTimelineSessions(now), [now]);
  const timeTicks = useMemo(() => buildTimeTicks(now, utcOffset), [now, utcOffset]);
  const timelineEvents = useMemo(() => {
    const halfWidth = (TIMELINE_HOURS * PX_PER_HOUR) / 2;
    return events
      .map((event) => ({
        event,
        left: ((new Date(event.datetimeUtc).getTime() - now.getTime()) / HOUR_MS) * PX_PER_HOUR
      }))
      .filter(({ left }) => left > -halfWidth && left < halfWidth);
  }, [events, now]);

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
        <div className="sheet-backdrop" onClick={() => setSettingsHintOpen(false)}>
          <section className="settings-sheet" aria-label="Settings" onClick={(event) => event.stopPropagation()}>
            <div className="sheet-header">
              <h2>Settings</h2>
              <button className="sheet-close" type="button" onClick={() => setSettingsHintOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <div className="settings-panel-row">
              <span>News window</span>
              <div className="segmented-control three">
                {newsWindowOptions.map((option) => (
                  <button
                    className={option.value === newsWindow ? "segment active" : "segment"}
                    key={option.value}
                    type="button"
                    onClick={() => updatePreferences({ newsWindow: option.value })}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="settings-panel-row">
              <span>Impact</span>
              <div className="segmented-control three">
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

            <div className="settings-panel-row">
              <span>Currencies</span>
              <div className="currency-grid">
                {currencyOptions.map((currency) => {
                  const isActive = selectedCurrencies.includes(currency);
                  return (
                    <button
                      className={isActive ? "segment active" : "segment"}
                      key={currency}
                      type="button"
                      onClick={() => {
                        const nextCurrencies = isActive
                          ? selectedCurrencies.filter((item) => item !== currency)
                          : [...selectedCurrencies, currency];
                        updatePreferences({ currencies: nextCurrencies });
                      }}
                    >
                      {currency}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="settings-panel-row">
              <span>Timezone</span>
              <select
                className="timezone-select"
                value={utcOffset}
                onChange={(event) => updatePreferences({ utcOffset: Number(event.target.value) })}
              >
                {timezoneOptions.map((option) => (
                  <option key={option.offset} value={option.offset}>
                    {`${formatUtcLabel(option.offset)} ${option.label}`}
                  </option>
                ))}
              </select>
            </div>

            <div className={`settings-sync ${settingsStatus}`}>{settingsStatus === "synced" ? "Saved" : "Local"}</div>
          </section>
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

          {timelineEvents.map(({ event, left }) => {
            const minutesAway = Math.abs(new Date(event.datetimeUtc).getTime() - now.getTime()) / (60 * 1000);
            return (
              <button
                className={`event-marker ${event.impact.toLowerCase()} ${minutesAway <= 60 ? "soon" : ""}`}
                key={event.id}
                style={{ left: `calc(50% + ${left}px)` }}
                type="button"
                onClick={() => setSelectedEvent(event)}
                aria-label={`${event.title} ${formatEventDate(event.datetimeUtc, utcOffset)}`}
              >
                <span>{event.currency}</span>
              </button>
            );
          })}
        </div>

        <div className="now-line" />
        <div className="now-arrow" />

        <button className="news-toggle" type="button" onClick={() => setNewsOpen((value) => !value)}>
          <Newspaper size={22} />
        </button>

        {selectedEvent && (
          <article className="event-popover">
            <button className="popover-close" type="button" onClick={() => setSelectedEvent(null)}>
              <X size={14} />
            </button>
            <h2>{selectedEvent.title}</h2>
            <p>{selectedEvent.currency} / {selectedEvent.impact}</p>
            <time>{formatEventDate(selectedEvent.datetimeUtc, utcOffset)}</time>
          </article>
        )}

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
                    <p>{event.currency} / {event.impact}</p>
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
