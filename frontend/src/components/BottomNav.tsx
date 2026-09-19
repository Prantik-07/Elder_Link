import { NavLink } from "react-router-dom";
import { Clock, Home, UserRound } from "lucide-react";

const BOTTOM_NAV_ITEMS = [
  { to: "/", label: "Care", end: true, icon: Home },
  { to: "/timeline", label: "Timeline", end: false, icon: Clock },
  { to: "/handoff", label: "Handoff", end: false, icon: UserRound },
];

/**
 * Fixed bottom navigation for the three primary phone-sized destinations.
 * Care Circle stays reachable through Header's mobile menu instead of
 * competing for space here - see the Phase (mobile refinement) report for
 * why only these three get a permanent thumb-reach slot.
 */
export function BottomNav() {
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-30 border-t bg-[var(--color-ivory)]/95 backdrop-blur lg:hidden"
      style={{ borderColor: "var(--color-line)", paddingBottom: "env(safe-area-inset-bottom)" }}
      aria-label="Primary"
    >
      <div className="mx-auto flex max-w-lg items-stretch justify-around">
        {BOTTOM_NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `flex min-w-[4.5rem] flex-1 flex-col items-center justify-center gap-0.5 py-2.5 text-[11.5px] font-medium transition-colors ${
                isActive ? "text-[var(--color-teal-dark)]" : "text-[var(--color-ink-muted)]"
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className="flex h-8 w-8 items-center justify-center rounded-full transition-colors"
                  style={isActive ? { backgroundColor: "var(--color-teal-soft)" } : undefined}
                  aria-hidden="true"
                >
                  <item.icon size={18} strokeWidth={isActive ? 2.25 : 2} />
                </span>
                {item.label}
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
