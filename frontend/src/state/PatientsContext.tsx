import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export interface Patient {
  id: string;
  name: string;
  relationship: string;
  age?: number;
  /** Optional image; patients without one get a colored-initials avatar. */
  avatar?: string;
  color: string;
}

/** Events that carry no patientId (mock data, the read API) belong to this patient. */
export const DEFAULT_PATIENT_ID = "dad";

export const RELATIONSHIPS = ["Parent", "Grandparent", "Spouse", "Sibling", "Friend", "Other"];

const PALETTE = [
  "var(--color-teal)",
  "var(--color-med)",
  "var(--color-obs)",
  "var(--color-routine)",
  "var(--color-amber)",
];

const SEED: Patient[] = [
  {
    id: DEFAULT_PATIENT_ID,
    name: "Dad",
    relationship: "Parent",
    age: 78,
    avatar: "/patient-avatar.svg",
    color: "var(--color-teal)",
  },
  {
    id: "mom",
    name: "Mom",
    relationship: "Parent",
    age: 74,
    color: "var(--color-med)",
  },
];

// No backend for patients yet, so profiles and the active choice live in
// localStorage. Swap load/save for an API call when one exists.
const PATIENTS_KEY = "elderlink.patients.v1";
const ACTIVE_KEY = "elderlink.activePatient.v1";

function loadPatients(): Patient[] {
  try {
    const raw = localStorage.getItem(PATIENTS_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Patient[];
      // Seeds are always present; only patients the caregiver added come from storage.
      if (Array.isArray(parsed)) {
        return [...SEED, ...parsed.filter((p) => !SEED.some((s) => s.id === p.id))];
      }
    }
  } catch {
    // Blocked or corrupt storage: fall back to the seed.
  }
  return SEED;
}

function loadActiveId(patients: Patient[]): string | null {
  try {
    const id = localStorage.getItem(ACTIVE_KEY);
    if (id && patients.some((p) => p.id === id)) return id;
  } catch {
    // ignore
  }
  return null;
}

function save(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Session-only if storage is unavailable.
  }
}

interface PatientsContextValue {
  patients: Patient[];
  /** The chosen patient, or the first one until a choice is made. */
  activePatient: Patient | null;
  selectPatient: (id: string) => void;
  addPatient: (input: { name: string; relationship: string; age?: number }) => Patient;
}

const PatientsContext = createContext<PatientsContextValue | null>(null);

export function PatientsProvider({ children }: { children: ReactNode }) {
  const [patients, setPatients] = useState<Patient[]>(loadPatients);
  const [activeId, setActiveId] = useState<string | null>(() => loadActiveId(loadPatients()));

  const selectPatient = useCallback((id: string) => {
    setActiveId(id);
    save(ACTIVE_KEY, id);
  }, []);

  const addPatient = useCallback(
    (input: { name: string; relationship: string; age?: number }) => {
      const patient: Patient = {
        id: crypto.randomUUID(),
        name: input.name,
        relationship: input.relationship,
        age: input.age,
        color: PALETTE[patients.length % PALETTE.length],
      };
      const next = [...patients, patient];
      setPatients(next);
      save(PATIENTS_KEY, JSON.stringify(next.filter((p) => !SEED.some((s) => s.id === p.id))));
      return patient;
    },
    [patients],
  );

  const activePatient = useMemo(
    () => patients.find((p) => p.id === activeId) ?? patients[0] ?? null,
    [patients, activeId],
  );

  const value = useMemo(
    () => ({ patients, activePatient, selectPatient, addPatient }),
    [patients, activePatient, selectPatient, addPatient],
  );

  return <PatientsContext.Provider value={value}>{children}</PatientsContext.Provider>;
}

export function usePatients(): PatientsContextValue {
  const ctx = useContext(PatientsContext);
  if (!ctx) throw new Error("usePatients must be used within PatientsProvider");
  return ctx;
}

export function patientSubtitle(p: Patient): string {
  return p.age ? `${p.relationship} · Age ${p.age}` : p.relationship;
}
