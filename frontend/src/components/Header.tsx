import { useState } from "react";
import { NavLink } from "react-router-dom";
import { ChevronDown, Clock, Home, Menu, Plus, Search, UserRound, Users, X } from "lucide-react";
import { useCareEvents } from "../state/CareEventsContext";
import { patientSubtitle, usePatients } from "../state/PatientsContext";
import { PatientAvatar } from "./PatientAvatar";
import { AddPatientModal } from "./AddPatientModal";

const NAV_ITEMS = [
  { to: "/", label: "Home", end: true, icon: Home },
  { to: "/timeline", label: "Timeline", end: false, icon: Clock },
  { to: "/handoff", label: "Handoff", end: false, icon: UserRound },
  { to: "/care-circle", label: "Care Circle", end: false, icon: Users },
];

export function Header() {
  const [searchOpen, setSearchOpen] = useState(false);
  const [patientMenuOpen, setPatientMenuOpen] = useState(false);
  const [addPatientOpen, setAddPatientOpen] = useState(false);
  const { patients, activePatient, selectPatient } = usePatients();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { search, setSearch } = useCareEvents();

  return (
    <header
      className="sticky top-0 z-30 border-b bg-[var(--color-ivory)]/90 backdrop-blur"
      style={{ borderColor: "var(--color-line)" }}
    >
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 sm:px-6 lg:gap-4 xl:gap-7">
        <div className="flex min-w-0 shrink-0 items-center gap-2">
          <img src="/assets/logo-mark.png" alt="" aria-hidden="true" className="h-8 w-auto shrink-0" />
          <div className="flex flex-col justify-center leading-none">
            <span className="font-display text-[20px] tracking-tight text-[var(--color-ink)]">
              ElderLink
            </span>
            <span className="mt-1 hidden text-[12px] tracking-wide text-[var(--color-ink-muted)] sm:block">
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
                `flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-[13.5px] font-medium whitespace-nowrap transition-colors xl:px-3.5 xl:text-[14px] ${
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
              onClick={() => {
                setPatientMenuOpen((o) => !o);
                setMobileMenuOpen(false);
              }}
              aria-haspopup="listbox"
              aria-expanded={patientMenuOpen}
              className="flex items-center gap-2 rounded-full py-1 pr-2 pl-1 transition-colors hover:bg-[var(--color-ivory-soft)]"
            >
              {activePatient ? (
                <PatientAvatar patient={activePatient} size={36} />
              ) : (
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--color-ivory-soft)] text-[var(--color-ink-muted)]">
                  <Users size={16} aria-hidden="true" />
                </span>
              )}
              <span className="hidden text-left leading-tight lg:block">
                <span className="block text-[13.5px] font-medium whitespace-nowrap text-[var(--color-ink)]">
                  {activePatient?.name ?? "Choose patient"}
                </span>
                <span className="block text-[12px] whitespace-nowrap text-[var(--color-ink-muted)]">
                  {activePatient ? patientSubtitle(activePatient) : "Who are you caring for?"}
                </span>
              </span>
              <ChevronDown size={14} className="text-[var(--color-ink-muted)]" aria-hidden="true" />
            </button>

            {patientMenuOpen && (
              <div
                className="absolute top-full right-0 z-40 mt-2 w-64 overflow-hidden rounded-xl border bg-[var(--color-paper)] py-1 shadow-[var(--shadow-panel)]"
                style={{ borderColor: "var(--color-line)" }}
              >
                <p className="px-3.5 pt-2 pb-1 text-[12px] font-semibold tracking-wide text-[var(--color-ink-muted)] uppercase">
                  Switch patient
                </p>
                <ul role="listbox" aria-label="Patients">
                  {patients.map((p) => {
                    const active = activePatient?.id === p.id;
                    return (
                      <li key={p.id} role="option" aria-selected={active}>
                        <button
                          type="button"
                          className="flex w-full items-center gap-2.5 px-3.5 py-2 text-left hover:bg-[var(--color-ivory-soft)]"
                          onClick={() => {
                            selectPatient(p.id);
                            setPatientMenuOpen(false);
                          }}
                        >
                          <PatientAvatar patient={p} size={30} />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-[13.5px] text-[var(--color-ink)]">{p.name}</span>
                            <span className="block truncate text-[12px] text-[var(--color-ink-muted)]">
                              {patientSubtitle(p)}
                            </span>
                          </span>
                          {active && <span style={{ color: "var(--color-teal)" }}>&#10003;</span>}
                        </button>
                      </li>
                    );
                  })}
                </ul>
                <div className="mt-1 border-t pt-1" style={{ borderColor: "var(--color-line)" }}>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 px-3.5 py-2 text-[13.5px] text-[var(--color-ink)] hover:bg-[var(--color-ivory-soft)]"
                    onClick={() => {
                      setPatientMenuOpen(false);
                      setAddPatientOpen(true);
                    }}
                  >
                    <Plus size={15} aria-hidden="true" />
                    Add patient
                  </button>
                </div>
              </div>
            )}
            {addPatientOpen && (
              <AddPatientModal
                onClose={() => setAddPatientOpen(false)}
                onAdded={(p) => selectPatient(p.id)}
              />
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
              <span className="block text-[12px] text-[var(--color-ink-muted)]">Caregiver</span>
            </span>
          </div>

          {/* Below lg, primary Care/Timeline/Handoff navigation moves to
              BottomNav; this menu holds what's left - Care Circle and the
              caregiver identity block - as a compact panel rather than
              squeezing the full desktop nav into the header. */}
          <div className="relative lg:hidden">
            <button
              type="button"
              onClick={() => {
                setMobileMenuOpen((o) => !o);
                setPatientMenuOpen(false);
              }}
              aria-haspopup="true"
              aria-expanded={mobileMenuOpen}
              aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[var(--color-ink-muted)] transition-colors hover:bg-[var(--color-ivory-soft)] hover:text-[var(--color-ink)]"
            >
              {mobileMenuOpen ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
            </button>

            {mobileMenuOpen && (
              <div
                className="absolute top-full right-0 z-40 mt-2 w-60 overflow-hidden rounded-xl border bg-[var(--color-paper)] shadow-[var(--shadow-panel)]"
                style={{ borderColor: "var(--color-line)" }}
              >
                <NavLink
                  to="/care-circle"
                  onClick={() => setMobileMenuOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-4 py-3 text-[14px] font-medium ${
                      isActive
                        ? "bg-[var(--color-teal-soft)] text-[var(--color-teal-dark)]"
                        : "text-[var(--color-ink)] hover:bg-[var(--color-ivory-soft)]"
                    }`
                  }
                >
                  <Users size={16} aria-hidden="true" />
                  Care Circle
                </NavLink>
                <div className="flex items-center gap-2.5 border-t px-4 py-3" style={{ borderColor: "var(--color-line)" }}>
                  <span
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold text-[var(--color-paper)]"
                    style={{ backgroundColor: "var(--color-teal)" }}
                    aria-hidden="true"
                  >
                    SP
                  </span>
                  <span className="leading-tight">
                    <span className="block text-[13px] font-medium text-[var(--color-ink)]">Hi, Shivaansh</span>
                    <span className="block text-[12px] text-[var(--color-ink-muted)]">Caregiver</span>
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
