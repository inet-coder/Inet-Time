import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronRight,
  CircleAlert,
  CircleCheck,
  Crown,
  Gem,
  LayoutGrid,
  LoaderCircle,
  Lock,
  ShieldAlert,
  ShieldCheck,
  Smartphone,
  UserRound,
  Wallet,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, authenticate, type ActiveService, type CatalogService, type State } from "./api";
import {
  EmojiEditor,
  OnlineEditor,
  PhotoEditor,
  PlaylistEditor,
  ScheduleEditor,
  TemplateEditor,
  type EditorProps,
} from "./components/Editors";
import { AdminView } from "./components/AdminView";
import { AIReplyEditor, StoriesEditor } from "./components/AIEditors";
import { PlansView } from "./components/PlansView";
import { ProfileCard } from "./components/ProfileCard";
import { ServiceGrid } from "./components/ServiceGrid";
import { ServiceIcon } from "./icons";
import { Sheet } from "./components/Sheet";
import { Timeline } from "./components/Timeline";
import { buildProfile, nextChangeAt, unlockingPlan, type Mode, type Overrides } from "./profile";
import { confirmDialog, haptic, matchChrome, openBot, tg } from "./tg";
import { money, whenText } from "./util";

// Profil maydonini o'zgartirmaydigan xizmatlar — o'z oynasi bor, "profil ko'rinishi" ko'rsatilmaydi.
const SPECIAL_EDITORS: Record<string, typeof AIReplyEditor> = { ai_reply: AIReplyEditor, stories: StoriesEditor };

const EDITORS: Record<string, (p: EditorProps) => JSX.Element> = {
  template: TemplateEditor,
  playlist: PlaylistEditor,
  schedule: ScheduleEditor,
  photo: PhotoEditor,
  emoji: EmojiEditor,
  online: OnlineEditor,
};

type Tab = "profile" | "services" | "plan" | "admin";

const TABS: [Tab, typeof UserRound, string][] = [
  ["profile", UserRound, "Profil"],
  ["services", LayoutGrid, "Xizmatlar"],
  ["plan", Gem, "Tarif"],
  ["admin", ShieldCheck, "Admin"],
];
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
    matchChrome();
    authenticate()
      .then(() => setAuthed(true))
      .catch((e: Error) => setAuthError(e.message));
  }, []);

  if (authError) {
    return (
      <div className="empty">
        <div className="empty__icon">
          <ShieldAlert size={34} />
        </div>
        <h2>Kirish tasdiqlanmadi</h2>
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

  // AI avto-javob automation emas — kartada "yoqilgan" ko'rinishi uchun sun'iy yozuv qo'shamiz.
  const services: ActiveService[] = [
    ...(state.services ?? []),
    ...(state.ai_reply?.enabled ? [aiService()] : []),
  ];
  const lockLabel = (svc: CatalogService) => (unlockingPlan(state, svc.flag)?.name ?? "PRO").toUpperCase();
  const toggle = async (code: string, active: ActiveService | undefined) => {
    haptic();
    const meta = state.catalog.find((c) => c.code === code)!;
    if (active && code === "ai_reply") {
      try {
        const current = await api.ai(state.account!.id);
        await api.saveAi(state.account!.id, { ...current.settings, enabled: false });
        showToast("AI avto-javob o'chirildi");
        refresh();
      } catch (e) {
        showToast((e as Error).message, "err");
      }
      return;
    }
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
      {state.account && state.accounts.length > 1 && (
        <select className="account-select" value={state.account.id} onChange={(e) => setAccountId(Number(e.target.value))}>
          {state.accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.username ? `@${a.username}` : a.first_name}
            </option>
          ))}
        </select>
      )}

      <Header state={state} title={TABS.find(([k]) => k === tab)![2]} onPlan={() => setTab("plan")} />

      {!state.account && (tab === "profile" || tab === "services") && <NoAccount state={state} />}
      {state.account && tab === "profile" && <ProfileTab state={state} mode={mode} setMode={setMode} onOpen={setOpenCode} />}
      {state.account && tab === "services" && (
        <div className="stack">
          <p className="hint">Kalitni bosib yoqing, kartani bosib sozlang. Oddiy xizmatlar standart shablon bilan darhol yoqiladi.</p>
          <h3 className="section-title">Sizda mavjud</h3>
          <ServiceGrid
            catalog={state.catalog.filter((c) => c.unlocked)}
            services={services}
            lockLabel={lockLabel}
            onOpen={setOpenCode}
            onToggle={toggle}
          />
          {state.catalog.some((c) => !c.unlocked) && (
            <>
              <h3 className="section-title section-title--pro">
                <Crown size={14} /> Tarifni yangilab oching
              </h3>
              <ServiceGrid
                catalog={state.catalog.filter((c) => !c.unlocked)}
                services={services}
                lockLabel={lockLabel}
                onOpen={setOpenCode}
                onToggle={toggle}
              />
            </>
          )}
        </div>
      )}
      {tab === "plan" && <PlansView state={state} refresh={refresh} toast={showToast} />}
      {tab === "admin" && state.is_admin && <AdminView toast={showToast} />}

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

      {toast && (
        <div className={`toast toast--${toast.kind}`}>
          {toast.kind === "ok" ? <CircleCheck size={18} /> : <CircleAlert size={18} />}
          <span>{toast.text}</span>
        </div>
      )}

      <nav className="tabbar">
        {TABS.filter(([key]) => key !== "admin" || state.is_admin).map(([key, Icon, label]) => (
          <button
            key={key}
            className={tab === key ? "is-active" : ""}
            onClick={() => {
              haptic("select");
              setTab(key);
            }}
          >
            <Icon size={22} strokeWidth={tab === key ? 2.4 : 1.9} />
            {label}
          </button>
        ))}
      </nav>
    </div>
  );
}

function Header({ state, title, onPlan }: { state: State; title: string; onPlan: () => void }) {
  const isPro = state.plan.code === "pro";
  return (
    <header className="header">
      <h1>{title}</h1>
      <button className={`plan-pill ${isPro ? "plan-pill--pro" : ""}`} onClick={onPlan}>
        {isPro ? <Crown size={14} strokeWidth={2.4} /> : <Zap size={14} strokeWidth={2.4} />}
        {state.plan.name}
      </button>
    </header>
  );
}

function Stat({ icon, value, label }: { icon: ReactNode; value: ReactNode; label: string }) {
  return (
    <div className="stat">
      <span className="stat__icon">{icon}</span>
      <span className="stat__value">{value}</span>
      <span className="stat__label">{label}</span>
    </div>
  );
}

function ProfileTab({ state, mode, setMode, onOpen }: { state: State; mode: Mode; setMode: (m: Mode) => void; onOpen: (c: string) => void }) {
  const profile = useMemo(() => buildProfile(state, mode), [state, mode]);
  const nextAt = nextChangeAt(state);
  const catalog = Object.fromEntries(state.catalog.map((c) => [c.code, c]));
  const services = [...(state.services ?? []), ...(state.ai_reply?.enabled ? [aiService()] : [])];
  const active = services.filter((s) => s.status === "ACTIVE").length;

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
      <section className={`card card--flush profile-wrap ${mode === "next" ? "is-next" : ""}`}>
        <ProfileCard profile={profile} key={mode} />
      </section>
      <p className="hint center">
        {mode === "now" ? "Boshqalar profilingizni hozir shunday ko'rishadi." : "Keyingi o'zgarishdan keyin profilingiz shunday bo'ladi."}
      </p>

      <div className="stats">
        <Stat icon={<Zap size={16} />} value={active} label="faol xizmat" />
        <Stat icon={<Crown size={16} />} value={state.plan.name} label="tarif" />
        <Stat icon={<Wallet size={16} />} value={money(state.user.balance).replace(" so'm", "")} label="so'm balans" />
      </div>

      <h3 className="section-title">Keyingi o'zgarishlar</h3>
      <section className="card">
        <Timeline state={state} />
      </section>

      <h3 className="section-title">Faol xizmatlar ({services.length})</h3>
      {services.length === 0 ? (
        <div className="card placeholder">
          <LayoutGrid size={22} />
          <span>Hali xizmat yoqilmagan — «Xizmatlar» bo'limidan tanlang</span>
        </div>
      ) : (
        <section className="card card--list">
          {services.map((s) => (
            <button key={s.id} className="list-item" onClick={() => onOpen(s.service_code)}>
              <ServiceIcon code={s.service_code} size={36} />
              <span className="list-item__body">
                <span className="list-item__title">{catalog[s.service_code]?.title}</span>
                <span className={`list-item__sub ${s.status === "ERROR" ? "is-err" : ""}`}>
                  {s.status === "ERROR" ? (
                    <>
                      <CircleAlert size={13} /> Xatolik — qayta sozlang
                    </>
                  ) : s.status === "STARTING" ? (
                    <>
                      <LoaderCircle size={13} className="spin" /> Yoqilmoqda
                    </>
                  ) : (
                    previewText(s)
                  )}
                </span>
              </span>
              <ChevronRight size={18} className="list-item__chev" />
            </button>
          ))}
        </section>
      )}
    </div>
  );
}

function aiService(): ActiveService {
  return {
    id: -1,
    service_code: "ai_reply",
    status: "ACTIVE",
    field: "ai",
    template: "",
    selection_strategy: "NONE",
    interval_seconds: null,
    error_message: null,
    actions: [],
    preview: { field: "ai", current: "", next: null, next_at: null },
  };
}

function previewText(s: ActiveService): string {
  if (s.service_code === "ai_reply") return "shaxsiy chatlarda javob beradi";
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
  const unlock = unlockingPlan(state, service.flag);
  const Special = SPECIAL_EDITORS[service.kind];
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
    <Sheet title={service.title} icon={<ServiceIcon code={code} size={34} />} onClose={onClose}>
      <p className="hint">{service.desc}</p>
      {!service.unlocked ? (
        <div className="stack">
          <div className="locked">
            <span className="locked__icon">
              <Lock size={22} />
            </span>
            <b>Bu xizmat {unlock?.name ?? "yuqoriroq"} tarifida ochiladi</b>
            {unlock && (
              <span className="hint">
                {unlock.name}: {String(unlock.flags.account_limit)} ta akkaunt, bir vaqtda {String(unlock.flags.scheduler_limit)} ta xizmat —{" "}
                {money(unlock.final_price)} / {unlock.duration_days} kun
              </span>
            )}
          </div>
          <button className="btn btn--gold" onClick={goPlans}>
            <Crown size={18} /> Tariflarni ko'rish
          </button>
        </div>
      ) : Special ? (
        <Special state={state} onDone={onDone} onError={onError} />
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
      <div className="empty__icon">
        <Smartphone size={34} />
      </div>
      <h2>Akkaunt ulanmagan</h2>
      <p>Avval botda Telegram akkauntingizni ulang — telefon raqam yoki QR kod orqali.</p>
      <button className="btn btn--primary" onClick={() => openBot(state.bot_username)}>
        Botga o'tish
      </button>
    </div>
  );
}
