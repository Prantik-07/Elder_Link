import { Phone } from "lucide-react";
import { CAREGIVERS } from "../data/caregivers";
import { CaregiverAvatar } from "../components/CaregiverAvatar";

export function CareCirclePage() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-7 sm:px-8 lg:py-9 xl:px-10">
      <div className="flex flex-col items-start gap-8 lg:flex-row lg:items-center">
        <div className="min-w-0 flex-1">
          <h1 className="font-display text-[28px] text-[var(--color-ink)]">Care Circle</h1>
          <p className="mt-1.5 max-w-md text-[14px] leading-relaxed text-[var(--color-ink-soft)]">
            Everyone helping look after Dad, and how to reach them. Coordinated care works best when the
            whole circle stays in the loop.
          </p>
        </div>
        <img
          src="/assets/caregiver-family.png"
          alt="An illustration of a family gathered around an older family member"
          className="h-40 w-auto shrink-0 sm:h-48"
        />
      </div>

      <ul className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {CAREGIVERS.map((c) => (
          <li
            key={c.id}
            className="flex items-center gap-3.5 rounded-2xl border p-4"
            style={{ borderColor: "var(--color-line)", backgroundColor: "var(--color-paper)" }}
          >
            <CaregiverAvatar reportedBy={c.name} size={40} />
            <div className="min-w-0 flex-1">
              <p className="text-[14.5px] font-medium text-[var(--color-ink)]">{c.name}</p>
              <p className="text-[12.5px] text-[var(--color-ink-muted)]">{c.role}</p>
            </div>
            <button
              type="button"
              aria-label={`Contact ${c.name}`}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-colors hover:bg-[var(--color-ivory-soft)]"
              style={{ color: "var(--color-teal)" }}
            >
              <Phone size={16} aria-hidden="true" />
            </button>
          </li>
        ))}
      </ul>

      <div
        className="mt-8 flex flex-col items-center gap-4 rounded-2xl border p-6 text-center sm:flex-row sm:text-left"
        style={{ borderColor: "var(--color-line)", backgroundColor: "var(--color-ivory-soft)" }}
      >
        <img src="/assets/support-woman.png" alt="" aria-hidden="true" className="h-32 w-auto shrink-0" />
        <div>
          <p className="font-display text-[18px] text-[var(--color-ink)]">You&rsquo;re not alone</p>
          <p className="mt-1 max-w-sm text-[13.5px] leading-relaxed text-[var(--color-ink-soft)]">
            Caregiving is easier with a circle around you. Add anyone who helps with Dad&rsquo;s care so
            they can see updates and pitch in on handoffs.
          </p>
        </div>
      </div>
    </div>
  );
}
