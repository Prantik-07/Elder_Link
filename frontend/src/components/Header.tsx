import { useState } from "react";
import { NavLink } from "react-router-dom";
import { ChevronDown, Search, X } from "lucide-react";
import { useCareEvents } from "../state/CareEventsContext";

const NAV_ITEMS = [
  { to: "/", label: "Care", end: true },
  { to: "/timeline", label: "Timeline", end: false },
  { to: "/handoff", label: "Handoff", end: false },
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
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 sm:px-6">
        <div className="flex min-w-0 shrink-0 flex-col justify-center leading-none">
          <span className="font-display text-[19px] text-[var(--color-ink)]">ElderLink</span>
          <span className="mt-0.5 hidden text-[10.5px] text-[var(--color-ink-muted)] sm:block">
            Voices. Context. Better Care.
          </span>
        </div>

        <nav className="hidden items-center gap-1 md:flex" aria-label="Primary">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `relative px-3 py-2 text-[14px] font-medium transition-colors ${
                  isActive ? "text-[var(--color-ink)]" : "text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {item.label}
                  {isActive && (
                    <span
                      className="absolute right-3 -bottom-[1px] left-3 h-[2px] rounded-full"
                      style={{ backgroundColor: "var(--color-teal)" }}
                      aria-hidden="true"
                    />
                  )}
                </>
              )}
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
              <span
                className="flex h-8 w-8 items-center justify-center rounded-full font-display text-[13px] text-[var(--color-paper)]"
                style={{ backgroundColor: "var(--color-routine)" }}
                aria-hidden="true"
              >
                D
              </span>
              <span className="hidden text-left leading-tight sm:block">
                <span className="block text-[13.5px] font-medium text-[var(--color-ink)]">Dad</span>
                <span className="block text-[11px] text-[var(--color-ink-muted)]">
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

          <span
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold text-[var(--color-ink)]"
            style={{ backgroundColor: "var(--color-ivory-soft)" }}
            title="Shivaansh P."
          >
            SP
          </span>
        </div>
      </div>

      <nav className="flex items-center gap-1 overflow-x-auto border-t px-4 py-1.5 md:hidden" style={{ borderColor: "var(--color-line)" }} aria-label="Primary">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `rounded-full px-3 py-1.5 text-[13px] font-medium whitespace-nowrap ${
                isActive ? "bg-[var(--color-teal)] text-[var(--color-paper)]" : "text-[var(--color-ink-muted)]"
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
