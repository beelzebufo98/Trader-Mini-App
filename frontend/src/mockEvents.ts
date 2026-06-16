import type { NewsEvent } from "./types";

export const mockEvents: NewsEvent[] = [
  {
    id: "ff_2026-01-02_15_00_USD_unemployment_claims",
    title: "Unemployment Claims",
    currency: "USD",
    impact: "HIGH",
    datetimeUtc: "2026-01-02T15:00:00Z"
  },
  {
    id: "ff_2026-01-02_15_00_USD_fomc_minutes",
    title: "FOMC Meeting Minutes",
    currency: "USD",
    impact: "HIGH",
    datetimeUtc: "2026-01-02T15:00:00Z"
  },
  {
    id: "ff_2026-01-03_09_30_GBP_services_pmi",
    title: "Final Services PMI",
    currency: "GBP",
    impact: "HIGH",
    datetimeUtc: "2026-01-03T09:30:00Z"
  }
];
