interface Props {
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmDialog({ title, message, confirmLabel = "Confirm", danger, busy, onConfirm, onCancel }: Props) {
  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center px-4"
      style={{ background: "rgba(20, 20, 18, 0.35)", backdropFilter: "blur(4px)" }}
      onClick={onCancel}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm rounded-xl border p-5 space-y-3"
        style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)", boxShadow: "var(--dsa-shadow-lg)" }}
      >
        <h3 className="font-semibold text-sm">{title}</h3>
        <p className="text-sm" style={{ color: "var(--dsa-muted)" }}>
          {message}
        </p>
        <div className="flex justify-end gap-2 pt-1">
          <button
            onClick={onCancel}
            disabled={busy}
            className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-50"
            style={{ borderColor: "var(--dsa-border)" }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={busy}
            className="rounded-md px-3 py-1.5 text-sm disabled:opacity-50"
            style={{ background: danger ? "#e11d48" : "var(--dsa-accent)", color: danger ? "white" : "var(--dsa-bg)" }}
          >
            {busy ? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
