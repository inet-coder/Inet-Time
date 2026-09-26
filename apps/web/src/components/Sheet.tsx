import { useEffect, type ReactNode } from "react";
import { backButtonSupported, tg } from "../tg";

export function Sheet({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    // Telegram'ning o'z "orqaga" tugmasi ham oynani yopsin.
    if (!backButtonSupported()) return;
    tg!.BackButton.show();
    tg!.BackButton.onClick(onClose);
    return () => {
      tg!.BackButton.offClick(onClose);
      tg!.BackButton.hide();
    };
  }, [onClose]);

  return (
    <div className="sheet" onClick={onClose}>
      <div className="sheet__panel" onClick={(e) => e.stopPropagation()}>
        <div className="sheet__handle" />
        <div className="sheet__header">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Yopish">
            ✕
          </button>
        </div>
        <div className="sheet__body">{children}</div>
      </div>
    </div>
  );
}
