import { X } from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { backButtonSupported, tg } from "../tg";

export function Sheet({
  title,
  icon,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  icon?: ReactNode;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
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
      <div className={`sheet__panel ${wide ? "sheet__panel--wide" : ""}`} onClick={(e) => e.stopPropagation()}>
        <div className="sheet__handle" />
        <div className="sheet__header">
          {icon}
          <h2>{title}</h2>
          <button className="icon-btn icon-btn--round" onClick={onClose} aria-label="Yopish">
            <X size={18} />
          </button>
        </div>
        <div className="sheet__body">{children}</div>
      </div>
    </div>
  );
}

/** Kompyuterda yon panel (inline), telefonda pastdan chiqadigan oyna. */
export function Inspector({
  title,
  icon,
  onClose,
  inline,
  children,
}: {
  title: string;
  icon?: ReactNode;
  onClose: () => void;
  inline: boolean;
  children: ReactNode;
}) {
  if (!inline)
    return (
      <Sheet title={title} icon={icon} onClose={onClose}>
        {children}
      </Sheet>
    );
  return (
    <section className="card bb-inspector">
      <div className="bb-inspector__head">
        {icon}
        <h2>{title}</h2>
        <button className="icon-btn icon-btn--round" onClick={onClose} aria-label="Yopish">
          <X size={18} />
        </button>
      </div>
      {children}
    </section>
  );
}
