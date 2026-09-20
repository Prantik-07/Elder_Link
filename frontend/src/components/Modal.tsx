import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

export function Modal({
  onClose,
  titleId,
  children,
  maxWidthClass = "max-w-md",
}: {
  onClose: () => void;
  titleId: string;
  children: ReactNode;
  maxWidthClass?: string;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  // Callers pass a fresh onClose every render. Depending on it directly would
  // re-run the effect on each keystroke and re-focus the dialog, stealing focus
  // from the input being typed in.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseRef.current();
    };
    document.addEventListener("keydown", onKeyDown);
    // Don't steal focus from a field that already autofocused.
    if (!dialogRef.current?.contains(document.activeElement)) dialogRef.current?.focus();
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-[var(--color-ink)]/40 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={`relative w-full ${maxWidthClass} rounded-2xl border bg-[var(--color-paper)] p-6 shadow-[var(--shadow-panel)] outline-none`}
        style={{ borderColor: "var(--color-line)" }}
      >
        {children}
      </div>
    </div>,
    document.body,
  );
}
