/** The moment the last handoff was reviewed - fixed at yesterday, 6:00 PM. */
export function lastHandoffCutoff(now: Date = new Date()): Date {
  const cutoff = new Date(now);
  cutoff.setDate(now.getDate() - 1);
  cutoff.setHours(18, 0, 0, 0);
  return cutoff;
}

export const LAST_HANDOFF_LABEL = "yesterday, 6:00 PM";
