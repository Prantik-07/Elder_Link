import { SearchX } from "lucide-react";

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center gap-2.5 rounded-xl border border-dashed px-4 py-10 text-center" style={{ borderColor: "var(--color-line)" }}>
      <SearchX size={22} className="text-[var(--color-ink-muted)]" aria-hidden="true" />
      <p className="text-[13.5px] text-[var(--color-ink-muted)]">{message}</p>
    </div>
  );
}
