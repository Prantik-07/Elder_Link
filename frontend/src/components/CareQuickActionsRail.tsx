import { useMemo } from "react";
import clsx from "clsx";
import { useNavigate } from "react-router-dom";
import { Bell, Heart, Mic, Upload, Users } from "lucide-react";
import { useCareEvents } from "../state/CareEventsContext";
import { lastHandoffCutoff } from "../lib/handoff";
import { VoiceRecorder } from "./VoiceRecorder";

function VoiceNoteCard() {
  return (
    <VoiceRecorder
      renderTrigger={(onClick) => (
        <div
          className="rounded-2xl border p-4"
          style={{ borderColor: "var(--color-med-soft)", backgroundColor: "var(--color-med-soft)" }}
        >
          <div className="flex items-start gap-3">
            <span
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full"
              style={{ backgroundColor: "var(--color-teal)" }}
              aria-hidden="true"
            >
              <Mic size={19} className="text-[var(--color-paper)]" strokeWidth={2} />
            </span>
            <div className="min-w-0">
              <p className="text-[14.5px] font-semibold text-[var(--color-ink)]">Add a quick voice note</p>
              <p className="mt-0.5 text-[12.5px] leading-snug text-[var(--color-ink-soft)]">
                Just speak - we&rsquo;ll take care of the rest.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClick}
            className="mt-3.5 inline-flex w-full items-center justify-center gap-2 rounded-full py-3.5 text-[14.5px] font-semibold text-[var(--color-paper)] transition-opacity hover:opacity-90 lg:py-2.5 lg:text-[13.5px]"
            style={{ backgroundColor: "var(--color-teal)" }}
          >
            <Mic size={15} aria-hidden="true" />
            Tap to speak
          </button>
        </div>
      )}
    />
  );
}

function NextHandoffCard() {
  const { events } = useCareEvents();
  const navigate = useNavigate();

  const { total, needsAttention } = useMemo(() => {
    const cutoff = lastHandoffCutoff();
    const since = events.filter((e) => new Date(e.occurredAt) > cutoff);
    return {
      total: since.length,
      needsAttention: since.filter((e) => e.status !== "verified").length,
    };
  }, [events]);

  return (
    <div className="rounded-2xl border p-4" style={{ borderColor: "var(--color-obs-soft)", backgroundColor: "var(--color-obs-soft)" }}>
      <div className="flex items-start gap-3">
        <span
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full"
          style={{ backgroundColor: "var(--color-paper)", color: "var(--color-obs)" }}
          aria-hidden="true"
        >
          <Users size={18} strokeWidth={2} />
        </span>
        <div className="min-w-0">
          <p className="text-[12px] font-medium text-[var(--color-ink-muted)]">Next handoff</p>
          <p className="font-display text-[16px] text-[var(--color-ink)]">
            {total === 0 ? "You're all set" : `${total} ${total === 1 ? "change" : "changes"} to share`}
          </p>
          <p className="mt-0.5 text-[12.5px] leading-snug text-[var(--color-ink-soft)]">
            {needsAttention > 0
              ? `${needsAttention} still ${needsAttention === 1 ? "needs" : "need"} verification.`
              : "Share a quick summary when you're done."}
          </p>
        </div>
      </div>
      <button
        type="button"
        onClick={() => navigate("/handoff")}
        className="mt-3.5 inline-flex w-full items-center justify-center gap-2 rounded-full border py-2.5 text-[13.5px] font-semibold text-[var(--color-ink)] transition-colors hover:bg-[var(--color-paper)]"
        style={{ borderColor: "var(--color-line)", backgroundColor: "var(--color-paper)" }}
      >
        <Upload size={13} aria-hidden="true" />
        Generate handoff summary
      </button>
    </div>
  );
}

function TeamEffortCard() {
  return (
    <div
      className="relative overflow-hidden rounded-2xl border p-4"
      style={{ borderColor: "var(--color-concern-soft)", backgroundColor: "var(--color-concern-soft)" }}
    >
      <div className="flex items-start gap-3">
        <span
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full"
          style={{ backgroundColor: "var(--color-paper)", color: "var(--color-concern)" }}
          aria-hidden="true"
        >
          <Heart size={18} strokeWidth={2} />
        </span>
        <div className="min-w-0">
          <p className="text-[14.5px] font-semibold text-[var(--color-ink)]">Care is a team effort</p>
          <p className="mt-0.5 text-[12.5px] leading-snug text-[var(--color-ink-soft)]">
            Thank you for being here <span aria-hidden="true">&hearts;</span>
          </p>
        </div>
      </div>
    </div>
  );
}

function ReminderCard() {
  return (
    <div
      className="flex w-full items-center gap-3 rounded-2xl border p-4 text-left"
      style={{ borderColor: "var(--color-routine-soft)", backgroundColor: "var(--color-routine-soft)" }}
    >
      <span
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
        style={{ backgroundColor: "var(--color-paper)", color: "var(--color-routine)" }}
        aria-hidden="true"
      >
        <Bell size={15} strokeWidth={2} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[12px] font-medium text-[var(--color-ink-muted)]">Today&rsquo;s reminder</span>
        <span className="block text-[13.5px] font-medium text-[var(--color-ink)]">9:00 AM &middot; Check blood pressure</span>
      </span>
    </div>
  );
}

export function CareQuickActionsRail({ className }: { className?: string }) {
  return (
    <aside
      className={clsx("flex w-full flex-col gap-3.5 lg:w-80 lg:shrink-0", className)}
      aria-label="Quick actions"
    >
      <VoiceNoteCard />
      <NextHandoffCard />
      <TeamEffortCard />
      <ReminderCard />
      <p className="font-hand px-2 text-center text-[15px] leading-snug text-[var(--color-ink-muted)]">
        &ldquo;Better care isn&rsquo;t about doing more, but knowing what matters.&rdquo;
        <span className="mt-1 block text-[12px] not-italic">&mdash; ElderLink</span>
      </p>
    </aside>
  );
}
