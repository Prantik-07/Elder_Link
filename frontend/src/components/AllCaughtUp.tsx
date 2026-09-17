import { Users } from "lucide-react";

export function AllCaughtUp({ since }: { since: string }) {
  return (
    <div className="flex items-center gap-3.5 rounded-xl border border-dashed px-4 py-4" style={{ borderColor: "var(--color-line)" }}>
      <span
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
        style={{ backgroundColor: "var(--color-teal-soft)", color: "var(--color-teal)" }}
        aria-hidden="true"
      >
        <Users size={17} strokeWidth={2} />
      </span>
      <div>
        <p className="font-display text-[15px] text-[var(--color-ink)]">All caught up!</p>
        <p className="mt-0.5 text-[12.5px] text-[var(--color-ink-muted)]">
          No more new events since your last handoff {since}.
        </p>
      </div>
    </div>
  );
}
