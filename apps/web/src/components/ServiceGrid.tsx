import { CircleAlert, Crown, LoaderCircle } from "lucide-react";
import type { ActiveService, CatalogService } from "../api";
import { ServiceIcon } from "../icons";

type Props = {
  catalog: CatalogService[];
  services: ActiveService[];
  onOpen: (code: string) => void;
  onToggle: (code: string, active: ActiveService | undefined) => void;
};

function Status({ active }: { active: ActiveService }) {
  if (active.status === "ERROR")
    return (
      <span className="status status--err">
        <CircleAlert size={13} /> Xatolik
      </span>
    );
  if (active.status === "STARTING")
    return (
      <span className="status status--wait">
        <LoaderCircle size={13} className="spin" /> Yoqilmoqda
      </span>
    );
  return (
    <span className="status status--ok">
      <i className="pulse" /> Ishlayapti
    </span>
  );
}

export function ServiceGrid({ catalog, services, onOpen, onToggle }: Props) {
  return (
    <div className="grid">
      {catalog.map((svc) => {
        const active = services.find((s) => s.service_code === svc.code);
        return (
          <div
            key={svc.code}
            className={`card service ${active ? "is-active" : ""} ${svc.unlocked ? "" : "is-locked"}`}
            onClick={() => onOpen(svc.code)}
          >
            <div className="service__top">
              <ServiceIcon code={svc.code} />
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
                <span className="pro-badge">
                  <Crown size={11} strokeWidth={2.5} /> PRO
                </span>
              )}
            </div>
            <div className="service__title">{svc.title}</div>
            <div className="service__desc">{active ? <Status active={active} /> : svc.desc}</div>
          </div>
        );
      })}
    </div>
  );
}
