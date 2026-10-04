import { useEffect, useRef, type ReactNode } from "react";
import { Icon } from "./Icon";

interface ModalProps {
  title: string;
  eyebrow?: string;
  onClose: () => void;
  children: ReactNode;
  labelledBy?: string;
}

/**
 * Native modal dialog: the browser supplies focus containment, Escape to
 * close and inert background content in all supported desktop browsers.
 */
export function Modal({ title, eyebrow, onClose, children }: ModalProps) {
  const dialog = useRef<HTMLDialogElement>(null);
  const opener = useRef<Element | null>(null);
  useEffect(() => {
    opener.current = document.activeElement;
    const element = dialog.current;
    element?.showModal();
    // React applies autoFocus before showModal() opens the dialog, which has
    // no effect, so move focus to the marked control once the dialog is open.
    element?.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    return () => {
      element?.close();
      if (opener.current instanceof HTMLElement && opener.current.isConnected) opener.current.focus();
    };
  }, []);
  return (
    <dialog
      ref={dialog}
      className="dk-dialog"
      aria-labelledby="dk-dialog-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div className="dk-dialog-header">
        <div>
          {eyebrow && <span className="dk-eyebrow">{eyebrow}</span>}
          <h2 id="dk-dialog-title">{title}</h2>
        </div>
        <button type="button" className="dk-icon-button" aria-label="Close" onClick={onClose}>
          <Icon name="close" />
        </button>
      </div>
      {children}
    </dialog>
  );
}
