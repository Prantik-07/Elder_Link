import type { CareEvent, CareEventStatus } from "./types";

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

/**
 * Persists a caregiver's verification decision (Day 5) via
 * PATCH /care-recipients/{id}/care-events/{eventId}. Only "verified" and
 * "uncertain" are valid caregiver-initiated statuses - the backend maps
 * "uncertain" to review_state=needs_verification with a fixed
 * verification_reason (see update_care_event_status/handler.py); this is
 * the same narrow contract the backend enforces, not an independent
 * frontend rule that could drift from it. Throws on any non-2xx response
 * or network failure - callers must treat that as "not persisted", never
 * apply the change locally anyway (see CareEventsContext.setStatus).
 */
export async function updateCareEventStatus(
  eventId: string,
  status: Extract<CareEventStatus, "verified" | "uncertain">,
  careRecipientId: string = CARE_RECIPIENT_ID,
): Promise<CareEvent> {
  if (!API_BASE_URL) {
    throw new Error("VITE_ELDERLINK_API_URL is not configured - cannot save verification status.");
  }

  const url = `${API_BASE_URL.replace(/\/$/, "")}/care-recipients/${encodeURIComponent(careRecipientId)}/care-events/${encodeURIComponent(eventId)}`;
  const response = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });

  if (!response.ok) {
    throw new Error(`Failed to save verification status: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

export interface AudioUploadUrlResponse {
  object_key: string;
  upload_url: string;
  method: "PUT";
  headers: Record<string, string>;
  care_recipient_id: string;
  expires_in: number;
}

/**
 * Day 4: asks the backend (POST /audio/upload-url) for a presigned S3 PUT
 * URL under the existing audio/ prefix - the browser never holds an AWS
 * credential. Throws on any non-2xx response or network failure, same
 * honesty rule as fetchCareEventTimeline: a failure here must surface as a
 * real error state in the recorder, never a silently-skipped step.
 */
export async function requestAudioUploadUrl(
  contentType: string,
  careRecipientId: string = CARE_RECIPIENT_ID,
): Promise<AudioUploadUrlResponse> {
  if (!API_BASE_URL) {
    throw new Error("VITE_ELDERLINK_API_URL is not configured - cannot request an upload URL.");
  }

  const response = await fetch(`${API_BASE_URL.replace(/\/$/, "")}/audio/upload-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ care_recipient_id: careRecipientId, content_type: contentType }),
  });

  if (!response.ok) {
    throw new Error(`Failed to get an upload URL: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

/**
 * Uploads a recorded audio Blob directly to S3 via a presigned PUT URL.
 * Uses XMLHttpRequest (not fetch) specifically so real upload progress is
 * available - onProgress reports true bytes-sent/bytes-total, never a
 * fabricated percentage.
 */
export function uploadAudioToPresignedUrl(
  uploadUrl: string,
  blob: Blob,
  contentType: string,
  onProgress?: (fraction: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", uploadUrl);
    xhr.setRequestHeader("Content-Type", contentType);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(event.loaded / event.total);
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(new Error(`Upload to S3 failed: ${xhr.status} ${xhr.statusText}`));
      }
    };

    xhr.onerror = () => reject(new Error("Upload to S3 failed - network error."));
    xhr.onabort = () => reject(new Error("Upload cancelled."));

    xhr.send(blob);
  });
}
