import { useState } from "react";
import { NavLink } from "react-router-dom";
import { ChevronDown, Clock, Home, Search, UserRound, Users, X } from "lucide-react";
import { useCareEvents } from "../state/CareEventsContext";

const NAV_ITEMS = [
  { to: "/", label: "Home", end: true, icon: Home },
  { to: "/timeline", label: "Timeline", end: false, icon: Clock },
  { to: "/handoff", label: "Handoff", end: false, icon: UserRound },
  { to: "/care-circle", label: "Care Circle", end: false, icon: Users },
];

export function Header() {
  const [searchOpen, setSearchOpen] = useState(false);
  const [patientMenuOpen, setPatientMenuOpen] = useState(false);
  const { search, setSearch } = useCareEvents();

  return (
    <header
      className="sticky top-0 z-30 border-b bg-[var(--color-ivory)]/90 backdrop-blur"
      style={{ borderColor: "var(--color-line)" }}
    >
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-7 px-4 sm:px-6">
        <div className="flex min-w-0 shrink-0 items-center gap-2">
          <img src="/assets/logo-mark.png" alt="" aria-hidden="true" className="h-8 w-auto shrink-0" />
          <div className="flex flex-col justify-center leading-none">
            <span className="font-display text-[20px] tracking-tight text-[var(--color-ink)]">
              ElderLink
            </span>
            <span className="mt-1 hidden text-[10.5px] tracking-wide text-[var(--color-ink-muted)] sm:block">
              Together in every chapter
            </span>
          </div>
        </div>

        <nav className="hidden items-center gap-1 lg:flex" aria-label="Primary">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-[14px] font-medium whitespace-nowrap transition-colors ${
                  isActive
                    ? "bg-[var(--color-teal-soft)] text-[var(--color-teal-dark)]"
                    : "text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]"
                }`
              }
            >
              <item.icon size={15} strokeWidth={2} aria-hidden="true" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex min-w-0 items-center gap-2 sm:gap-3">
          {searchOpen ? (
            <div className="flex items-center gap-1.5 rounded-full border bg-[var(--color-paper)] px-3 py-1.5" style={{ borderColor: "var(--color-line)" }}>
              <Search size={14} className="shrink-0 text-[var(--color-ink-muted)]" aria-hidden="true" />
              <input
                autoFocus
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search updates..."
                aria-label="Search care updates"
                className="w-36 bg-transparent text-[13.5px] text-[var(--color-ink)] outline-none placeholder:text-[var(--color-ink-muted)] sm:w-48"
              />
              <button
                type="button"
                aria-label="Close search"
                onClick={() => {
                  setSearchOpen(false);
                  setSearch("");
                }}
                className="text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]"
              >
                <X size={14} aria-hidden="true" />
              </button>
            </div>
          ) : (
            <button
              type="button"
              aria-label="Search"
              onClick={() => setSearchOpen(true)}
              className="rounded-full p-2 text-[var(--color-ink-muted)] transition-colors hover:bg-[var(--color-ivory-soft)] hover:text-[var(--color-ink)]"
            >
              <Search size={17} aria-hidden="true" />
            </button>
          )}

          <div className="relative">
            <button
              type="button"
              onClick={() => setPatientMenuOpen((o) => !o)}
              aria-haspopup="listbox"
              aria-expanded={patientMenuOpen}
              className="flex items-center gap-2 rounded-full py-1 pr-2 pl-1 transition-colors hover:bg-[var(--color-ivory-soft)]"
            >
              <img
                src="/patient-avatar.svg"
                alt=""
                aria-hidden="true"
                className="h-9 w-9 shrink-0 rounded-full ring-2 ring-[var(--color-paper)] ring-offset-1 ring-offset-[var(--color-line-soft)]"
              />
              <span className="hidden text-left leading-tight lg:block">
                <span className="block text-[13.5px] font-medium whitespace-nowrap text-[var(--color-ink)]">Dad</span>
                <span className="block text-[11px] whitespace-nowrap text-[var(--color-ink-muted)]">
                  Age 78 &middot; Living at home
                </span>
              </span>
              <ChevronDown size={14} className="text-[var(--color-ink-muted)]" aria-hidden="true" />
            </button>

            {patientMenuOpen && (
              <ul
                role="listbox"
                className="absolute top-full right-0 mt-2 w-48 overflow-hidden rounded-xl border bg-[var(--color-paper)] py-1 shadow-[var(--shadow-panel)]"
                style={{ borderColor: "var(--color-line)" }}
              >
                <li role="option" aria-selected="true">
                  <button
                    type="button"
                    className="flex w-full items-center justify-between px-3.5 py-2 text-[13.5px] text-[var(--color-ink)] hover:bg-[var(--color-ivory-soft)]"
                    onClick={() => setPatientMenuOpen(false)}
                  >
                    Dad
                    <span style={{ color: "var(--color-teal)" }}>&#10003;</span>
                  </button>
                </li>
              </ul>
            )}
          </div>

          <div className="hidden items-center gap-2 border-l pl-3 lg:flex" style={{ borderColor: "var(--color-line)" }}>
            <span
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold text-[var(--color-paper)]"
              style={{ backgroundColor: "var(--color-teal)" }}
              aria-hidden="true"
            >
              SP
            </span>
            <span className="leading-tight whitespace-nowrap">
              <span className="block text-[13px] font-medium text-[var(--color-ink)]">Hi, Shivaansh</span>
              <span className="block text-[10.5px] text-[var(--color-ink-muted)]">Caregiver</span>
            </span>
          </div>

          {/* Compact caregiver avatar shown below lg, where the full name/role block is hidden for space. */}
          <span
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold text-[var(--color-paper)] lg:hidden"
            style={{ backgroundColor: "var(--color-teal)" }}
            title="Shivaansh (Caregiver)"
          >
            SP
          </span>
        </div>
      </div>

      <nav className="flex items-center gap-1 overflow-x-auto border-t px-4 py-1.5 lg:hidden" style={{ borderColor: "var(--color-line)" }} aria-label="Primary">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `flex items-center gap-1 rounded-full px-3 py-1.5 text-[13px] font-medium whitespace-nowrap ${
                isActive ? "bg-[var(--color-teal)] text-[var(--color-paper)]" : "text-[var(--color-ink-muted)]"
              }`
            }
          >
            <item.icon size={13} aria-hidden="true" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
