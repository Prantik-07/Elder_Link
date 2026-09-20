import { API_BASE_URL } from "../data/api";
import { CURRENT_CAREGIVER_ID } from "../data/caregivers";
import type { CareEvent } from "../data/types";
import { getCareCircle } from "./careCircle";

export interface FlagNotifyOutcome {
  tone: "ok" | "info" | "error";
  message: string;
}

interface RecipientResult {
  name: string;
  email: string;
  status: "notified" | "pending_confirmation" | "confirmation_sent" | "failed";
}

/**
 * Tells the rest of the Care Circle that the current caregiver flagged an
 * event. The flagger is never a recipient (they did it themselves), and only
 * members with an email can be reached. Never throws: the flag itself already
 * succeeded locally, so a notification problem is reported, not raised.
 */
export async function notifyCircleOfFlag(
  event: CareEvent,
  patientName: string,
): Promise<FlagNotifyOutcome> {
  const circle = getCareCircle();
  const flagger = circle.find((c) => c.id === CURRENT_CAREGIVER_ID);
  const recipients = circle.filter((c) => c.id !== CURRENT_CAREGIVER_ID && c.email);

  if (recipients.length === 0) {
    return {
      tone: "info",
      message: "Flagged. No one else in the Care Circle has an email yet, so nobody was notified.",
    };
  }
  if (!API_BASE_URL) {
    return { tone: "info", message: "Flagged. Notifications need the backend URL to be configured." };
  }

  try {
    const response = await fetch(`${API_BASE_URL.replace(/\/$/, "")}/notifications/flag`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        patient_name: patientName,
        flagged_by: flagger?.name ?? "A caregiver",
        event_title: event.title,
        recipients: recipients.map((r) => ({ name: r.name, email: r.email })),
      }),
    });
    if (!response.ok) throw new Error(String(response.status));

    const { results } = (await response.json()) as { results: RecipientResult[] };
    const sent = results.filter((r) => r.status === "notified").map((r) => r.name);
    const needConfirm = results.filter(
      (r) => r.status === "confirmation_sent" || r.status === "pending_confirmation",
    );
    const failed = results.filter((r) => r.status === "failed");

    const parts: string[] = [];
    if (sent.length) parts.push(`Notified ${sent.join(", ")}.`);
    if (needConfirm.length) {
      parts.push(
        `${needConfirm.map((r) => r.name).join(", ")} must confirm the subscription email before they can be notified.`,
      );
    }
    if (failed.length) parts.push(`Couldn't notify ${failed.map((r) => r.name).join(", ")}.`);

    return {
      tone: failed.length ? "error" : sent.length ? "ok" : "info",
      message: `Flagged. ${parts.join(" ")}`,
    };
  } catch {
    return { tone: "error", message: "Flagged, but the Care Circle couldn't be notified. Try again later." };
  }
}
