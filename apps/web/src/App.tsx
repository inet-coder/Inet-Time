import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, authenticate, type ActiveService, type State } from "./api";
import {
  EmojiEditor,
  OnlineEditor,
  PhotoEditor,
  PlaylistEditor,
  ScheduleEditor,
  TemplateEditor,
  type EditorProps,
} from "./components/Editors";
import { PlansView } from "./components/PlansView";
import { ProfileCard } from "./components/ProfileCard";
import { ServiceGrid } from "./components/ServiceGrid";
import { Sheet } from "./components/Sheet";
import { Timeline } from "./components/Timeline";
import { buildProfile, nextChangeAt, type Mode, type Overrides } from "./profile";
import { confirmDialog, haptic, openBot, tg } from "./tg";
import { money, whenText } from "./util";

const EDITORS: Record<string, (p: EditorProps) => JSX.Element> = {
  template: TemplateEditor,
  playlist: PlaylistEditor,
  schedule: ScheduleEditor,
  photo: PhotoEditor,
  emoji: EmojiEditor,
  online: OnlineEditor,
};

type Tab = "profile" | "services" | "plan";
type Toast = { text: string; kind: "ok" | "err" } | null;

function useToast(): [Toast, (text: string, kind?: "ok" | "err") => void] {
  const [toast, setToast] = useState<Toast>(null);
  const show = useCallback((text: string, kind: "ok" | "err" = "ok") => {
    setToast({ text, kind });
    setTimeout(() => setToast(null), 3500);
  }, []);
  return [toast, show];
}

export function App() {
  const [authed, setAuthed] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    tg?.ready();
    tg?.expand();
    authenticate()
      .then(() => setAuthed(true))
      .catch((e: Error) => setAuthError(e.message));
  }, []);

  if (authError) {
    return (
      <div className="empty">
        <div className="empty__icon">🔒</div>
        <p>{authError}</p>
      </div>
    );
  }
  if (!authed) return <Loader />;
  return <Main />;
}

function Loader() {
  return (
    <div className="empty">
      <div className="spinner" />
    </div>
  );
}

function Main() {
  const queryClient = useQueryClient();
  const [accountId, setAccountId] = useState<number | undefined>();
  const [tab, setTab] = useState<Tab>("profile");
  const [mode, setMode] = useState<Mode>("now");
  const [openCode, setOpenCode] = useState<string | null>(null);
  const [toast, showToast] = useToast();

  const { data: state, refetch } = useQuery({
    queryKey: ["state", accountId],
    queryFn: () => api.state(accountId),
    refetchInterval: 20000,
  });

  const refresh = useCallback(() => {
    refetch();
    // Worker xizmatni 1–2 soniyada faollashtiradi — holat yangilansin.
    setTimeout(() => queryClient.invalidateQueries({ queryKey: ["state"] }), 2000);
  }, [refetch, queryClient]);

  if (!state) return <Loader />;
  if (!state.account) return <NoAccount state={state} />;

  const services = state.services ?? [];
  const toggle = async (code: string, active: ActiveService | undefined) => {
    haptic();
    const meta = state.catalog.find((c) => c.code === code)!;
    if (active) {
      if (!(await confirmDialog(`${meta.title} o'chirilsinmi? Profil asl holiga qaytadi.`))) return;
      try {
        await api.stop(active.id);
        showToast(`${meta.title} o'chirildi`);
        refresh();
      } catch (e) {
        showToast((e as Error).message, "err");
      }
      return;
    }
    // Oddiy xizmatlar bir bosishda standart shablon bilan yoqiladi; qolganlari sozlash oynasini ochadi.
    if (meta.kind === "template" || meta.kind === "online") {
      try {
        await api.enable({
          account_id: state.account!.id,
          service_code: code,
          items: [{ template: meta.kind === "online" ? "true" : meta.default! }],
        });
        haptic("success");
        showToast(`${meta.title} yoqildi`);
        refresh();
      } catch (e) {
        haptic("error");
        showToast((e as Error).message, "err");
      }
    } else setOpenCode(code);
  };

  return (
    <div className="app">
      {state.accounts.length > 1 && (
        <select className="account-select" value={state.account.id} onChange={(e) => setAccountId(Number(e.target.value))}>
          {state.accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.username ? `@${a.username}` : a.first_name}
            </option>
          ))}
        </select>
      )}

      {tab === "profile" && <ProfileTab state={state} mode={mode} setMode={setMode} onOpen={setOpenCode} />}
      {tab === "services" && (
        <div className="stack">
          <p className="hint">Tugmani bosib yoqing, kartani bosib sozlang. Oddiy xizmatlar standart shablon bilan darhol yoqiladi.</p>
          <h3 className="section-title">Asosiy</h3>
          <ServiceGrid
            catalog={state.catalog.filter((c) => !c.flag)}
            services={services}
            onOpen={setOpenCode}
            onToggle={toggle}
          />
          <h3 className="section-title">⭐ Pro</h3>
          <ServiceGrid
            catalog={state.catalog.filter((c) => c.flag)}
            services={services}
            onOpen={setOpenCode}
            onToggle={toggle}
          />
        </div>
      )}
      {tab === "plan" && <PlansView state={state} refresh={refresh} toast={showToast} />}

      {openCode && (
        <ServiceSheet
          state={state}
          code={openCode}
          onClose={() => setOpenCode(null)}
          onDone={(text) => {
            setOpenCode(null);
            showToast(text);
            refresh();
          }}
          onError={(text) => showToast(text, "err")}
          goPlans={() => {
            setOpenCode(null);
            setTab("plan");
          }}
        />
      )}

      {toast && <div className={`toast toast--${toast.kind}`}>{toast.text}</div>}

      <nav className="tabbar">
        {(
          [
            ["profile", "👤", "Profil"],
            ["services", "⚙️", "Xizmatlar"],
            ["plan", "💎", "Tarif"],
          ] as [Tab, string, string][]
        ).map(([key, icon, label]) => (
          <button key={key} className={tab === key ? "is-active" : ""} onClick={() => setTab(key)}>
            <span>{icon}</span>
            {label}
          </button>
        ))}
      </nav>
    </div>
  );
}

function ProfileTab({ state, mode, setMode, onOpen }: { state: State; mode: Mode; setMode: (m: Mode) => void; onOpen: (c: string) => void }) {
  const profile = useMemo(() => buildProfile(state, mode), [state, mode]);
  const nextAt = nextChangeAt(state);
  const catalog = Object.fromEntries(state.catalog.map((c) => [c.code, c]));
  const services = state.services ?? [];

  return (
    <div className="stack">
      <div className="segmented segmented--wide">
        <button className={mode === "now" ? "is-selected" : ""} onClick={() => setMode("now")}>
          Hozir
        </button>
        <button className={mode === "next" ? "is-selected" : ""} onClick={() => setMode("next")} disabled={!nextAt}>
          Keyingi {nextAt ? `· ${whenText(nextAt, state.timezone)}` : ""}
        </button>
      </div>
      <section className="card card--flush">
        <ProfileCard profile={profile} />
      </section>
      <p className="hint center">
        {mode === "now" ? "Boshqalar profilingizni hozir shunday ko'rishadi." : "Keyingi o'zgarishdan keyin profilingiz shunday bo'ladi."}
      </p>

      <h3 className="section-title">Keyingi o'zgarishlar</h3>
      <section className="card">
        <Timeline state={state} />
      </section>

      <h3 className="section-title">Faol xizmatlar ({services.length})</h3>
      {services.length === 0 ? (
        <p className="hint center">Hali xizmat yoqilmagan — «Xizmatlar» bo'limidan tanlang.</p>
      ) : (
        <section className="card card--list">
          {services.map((s) => (
            <button key={s.id} className="list-item" onClick={() => onOpen(s.service_code)}>
              <span className="list-item__icon">{catalog[s.service_code]?.icon}</span>
              <span className="list-item__body">
                <span className="list-item__title">{catalog[s.service_code]?.title}</span>
                <span className="list-item__sub">
                  {s.status === "ERROR" ? "⚠️ Xatolik — qayta sozlang" : s.status === "STARTING" ? "⏳ Yoqilmoqda…" : previewText(s)}
                </span>
              </span>
              <span className="list-item__chev">›</span>
            </button>
          ))}
        </section>
      )}

      <div className="card mini-plan">
        <span>
          💎 {state.plan.name} · 💰 {money(state.user.balance)}
        </span>
      </div>
    </div>
  );
}

function previewText(s: ActiveService): string {
  if (s.field === "photo") return `${s.actions.length} ta rasm`;
  if (s.field === "emoji_status") return `${s.actions.length} ta emoji`;
  if (s.field === "online") return "doim online";
  return s.preview.current;
}

function ServiceSheet({
  state,
  code,
  onClose,
  onDone,
  onError,
  goPlans,
}: {
  state: State;
  code: string;
  onClose: () => void;
  onDone: (text: string) => void;
  onError: (text: string) => void;
  goPlans: () => void;
}) {
  const service = state.catalog.find((c) => c.code === code)!;
  const active = (state.services ?? []).find((s) => s.service_code === code);
  const [overrides, setOverridesState] = useState<Overrides>({});
  const [busy, setBusy] = useState(false);
  const setOverrides = useCallback((o: Overrides) => setOverridesState(o), []);
  const draftProfile = useMemo(() => buildProfile(state, "now", overrides), [state, overrides]);
  const Editor = EDITORS[service.kind];

  const save: EditorProps["save"] = async (body) => {
    setBusy(true);
    try {
      await api.enable({ account_id: state.account!.id, service_code: code, ...body });
      haptic("success");
      onDone(`${service.title} ${active ? "saqlandi" : "yoqildi"}`);
    } catch (e) {
      haptic("error");
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    if (!active || !(await confirmDialog(`${service.title} o'chirilsinmi? Profil asl holiga qaytadi.`))) return;
    setBusy(true);
    try {
      await api.stop(active.id);
      onDone(`${service.title} o'chirildi`);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet title={`${service.icon} ${service.title}`} onClose={onClose}>
      <p className="hint">{service.desc}</p>
      {!service.unlocked ? (
        <div className="stack">
          <div className="notice">🔒 Bu xizmat Pro tarifda ochiladi.</div>
          <button className="btn btn--primary" onClick={goPlans}>
            💎 Tariflarni ko'rish
          </button>
        </div>
      ) : (
        <>
          <div className="sheet__preview">
            <div className="label">Saqlagandan keyin profilingiz:</div>
            <ProfileCard profile={draftProfile} compact />
          </div>
          <Editor state={state} service={service} active={active} setOverrides={setOverrides} save={save} busy={busy} />
          {active && (
            <button className="btn btn--danger" disabled={busy} onClick={stop}>
              O'chirish
            </button>
          )}
        </>
      )}
    </Sheet>
  );
}

function NoAccount({ state }: { state: State }) {
  return (
    <div className="empty">
      <div className="empty__icon">📱</div>
      <h2>Akkaunt ulanmagan</h2>
      <p>Avval botda Telegram akkauntingizni ulang — telefon raqam yoki QR kod orqali.</p>
      <button className="btn btn--primary" onClick={() => openBot(state.bot_username)}>
        Botga o'tish
      </button>
    </div>
  );
}
