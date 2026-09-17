export type CareEventType =
  | "medication"
  | "observation"
  | "concern"
  | "appointment"
  | "vital"
  | "routine";

export type CareEventStatus = "verified" | "needs_verification" | "uncertain";

export interface CareEventEvidence {
  transcript: string;
  segmentId: string;
  startTime?: number;
  endTime?: number;
  audioUrl?: string;
  /** Mock playback duration in seconds, used until real audio is wired up. */
  durationSeconds?: number;
}

export interface CareEvent {
  id: string;
  type: CareEventType;
  /**
   * Display label override for the category chip. Most event types render
   * a fixed label derived from `type` (see CATEGORY_META), but some events
   * need a more specific label than their underlying type conveys - e.g. a
   * "medication" event that represents a possible missed dose reads as
   * "Possible medication miss" rather than the generic "Medication".
   */
  categoryLabel?: string;
  title: string;
  summary: string;
  whatHappened: string;
  occurredAt: string;
  reportedBy: string;
  location?: string;
  status: CareEventStatus;
  evidence?: CareEventEvidence;
  verificationReason?: string;
}
