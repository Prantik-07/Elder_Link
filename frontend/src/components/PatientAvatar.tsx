import type { Patient } from "../state/PatientsContext";

export function PatientAvatar({ patient, size = 36 }: { patient: Patient; size?: number }) {
  if (patient.avatar) {
    return (
      <img
        src={patient.avatar}
        alt=""
        aria-hidden="true"
        width={size}
        height={size}
        className="shrink-0 rounded-full"
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-[var(--color-paper)]"
      style={{
        width: size,
        height: size,
        backgroundColor: patient.color,
        fontSize: Math.max(12, size * 0.4),
      }}
      aria-hidden="true"
    >
      {patient.name.slice(0, 1).toUpperCase()}
    </span>
  );
}
