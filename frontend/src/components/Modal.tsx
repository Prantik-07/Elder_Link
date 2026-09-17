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

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    dialogRef.current?.focus();
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

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
