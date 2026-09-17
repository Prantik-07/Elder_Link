export interface Caregiver {
  id: string;
  name: string;
  role: string;
  initials: string;
  color: string;
}

// Derived from who actually appears as `reportedBy` on care events. There are
// no real caregiver photos to show, so each person gets a consistent color +
// initials avatar instead of a fabricated headshot.
export const CAREGIVERS: Caregiver[] = [
  { id: "shivaansh", name: "Shivaansh", role: "Primary caregiver", initials: "SP", color: "var(--color-teal)" },
  { id: "priya", name: "Priya", role: "Caregiver", initials: "P", color: "var(--color-med)" },
  { id: "anita", name: "Anita", role: "Caregiver", initials: "A", color: "var(--color-obs)" },
  { id: "ramesh", name: "Ramesh", role: "Caregiver", initials: "R", color: "var(--color-routine)" },
];

export function findCaregiverByReportedBy(reportedBy: string): Caregiver | undefined {
  const firstName = reportedBy.split(" ")[0]?.toLowerCase();
  return CAREGIVERS.find((c) => c.name.toLowerCase() === firstName);
}
