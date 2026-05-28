import { useEffect, type ReactNode } from "react";

type ModalProps = {
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
};

export function Modal({ title, children, footer, onClose }: ModalProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true">
      <button
        type="button"
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-label="Close dialog"
      />
      <div className="absolute left-1/2 top-1/2 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-[var(--radius-xl)] border border-border bg-surface p-6 shadow-card-lg">
        <h2 className="mb-4 text-lg font-bold text-fg">{title}</h2>
        <div className="space-y-4">{children}</div>
        {footer ? <div className="mt-6 flex justify-end gap-3">{footer}</div> : null}
      </div>
    </div>
  );
}
