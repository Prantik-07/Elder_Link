import { useEffect, useState, type FormEvent } from "react";
import { Phone, Plus } from "lucide-react";
import { CAREGIVERS, type Caregiver } from "../data/caregivers";
import { CaregiverAvatar } from "../components/CaregiverAvatar";
import { Modal } from "../components/Modal";

const MEMBERS_KEY = "elderlink.careCircle.members";

// Demo-grade persistence: members added here live only in this browser's
// localStorage (no backend), so they survive a refresh but are not shared.
function loadMembers(): Caregiver[] {
  try {
    const raw = localStorage.getItem(MEMBERS_KEY);
    if (!raw) return CAREGIVERS;
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.length > 0 ? (parsed as Caregiver[]) : CAREGIVERS;
  } catch {
    return CAREGIVERS;
  }
}

export function CareCirclePage() {
  const [members, setMembers] = useState<Caregiver[]>(loadMembers);
  useEffect(() => {
    try {
      localStorage.setItem(MEMBERS_KEY, JSON.stringify(members));
    } catch {
      // Storage unavailable (private mode/quota): the list still works in memory.
    }
  }, [members]);
  const [addOpen, setAddOpen] = useState(false);
  const [name, setName] = useState("");
  const [role, setRole] = useState("Caregiver");

  const closeAdd = () => {
    setAddOpen(false);
    setName("");
    setRole("Caregiver");
  };

  const addMember = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    setMembers((prev) => [
      ...prev,
      {
        id: `${trimmed.toLowerCase().replace(/\s+/g, "-")}-${prev.length}`,
        name: trimmed,
        role: role.trim() || "Caregiver",
        initials: trimmed.slice(0, 1).toUpperCase(),
        color: "var(--color-ink-muted)",
      },
    ]);
    closeAdd();
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-5 sm:px-6 sm:py-7 lg:px-8 lg:py-9 xl:px-10">
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
        {members.map((c) => (
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
        <button
          type="button"
          onClick={() => setAddOpen(true)}
          className="flex w-full shrink-0 items-center justify-center gap-1.5 rounded-full px-5 py-3 text-[13.5px] font-semibold text-[var(--color-paper)] transition-opacity hover:opacity-90 sm:ml-auto sm:w-auto sm:py-2.5"
          style={{ backgroundColor: "var(--color-teal)" }}
        >
          <Plus size={14} aria-hidden="true" />
          Add to Care Circle
        </button>
      </div>

      {addOpen && (
        <Modal onClose={closeAdd} titleId="add-member-title">
          <form onSubmit={addMember}>
            <h2 id="add-member-title" className="font-display text-[20px] text-[var(--color-ink)]">
              Add to Care Circle
            </h2>
            <label className="mt-4 block text-[13px] font-medium text-[var(--color-ink)]">
              Name
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                autoFocus
                className="mt-1.5 w-full rounded-lg border bg-[var(--color-paper)] px-3 py-2 text-[14px] font-normal"
                style={{ borderColor: "var(--color-line)" }}
              />
            </label>
            <label className="mt-3 block text-[13px] font-medium text-[var(--color-ink)]">
              Role
              <input
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="mt-1.5 w-full rounded-lg border bg-[var(--color-paper)] px-3 py-2 text-[14px] font-normal"
                style={{ borderColor: "var(--color-line)" }}
              />
            </label>
            <div className="mt-6 flex flex-col gap-2.5 sm:flex-row">
              <button
                type="submit"
                className="w-full rounded-full px-5 py-3 text-[13.5px] font-semibold text-[var(--color-paper)] sm:w-auto sm:py-2.5"
                style={{ backgroundColor: "var(--color-teal)" }}
              >
                Add member
              </button>
              <button
                type="button"
                onClick={closeAdd}
                className="w-full rounded-full border px-5 py-3 text-[13.5px] font-semibold text-[var(--color-ink-soft)] sm:w-auto sm:py-2.5"
                style={{ borderColor: "var(--color-line)" }}
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
