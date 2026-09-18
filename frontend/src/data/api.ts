import type { CareEvent } from "./types";

export const API_BASE_URL = import.meta.env.VITE_ELDERLINK_API_URL ?? "";
export const CARE_RECIPIENT_ID = import.meta.env.VITE_ELDERLINK_CARE_RECIPIENT_ID ?? "demo-dad";
export const USE_MOCK_DATA = import.meta.env.VITE_ELDERLINK_USE_MOCK_DATA === "true";

interface TimelineResponse {
  care_recipient_id: string;
  events: CareEvent[];
}

/**
 * Fetches the real, persisted CareEvent timeline for one demo care
 * recipient from the Phase 7 read API (GET /care-recipients/{id}/timeline).
 * Throws on any non-2xx response or network failure - callers must not
 * swallow this into a silent mock-data fallback (see CareEventsContext),
 * since a hidden fallback could make a broken demo look healthy.
 */
export async function fetchCareEventTimeline(
  careRecipientId: string = CARE_RECIPIENT_ID,
): Promise<CareEvent[]> {
  if (!API_BASE_URL) {
    throw new Error(
      "VITE_ELDERLINK_API_URL is not configured. Set it in frontend/.env (see .env.example) or set VITE_ELDERLINK_USE_MOCK_DATA=true for local UI work without a deployed backend.",
    );
  }

  const url = `${API_BASE_URL.replace(/\/$/, "")}/care-recipients/${encodeURIComponent(careRecipientId)}/timeline`;
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`CareEvents API request failed: ${response.status} ${response.statusText}`);
  }

  const data: TimelineResponse = await response.json();
  return data.events;
}
