import { useState, type FormEvent } from "react";
import { Modal } from "./Modal";
import { RELATIONSHIPS, type Patient, usePatients } from "../state/PatientsContext";

export function AddPatientModal({
  onClose,
  onAdded,
}: {
  onClose: () => void;
  onAdded?: (patient: Patient) => void;
}) {
  const { addPatient } = usePatients();
  const [name, setName] = useState("");
  const [relationship, setRelationship] = useState(RELATIONSHIPS[0]);
  const [age, setAge] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    const parsedAge = Number.parseInt(age, 10);
    const patient = addPatient({
      name: trimmed,
      relationship,
      age: Number.isFinite(parsedAge) && parsedAge > 0 ? parsedAge : undefined,
    });
    onAdded?.(patient);
    onClose();
  };

  const field = "mt-1.5 w-full rounded-lg border bg-[var(--color-paper)] px-3 py-2 text-[14px] font-normal";
  const border = { borderColor: "var(--color-line)" };

  return (
    <Modal onClose={onClose} titleId="add-patient-title">
      <form onSubmit={submit}>
        <h2 id="add-patient-title" className="font-display text-[20px] text-[var(--color-ink)]">
          Add a patient
        </h2>
        <p className="mt-1.5 text-[13.5px] text-[var(--color-ink-soft)]">
          Who are you looking after? Each person keeps their own updates, timeline and handoff.
        </p>
        <label className="mt-4 block text-[13px] font-medium text-[var(--color-ink)]">
          Name or nickname
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            autoFocus
            autoComplete="off"
            className={field}
            style={border}
          />
        </label>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <label className="block text-[13px] font-medium text-[var(--color-ink)]">
            Relationship
            <select
              value={relationship}
              onChange={(e) => setRelationship(e.target.value)}
              className={field}
              style={border}
            >
              {RELATIONSHIPS.map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </label>
          <label className="block text-[13px] font-medium text-[var(--color-ink)]">
            Age (optional)
            <input
              value={age}
              onChange={(e) => setAge(e.target.value)}
              inputMode="numeric"
              autoComplete="off"
              className={field}
              style={border}
            />
          </label>
        </div>
        <div className="mt-6 flex flex-col gap-2.5 sm:flex-row">
          <button
            type="submit"
            className="w-full rounded-full px-5 py-3 text-[13.5px] font-semibold text-[var(--color-paper)] sm:w-auto sm:py-2.5"
            style={{ backgroundColor: "var(--color-teal)" }}
          >
            Add patient
          </button>
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-full border px-5 py-3 text-[13.5px] font-semibold text-[var(--color-ink-soft)] sm:w-auto sm:py-2.5"
            style={border}
          >
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}
