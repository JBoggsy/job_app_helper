import { useState, useEffect, useCallback } from "react";

/**
 * Toast notification system for displaying non-intrusive alerts.
 *
 * Usage:
 *   const { toasts, addToast, removeToast } = useToast();
 *   addToast({ type: "error", title: "...", message: "...", detail: "..." });
 *
 *   <ToastContainer toasts={toasts} onDismiss={removeToast} />
 */

let _nextId = 1;

export function useToast() {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((toast) => {
    const id = _nextId++;
    setToasts((prev) => [...prev, { id, ...toast }]);
    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return { toasts, addToast, removeToast };
}

// Icon components
function ErrorIcon() {
  return (
    <svg className="w-5 h-5 text-red-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function WarningIcon() {
  return (
    <svg className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
    </svg>
  );
}

function InfoIcon() {
  return (
    <svg className="w-5 h-5 text-blue-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

const ICON_MAP = {
  error: ErrorIcon,
  warning: WarningIcon,
  info: InfoIcon,
};

const BORDER_COLOR_MAP = {
  error: "border-red-400",
  warning: "border-amber-400",
  info: "border-blue-400",
};

function Toast({ toast, onDismiss }) {
  const [expanded, setExpanded] = useState(false);
  const [exiting, setExiting] = useState(false);

  // Auto-dismiss after duration (default 0 = no auto-dismiss for errors)
  useEffect(() => {
    const duration = toast.duration ?? (toast.type === "error" ? 0 : 5000);
    if (duration > 0) {
      const timer = setTimeout(() => {
        setExiting(true);
        setTimeout(() => onDismiss(toast.id), 300);
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [toast, onDismiss]);

  const handleDismiss = () => {
    setExiting(true);
    setTimeout(() => onDismiss(toast.id), 300);
  };

  const IconComponent = ICON_MAP[toast.type] || ErrorIcon;
  const borderColor = BORDER_COLOR_MAP[toast.type] || BORDER_COLOR_MAP.error;

  return (
    <div
      className={`max-w-sm w-full bg-white shadow-lg rounded-lg border-l-4 ${borderColor} pointer-events-auto transition-all duration-300 ${
        exiting ? "opacity-0 translate-x-4" : "opacity-100 translate-x-0"
      }`}
      role="alert"
    >
      <div className="p-4">
        <div className="flex items-start gap-3">
          <IconComponent />
          <div className="flex-1 min-w-0">
            {toast.title && (
              <p className="text-sm font-semibold text-gray-900">{toast.title}</p>
            )}
            {toast.message && (
              <p className="text-sm text-gray-600 mt-0.5">{toast.message}</p>
            )}
            {toast.detail && (
              <>
                <button
                  onClick={() => setExpanded(!expanded)}
                  className="text-xs text-gray-400 hover:text-gray-600 mt-1 underline"
                >
                  {expanded ? "Hide technical details" : "Show technical details"}
                </button>
                {expanded && (
                  <pre className="mt-1 text-xs text-gray-400 bg-gray-50 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all font-mono border border-gray-100">
                    {toast.detail}
                  </pre>
                )}
              </>
            )}
          </div>
          <button
            onClick={handleDismiss}
            className="shrink-0 text-gray-400 hover:text-gray-600"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

export function ToastContainer({ toasts, onDismiss }) {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-3 pointer-events-none">
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

export default ToastContainer;
