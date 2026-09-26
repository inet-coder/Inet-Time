import type { ActiveService, CatalogService } from "../api";

const STATUS: Record<string, { text: string; cls: string }> = {
  ACTIVE: { text: "Faol", cls: "chip--ok" },
  STARTING: { text: "Yoqilmoqda…", cls: "chip--wait" },
  ERROR: { text: "Xatolik", cls: "chip--err" },
};

type Props = {
  catalog: CatalogService[];
  services: ActiveService[];
  onOpen: (code: string) => void;
  onToggle: (code: string, active: ActiveService | undefined) => void;
};

export function ServiceGrid({ catalog, services, onOpen, onToggle }: Props) {
  return (
    <div className="grid">
      {catalog.map((svc) => {
        const active = services.find((s) => s.service_code === svc.code);
        const status = active ? STATUS[active.status] : null;
        return (
          <div key={svc.code} className={`card service ${active ? "is-active" : ""} ${svc.unlocked ? "" : "is-locked"}`} onClick={() => onOpen(svc.code)}>
            <div className="service__top">
              <span className="service__icon">{svc.icon}</span>
              {svc.unlocked ? (
                <button
                  className={`switch ${active ? "is-on" : ""}`}
                  aria-label={active ? "O'chirish" : "Yoqish"}
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggle(svc.code, active);
                  }}
                >
                  <i />
                </button>
              ) : (
                <span className="chip chip--pro">PRO</span>
              )}
            </div>
            <div className="service__title">{svc.title}</div>
            <div className="service__desc">{status ? <span className={`chip ${status.cls}`}>{status.text}</span> : svc.desc}</div>
          </div>
        );
      })}
    </div>
  );
}
