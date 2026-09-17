import { findCaregiverByReportedBy } from "../data/caregivers";

/**
 * Small colored-initials avatar for whoever reported a care event. There are
 * no real caregiver photos to show (and we don't fabricate stock headshots),
 * so each known caregiver gets a consistent color + initials mark instead.
 */
export function CaregiverAvatar({
  reportedBy,
  size = 20,
}: {
  reportedBy: string;
  size?: number;
}) {
  const caregiver = findCaregiverByReportedBy(reportedBy);
  const initials = caregiver?.initials ?? reportedBy.slice(0, 1).toUpperCase();
  const color = caregiver?.color ?? "var(--color-ink-muted)";

  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-full font-medium text-[var(--color-paper)]"
      style={{
        width: size,
        height: size,
        backgroundColor: color,
        fontSize: Math.max(8, size * 0.42),
      }}
      aria-hidden="true"
    >
      {initials}
    </span>
  );
}
