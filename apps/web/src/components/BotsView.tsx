import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Bot,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  ExternalLink,
  FileText,
  Globe,
  Home,
  ImagePlus,
  Keyboard,
  LayoutGrid,
  Link2,
  MessageSquareText,
  Plus,
  Send,
  Settings2,
  Star,
  Trash2,
  Undo2,
  Users,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  mediaUrl,
  type BotAction,
  type BotButton,
  type BotDetail,
  type BotMenu,
  type BotPage,
  type BotsList,
  type State,
} from "../api";
import { confirmDialog, haptic, tg } from "../tg";
import { fileToJpegBase64 } from "../util";
import { Sheet } from "./Sheet";
import { WebAppPanel } from "./WebAppBuilder";

type Toast = (text: string, kind?: "ok" | "err") => void;

const MAX_ROWS = 10;
const MAX_PER_ROW = 4;

const ACTIONS: { code: BotAction; title: string; icon: typeof FileText }[] = [
  { code: "page", title: "Sahifa", icon: FileText },
  { code: "url", title: "Havola", icon: Link2 },
  { code: "feedback", title: "Adminga yozish", icon: MessageSquareText },
  { code: "back", title: "Orqaga", icon: Undo2 },
  { code: "home", title: "Bosh menyu", icon: Home },
  { code: "webapp", title: "Web App", icon: Globe },
];

const STATUS_TEXT = { active: "Ishlayapti", paused: "To'xtatilgan", error: "Xatolik" } as const;

function openLink(url: string) {
  if (url.startsWith("https://t.me/") && tg) tg.openTelegramLink(url);
  else if (tg?.openLink) tg.openLink(url);
  else window.open(url, "_blank");
}

function newId(): string {
  return "p" + Math.random().toString(16).slice(2, 8);
}

function clone<T>(v: T): T {
  return JSON.parse(JSON.stringify(v));
}

// ============================================================
// Ro'yxat
// ============================================================

export function BotsView({ state, toast, goPlans }: { state: State; toast: Toast; goPlans: () => void }) {
  const [openId, setOpenId] = useState<number | null>(null);
  const [connecting, setConnecting] = useState(false);
  const { data, refetch } = useQuery({ queryKey: ["bots"], queryFn: api.bots });

  if (openId !== null)
    return (
      <BotEditor
        botId={openId}
        variables={data?.variables ?? []}
        toast={toast}
        onBack={() => {
          setOpenId(null);
          refetch();
        }}
      />
    );
  if (!data) return <div className="spinner spinner--center" />;

  const canAdd = data.bots.length < data.limit;
  return (
    <div className="stack">
      {data.bots.length === 0 ? (
        <section className="card bb-hero">
          <span className="bb-hero__icon">
            <LayoutGrid size={30} />
          </span>
          <h2>O'z botingizni yarating</h2>
          <p className="hint">
            Dasturlashsiz: sahifalar, tugmalar, rasmlar, ichma-ich menyular, buyurtma qabul qilish va obunachilarga xabar
            yuborish.
          </p>
          <ol className="bb-steps">
            <li>
              <b>@BotFather</b> da <code>/newbot</code> — bot yarating
            </li>
            <li>U bergan tokenni nusxalang</li>
            <li>Shablon tanlab, tokenni shu yerga qo'ying</li>
            <li>Menyuni quring — bot darhol ishlaydi</li>
          </ol>
        </section>
      ) : (
        <section className="card card--list">
          {data.bots.map((b) => (
            <button key={b.id} className="list-item" onClick={() => setOpenId(b.id)}>
              <span className="bb-avatar">
                <Bot size={20} />
              </span>
              <span className="list-item__body">
                <span className="list-item__title">{b.name}</span>
                <span className={`list-item__sub ${b.status === "error" ? "is-err" : ""}`}>
                  @{b.username} · <i className={`bb-dot bb-dot--${b.status}`} /> {STATUS_TEXT[b.status]} · {b.subscribers} obunachi
                </span>
              </span>
              <ChevronRight size={18} className="list-item__chev" />
            </button>
          ))}
        </section>
      )}

      <p className="hint center">
        {data.plan_name} tarifi: {data.bots.length}/{data.limit} bot · har birida {data.pages_limit} tagacha sahifa
      </p>
      {canAdd ? (
        <button className="btn btn--primary" onClick={() => setConnecting(true)}>
          <Plus size={18} /> Bot ulash
        </button>
      ) : (
        <button className="btn btn--gold" onClick={goPlans}>
          {data.limit === 0 ? "Bot konstruktori uchun tarifni yangilang" : "Ko'proq bot uchun tarifni yangilang"}
        </button>
      )}

      {connecting && (
        <ConnectSheet
          data={data}
          onClose={() => setConnecting(false)}
          onDone={(bot) => {
            setConnecting(false);
            toast(`@${bot.username} ulandi`);
            refetch();
            setOpenId(bot.id);
          }}
        />
      )}
      {state.bot_username && data.bots.length > 0 && (
        <p className="hint center">Buyurtma va xabarlar sizga o'z botingiz orqali keladi — unga bir marta /start bosing.</p>
      )}
    </div>
  );
}

function ConnectSheet({ data, onClose, onDone }: { data: BotsList; onClose: () => void; onDone: (bot: BotDetail) => void }) {
  const [template, setTemplate] = useState("blank");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const bot = await api.connectBot(token.trim(), template);
      haptic("success");
      onDone(bot);
    } catch (e) {
      haptic("error");
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet title="Bot ulash" icon={<Bot size={20} />} onClose={onClose}>
      <div className="stack">
        <span className="label">1. Shablon</span>
        <div className="bb-templates">
          {data.templates.map((t) => (
            <button key={t.code} className={`bb-template ${template === t.code ? "is-selected" : ""}`} onClick={() => setTemplate(t.code)}>
              <span className="bb-template__icon">{t.icon}</span>
              <b>{t.title}</b>
              <span className="hint">{t.desc}</span>
              <span className="bb-template__meta">{t.pages} sahifa</span>
            </button>
          ))}
        </div>

        <span className="label">2. Bot tokeni</span>
        <button className="btn btn--ghost btn--compact" onClick={() => openLink("https://t.me/BotFather")}>
          <ExternalLink size={16} /> @BotFather'ni ochish
        </button>
        <p className="hint">
          @BotFather → <code>/newbot</code> → nom va username bering → u yuborgan <b>token</b>ni nusxalab qo'ying.
        </p>
        <textarea
          className="input input--code"
          rows={2}
          placeholder="1234567890:AAH..."
          value={token}
          onChange={(e) => setToken(e.target.value)}
        />
        {error && <div className="field-error">{error}</div>}
        <button className="btn btn--primary" disabled={busy || token.trim().length < 20} onClick={submit}>
          {busy ? "Tekshirilmoqda…" : "Ulash"}
        </button>
        <p className="hint">Token shifrlangan holda saqlanadi va hech kimga ko'rsatilmaydi.</p>
      </div>
    </Sheet>
  );
}

// ============================================================
// Bot muharriri
// ============================================================

type EditorTab = "menu" | "webapp" | "broadcast" | "settings";

export function BotEditor({
  botId,
  variables,
  toast,
  onBack,
  standalone = false,
  startTab,
}: {
  botId: number;
  variables: { key: string; label: string }[];
  toast: Toast;
  onBack: () => void;
  standalone?: boolean;
  startTab?: EditorTab;
}) {
  const queryClient = useQueryClient();
  const { data: bot, refetch } = useQuery({
    queryKey: ["bot", botId],
    queryFn: () => api.bot(botId),
    refetchInterval: (q) => (q.state.data?.last_broadcast?.status === "sending" ? 3000 : 30000),
  });
  const [draft, setDraft] = useState<BotMenu | null>(null);
  const [saved, setSaved] = useState<string>("");
  const [tab, setTab] = useState<EditorTab>(startTab ?? "menu");
  const [editing, setEditing] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (bot && draft === null) {
      setDraft(clone(bot.menu));
      setSaved(JSON.stringify(bot.menu));
    }
  }, [bot, draft]);

  const dirty = draft !== null && JSON.stringify(draft) !== saved;

  const back = async () => {
    if (dirty && !(await confirmDialog("O'zgarishlar saqlanmagan. Chiqib ketilsinmi?"))) return;
    onBack();
  };

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      const res = await api.saveBotMenu(botId, draft);
      setDraft(clone(res.menu));
      setSaved(JSON.stringify(res.menu));
      haptic("success");
      toast("Saqlandi — bot darhol yangilandi");
      refetch();
    } catch (e) {
      haptic("error");
      toast((e as Error).message, "err");
    } finally {
      setSaving(false);
    }
  };

  if (!bot || !draft) return <div className="spinner spinner--center" />;

  const update = (fn: (m: BotMenu) => void) =>
    setDraft((prev) => {
      const next = clone(prev!);
      fn(next);
      return next;
    });

  const toggleActive = async () => {
    try {
      await api.setBotActive(botId, bot.status !== "active");
      haptic("select");
      refetch();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  const remove = async () => {
    if (!(await confirmDialog(`@${bot.username} o'chirilsinmi? Menyu va obunachilar ro'yxati o'chadi (bot Telegram'da qoladi).`))) return;
    try {
      await api.deleteBot(botId);
      queryClient.invalidateQueries({ queryKey: ["bots"] });
      toast("Bot o'chirildi");
      onBack();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <div className="stack bb-editor">
      <div className="bb-topbar">
        <button className="icon-btn icon-btn--round" onClick={back} aria-label={standalone ? "Yopish" : "Orqaga"}>
          {standalone ? <X size={18} /> : <ChevronLeft size={18} />}
        </button>
        <div className="bb-topbar__title">
          <b>{bot.name}</b>
          <button className="bb-link" onClick={() => openLink(`https://t.me/${bot.username}`)}>
            @{bot.username} <ExternalLink size={12} />
          </button>
        </div>
        {!standalone && (
          <button className={`switch ${bot.status === "active" ? "is-on" : ""}`} onClick={toggleActive} aria-label="Yoqish">
            <i />
          </button>
        )}
      </div>

      {bot.error_message && (
        <div className="notice notice--warn">
          <CircleAlert size={16} /> {bot.error_message}
        </div>
      )}
      {bot.status === "paused" && <div className="notice">Bot to'xtatilgan — foydalanuvchilarga javob bermaydi.</div>}

      <div className="stats">
        <div className="stat">
          <span className="stat__icon">
            <Users size={16} />
          </span>
          <span className="stat__value">{bot.stats.subscribers}</span>
          <span className="stat__label">obunachi</span>
        </div>
        <div className="stat">
          <span className="stat__value">{bot.stats.active_24h}</span>
          <span className="stat__label">24 soatda faol</span>
        </div>
        <div className="stat">
          <span className="stat__value">+{bot.stats.new_7d}</span>
          <span className="stat__label">7 kunda yangi</span>
        </div>
      </div>

      <div className="segmented">
        <button className={tab === "menu" ? "is-selected" : ""} onClick={() => setTab("menu")}>
          <LayoutGrid size={15} /> Menyu
        </button>
        <button className={tab === "webapp" ? "is-selected" : ""} onClick={() => setTab("webapp")}>
          <Globe size={15} /> Web App
        </button>
        <button className={tab === "broadcast" ? "is-selected" : ""} onClick={() => setTab("broadcast")}>
          <Send size={15} /> Xabar
        </button>
        <button className={tab === "settings" ? "is-selected" : ""} onClick={() => setTab("settings")}>
          <Settings2 size={15} /> Sozlama
        </button>
      </div>

      {tab === "menu" && <PagesList menu={draft} limit={Math.max(bot.pages_limit, draft.pages.length)} update={update} onOpen={setEditing} />}
      {tab === "broadcast" && <BroadcastTab bot={bot} toast={toast} refetch={refetch} />}
      {tab === "settings" && <SettingsTab menu={draft} update={update} onDelete={standalone ? undefined : remove} />}
      {tab === "webapp" && <WebAppPanel botId={botId} toast={toast} autoOpen={startTab === "webapp"} />}

      {editing && draft.pages.some((p) => p.id === editing) && (
        <PageSheet
          menu={draft}
          pageId={editing}
          botName={bot.name}
          variables={variables}
          limit={Math.max(bot.pages_limit, draft.pages.length)}
          update={update}
          onNavigate={setEditing}
          onClose={() => setEditing(null)}
          toast={toast}
        />
      )}

      {dirty && (
        <div className="bb-savebar">
          <button className="btn btn--ghost" disabled={saving} onClick={() => setDraft(JSON.parse(saved))}>
            Bekor qilish
          </button>
          <button className="btn btn--primary" disabled={saving} onClick={save}>
            {saving ? "Saqlanmoqda…" : "Saqlash"}
          </button>
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------
// Sahifalar ro'yxati (menyu tuzilmasi)
// ------------------------------------------------------------

function incoming(menu: BotMenu, pageId: string): BotPage[] {
  return menu.pages.filter((p) => p.buttons.some((row) => row.some((b) => b.action === "page" && b.target === pageId)));
}

function PagesList({
  menu,
  limit,
  update,
  onOpen,
}: {
  menu: BotMenu;
  limit: number;
  update: (fn: (m: BotMenu) => void) => void;
  onOpen: (id: string) => void;
}) {
  // Bosh sahifadan boshlab daraxt ko'rinishida (chuqurlik bilan) — qolganlari («yetib bo'lmaydigan») oxirida.
  const ordered = useMemo(() => {
    const byId = Object.fromEntries(menu.pages.map((p) => [p.id, p]));
    const seen = new Set<string>();
    const out: { page: BotPage; depth: number }[] = [];
    const walk = (id: string, depth: number) => {
      if (seen.has(id) || !byId[id]) return;
      seen.add(id);
      out.push({ page: byId[id], depth });
      for (const row of byId[id].buttons) for (const b of row) if (b.action === "page" && b.target) walk(b.target, depth + 1);
    };
    walk(menu.start, 0);
    const orphans = menu.pages.filter((p) => !seen.has(p.id)).map((page) => ({ page, depth: -1 }));
    return [...out, ...orphans];
  }, [menu]);

  const add = () => {
    const id = newId();
    update((m) => {
      m.pages.push({ id, title: "Yangi sahifa", text: "Matnni yozing…", media_id: null, keyboard: "inline", buttons: [[{ text: "⬅️ Orqaga", action: "back", target: null, url: null }]] });
    });
    onOpen(id);
  };

  return (
    <>
      <div className="bb-section-head">
        <h3 className="section-title">Sahifalar</h3>
        <span className="hint">
          {menu.pages.length}/{limit}
        </span>
      </div>
      <section className="card card--list">
        {ordered.map(({ page, depth }) => {
          const buttons = page.buttons.reduce((n, r) => n + r.length, 0);
          return (
            <button key={page.id} className="list-item bb-page-item" onClick={() => onOpen(page.id)}>
              <span className="bb-indent" style={{ width: Math.max(0, Math.min(depth, 4)) * 14 }} />
              <span className={`bb-page-icon ${page.id === menu.start ? "is-start" : ""}`}>
                {page.id === menu.start ? <Home size={16} /> : page.keyboard === "reply" ? <Keyboard size={16} /> : <FileText size={16} />}
              </span>
              <span className="list-item__body">
                <span className="list-item__title">{page.title}</span>
                <span className="list-item__sub">
                  {depth === -1 ? "⚠️ hech qayerdan ochilmaydi · " : ""}
                  {buttons} tugma{page.media_id ? " · rasm" : ""}
                </span>
              </span>
              <ChevronRight size={18} className="list-item__chev" />
            </button>
          );
        })}
      </section>
      <button className="btn btn--ghost" disabled={menu.pages.length >= limit} onClick={add}>
        <Plus size={18} /> Sahifa qo'shish
      </button>
      {menu.pages.length >= limit && <p className="hint center">Tarif limiti: {limit} ta sahifa.</p>}
    </>
  );
}

// ------------------------------------------------------------
// Sahifa muharriri: jonli ko'rinish + matn + rasm + tugmalar
// ------------------------------------------------------------

function PageSheet({
  menu,
  pageId,
  botName,
  variables,
  limit,
  update,
  onNavigate,
  onClose,
  toast,
}: {
  menu: BotMenu;
  pageId: string;
  botName: string;
  variables: { key: string; label: string }[];
  limit: number;
  update: (fn: (m: BotMenu) => void) => void;
  onNavigate: (id: string) => void;
  onClose: () => void;
  toast: Toast;
}) {
  const page = menu.pages.find((p) => p.id === pageId)!;
  const [selected, setSelected] = useState<[number, number] | null>(null);
  const [history, setHistory] = useState<string[]>([]);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => setSelected(null), [pageId]);

  const edit = (fn: (p: BotPage, m: BotMenu) => void) =>
    update((m) => {
      fn(m.pages.find((p) => p.id === pageId)!, m);
    });

  const go = (id: string) => {
    setHistory((h) => [...h, pageId]);
    onNavigate(id);
  };

  const pressPreview = (b: BotButton) => {
    haptic("select");
    if (b.action === "page" && b.target) go(b.target);
    else if (b.action === "home") go(menu.start);
    else if (b.action === "back") {
      const prev = history[history.length - 1];
      if (prev) {
        setHistory((h) => h.slice(0, -1));
        onNavigate(prev);
      } else toast("Orqaga — foydalanuvchi oldingi sahifasiga qaytadi");
    } else if (b.action === "url" && b.url) openLink(b.url);
    else if (b.action === "feedback") toast("Foydalanuvchi xabar yozadi — u sizga botda keladi, «Reply» qilib javob berasiz");
    else if (b.action === "webapp") toast("Bu tugma botingizning Web App ilovasini ochadi");
  };

  const insertVar = (key: string) => {
    const el = textRef.current;
    const pos = el?.selectionStart ?? page.text.length;
    edit((p) => {
      p.text = p.text.slice(0, pos) + key + p.text.slice(pos);
    });
    setTimeout(() => el?.focus(), 0);
  };

  const upload = async (file: File) => {
    setUploading(true);
    try {
      const { id } = await api.uploadMedia(await fileToJpegBase64(file));
      edit((p) => {
        p.media_id = id;
      });
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setUploading(false);
    }
  };

  const addRow = () =>
    edit((p) => {
      p.buttons.push([{ text: "Yangi tugma", action: "page", target: null, url: null }]);
      setSelected([p.buttons.length - 1, 0]);
    });

  const addToRow = (r: number) =>
    edit((p) => {
      p.buttons[r].push({ text: "Tugma", action: "page", target: null, url: null });
      setSelected([r, p.buttons[r].length - 1]);
    });

  const remove = async () => {
    const refs = incoming(menu, pageId);
    const msg = refs.length
      ? `«${page.title}» o'chirilsinmi? Unga olib boradigan ${refs.length} ta sahifadagi tugmalar ham o'chadi.`
      : `«${page.title}» o'chirilsinmi?`;
    if (!(await confirmDialog(msg))) return;
    update((m) => {
      m.pages = m.pages.filter((p) => p.id !== pageId);
      for (const p of m.pages) p.buttons = p.buttons.map((row) => row.filter((b) => !(b.action === "page" && b.target === pageId))).filter((row) => row.length);
    });
    onClose();
  };

  const limitText = page.media_id ? 1024 : 4096;
  const refs = incoming(menu, pageId);
  const sel = selected && page.buttons[selected[0]]?.[selected[1]] ? selected : null;

  return (
    <Sheet title={page.title} icon={page.id === menu.start ? <Home size={20} /> : <FileText size={20} />} onClose={onClose}>
      <div className="stack">
        <PagePreview menu={menu} page={page} botName={botName} onPress={pressPreview} />
        <p className="hint center">Ko'rinishdagi tugmalarni bosib sahifalar bo'ylab yuring.</p>

        {refs.length > 0 && page.id !== menu.start && (
          <div className="chips">
            <span className="hint">Bu yerga olib keladi:</span>
            {refs.map((r) => (
              <button key={r.id} className="chip-btn" onClick={() => go(r.id)}>
                {r.title}
              </button>
            ))}
          </div>
        )}

        <label className="field">
          <span className="label">Sahifa nomi (faqat sizga ko'rinadi)</span>
          <input className="input" maxLength={64} value={page.title} onChange={(e) => edit((p) => void (p.title = e.target.value))} />
        </label>

        <label className="field">
          <span className="label">
            Xabar matni · {page.text.length}/{limitText}
          </span>
          <textarea
            ref={textRef}
            className="input"
            rows={5}
            maxLength={limitText}
            value={page.text}
            onChange={(e) => edit((p) => void (p.text = e.target.value))}
          />
        </label>
        <div className="chips">
          {variables.map((v) => (
            <button key={v.key} className="chip-btn" onClick={() => insertVar(v.key)} title={v.label}>
              {v.key} <span className="hint">{v.label}</span>
            </button>
          ))}
        </div>

        <span className="label">Rasm</span>
        {page.media_id ? (
          <div className="row">
            <div className="bc-photo">
              <img src={mediaUrl(page.media_id)} alt="" />
            </div>
            <button className="btn btn--ghost btn--compact" onClick={() => edit((p) => void (p.media_id = null))}>
              <X size={16} /> Olib tashlash
            </button>
          </div>
        ) : (
          <button className="btn btn--ghost btn--compact" disabled={uploading} onClick={() => fileRef.current?.click()}>
            <ImagePlus size={16} /> {uploading ? "Yuklanmoqda…" : "Rasm qo'shish"}
          </button>
        )}
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) upload(f);
            e.target.value = "";
          }}
        />

        <span className="label">Tugmalar joylashuvi</span>
        <div className="segmented">
          <button className={page.keyboard === "inline" ? "is-selected" : ""} onClick={() => edit((p) => void (p.keyboard = "inline"))}>
            Xabar ostida
          </button>
          <button
            className={page.keyboard === "reply" ? "is-selected" : ""}
            onClick={() =>
              edit((p) => {
                p.keyboard = "reply";
                // Pastki menyuda havola tugmasi ishlamaydi
                for (const row of p.buttons) for (const b of row) if (b.action === "url") b.action = "page";
              })
            }
          >
            Pastki menyu
          </button>
        </div>
        <p className="hint">
          {page.keyboard === "inline"
            ? "Tugmalar xabar ostida chiqadi, bosilganda xabar o'rnida yangi sahifa ochiladi."
            : "Tugmalar klaviatura o'rnida doim turadi — asosiy menyu uchun qulay."}
        </p>

        <div className="bb-section-head">
          <span className="label">Tugmalar</span>
          <span className="hint">tugmani bosib tahrirlang</span>
        </div>
        <div className="bb-grid">
          {page.buttons.map((row, r) => (
            <div key={r} className="bb-grid__row">
              {row.map((b, c) => (
                <button
                  key={c}
                  className={`bb-key ${sel && sel[0] === r && sel[1] === c ? "is-selected" : ""} ${invalid(b, menu) ? "is-invalid" : ""}`}
                  onClick={() => setSelected([r, c])}
                >
                  <ActionIcon action={b.action} />
                  <span>{b.text}</span>
                </button>
              ))}
              {row.length < MAX_PER_ROW && (
                <button className="bb-key bb-key--add" onClick={() => addToRow(r)} aria-label="Qatorga tugma">
                  <Plus size={16} />
                </button>
              )}
            </div>
          ))}
          {page.buttons.length < MAX_ROWS && (
            <button className="bb-key bb-key--row" onClick={addRow}>
              <Plus size={16} /> Yangi qator
            </button>
          )}
        </div>

        {sel && (
          <ButtonEditor
            key={`${pageId}-${sel[0]}-${sel[1]}`}
            menu={menu}
            page={page}
            pos={sel}
            limit={limit}
            edit={edit}
            onSelect={setSelected}
            onOpenPage={go}
          />
        )}

        <div className="bb-page-actions">
          {page.id !== menu.start && (
            <button className="btn btn--ghost btn--compact" onClick={() => update((m) => void (m.start = pageId))}>
              <Star size={16} /> Bosh sahifa qilish
            </button>
          )}
          {page.id !== menu.start && (
            <button className="btn btn--danger btn--compact" onClick={remove}>
              <Trash2 size={16} /> Sahifani o'chirish
            </button>
          )}
        </div>
      </div>
    </Sheet>
  );
}

function invalid(b: BotButton, menu: BotMenu): boolean {
  if (!b.text.trim()) return true;
  if (b.action === "page") return !b.target || !menu.pages.some((p) => p.id === b.target);
  if (b.action === "url") return !b.url || !/^(https?:\/\/|tg:\/\/)\S+$/.test(b.url);
  return false;
}

function ActionIcon({ action }: { action: BotAction }) {
  const Icon = ACTIONS.find((a) => a.code === action)?.icon ?? FileText;
  return <Icon size={13} className="bb-key__icon" />;
}

function ButtonEditor({
  menu,
  page,
  pos,
  limit,
  edit,
  onSelect,
  onOpenPage,
}: {
  menu: BotMenu;
  page: BotPage;
  pos: [number, number];
  limit: number;
  edit: (fn: (p: BotPage, m: BotMenu) => void) => void;
  onSelect: (pos: [number, number] | null) => void;
  onOpenPage: (id: string) => void;
}) {
  const [r, c] = pos;
  const b = page.buttons[r][c];
  const set = (fn: (b: BotButton) => void) => edit((p) => fn(p.buttons[r][c]));

  const move = (dr: number, dc: number) =>
    edit((p) => {
      if (dc !== 0) {
        const row = p.buttons[r];
        const to = c + dc;
        if (to < 0 || to >= row.length) return;
        [row[c], row[to]] = [row[to], row[c]];
        onSelect([r, to]);
      } else {
        const to = r + dr;
        if (to < 0) return;
        const [btn] = p.buttons[r].splice(c, 1);
        if (to >= p.buttons.length) {
          if (p.buttons.length >= MAX_ROWS && p.buttons[r].length) {
            p.buttons[r].splice(c, 0, btn);
            return;
          }
          p.buttons.push([btn]);
        } else {
          if (p.buttons[to].length >= MAX_PER_ROW) {
            p.buttons[r].splice(c, 0, btn);
            return;
          }
          p.buttons[to].push(btn);
        }
        const target = Math.min(to, p.buttons.length - 1);
        const empty = p.buttons[r].length === 0;
        p.buttons = p.buttons.filter((row) => row.length);
        const newRow = empty && target > r ? target - 1 : target;
        onSelect([newRow, p.buttons[newRow].length - 1]);
      }
    });

  const removeBtn = () => {
    edit((p) => {
      p.buttons[r].splice(c, 1);
      p.buttons = p.buttons.filter((row) => row.length);
    });
    onSelect(null);
  };

  const createPage = () => {
    const id = newId();
    edit((p, m) => {
      m.pages.push({
        id,
        title: b.text.slice(0, 64) || "Yangi sahifa",
        text: b.text || "Matnni yozing…",
        media_id: null,
        keyboard: "inline",
        buttons: [[{ text: "⬅️ Orqaga", action: "back", target: null, url: null }]],
      });
      p.buttons[r][c].target = id;
    });
  };

  const actions = ACTIONS.filter((a) => !(a.code === "url" && page.keyboard === "reply"));
  const others = menu.pages.filter((p) => p.id !== page.id);

  return (
    <div className="card-inset card-inset--pad bb-btn-editor">
      <div className="bb-section-head">
        <b>Tugma</b>
        <div className="row">
          <button className="icon-btn" onClick={() => move(0, -1)} disabled={c === 0} aria-label="Chapga">
            <ArrowLeft size={16} />
          </button>
          <button className="icon-btn" onClick={() => move(0, 1)} disabled={c === page.buttons[r].length - 1} aria-label="O'ngga">
            <ArrowRight size={16} />
          </button>
          <button className="icon-btn" onClick={() => move(-1, 0)} disabled={r === 0} aria-label="Yuqoriga">
            <ArrowUp size={16} />
          </button>
          <button className="icon-btn" onClick={() => move(1, 0)} aria-label="Pastga">
            <ArrowDown size={16} />
          </button>
          <button className="icon-btn" onClick={removeBtn} aria-label="O'chirish">
            <Trash2 size={16} color="var(--danger)" />
          </button>
        </div>
      </div>
      <input className="input" maxLength={64} value={b.text} placeholder="Tugma matni" onChange={(e) => set((x) => void (x.text = e.target.value))} />

      <div className="chips">
        {actions.map((a) => (
          <button
            key={a.code}
            className={`chip-btn ${b.action === a.code ? "is-selected" : ""}`}
            onClick={() =>
              set((x) => {
                x.action = a.code;
                if (a.code !== "page") x.target = null;
                if (a.code !== "url") x.url = null;
              })
            }
          >
            <a.icon size={14} /> {a.title}
          </button>
        ))}
      </div>

      {b.action === "page" && (
        <>
          <select className="input" value={b.target ?? ""} onChange={(e) => set((x) => void (x.target = e.target.value || null))}>
            <option value="">— sahifani tanlang —</option>
            {others.map((p) => (
              <option key={p.id} value={p.id}>
                {p.id === menu.start ? "🏠 " : ""}
                {p.title}
              </option>
            ))}
          </select>
          <div className="row">
            <button className="btn btn--ghost btn--compact" disabled={menu.pages.length >= limit} onClick={createPage}>
              <Plus size={16} /> Yangi sahifa
            </button>
            {b.target && (
              <button className="btn btn--ghost btn--compact" onClick={() => onOpenPage(b.target!)}>
                Ochish <ChevronRight size={16} />
              </button>
            )}
          </div>
        </>
      )}
      {b.action === "url" && (
        <input
          className="input"
          inputMode="url"
          placeholder="https://..."
          value={b.url ?? ""}
          onChange={(e) => set((x) => void (x.url = e.target.value.trim() || null))}
        />
      )}
      {b.action === "feedback" && <p className="hint">Foydalanuvchi keyingi xabarini sizga yuboradi (buyurtma, savol, ariza).</p>}
      {b.action === "back" && <p className="hint">Foydalanuvchi oldingi sahifasiga qaytadi.</p>}
      {b.action === "home" && <p className="hint">Bosh sahifani ochadi.</p>}
      {b.action === "webapp" && (
        <p className="hint">Botingizning Web App ilovasini ochadi. Ilova «Web App» bo'limida e'lon qilinmaguncha tugma ko'rinmaydi.</p>
      )}
    </div>
  );
}

function PagePreview({ menu, page, botName, onPress }: { menu: BotMenu; page: BotPage; botName: string; onPress: (b: BotButton) => void }) {
  const userName = tg?.initDataUnsafe.user?.first_name ?? "Ali";
  const username = tg?.initDataUnsafe.user?.username;
  const text = page.text
    .split("{name}")
    .join(userName)
    .split("{username}")
    .join(username ? `@${username}` : userName)
    .split("{bot}")
    .join(botName);
  // Pastki menyu: shu sahifada bo'lmasa — oxirgi ochilgan reply-menyu (odatda bosh sahifa) ko'rinib turadi.
  const replyPage = page.keyboard === "reply" ? page : menu.pages.find((p) => p.id === menu.start && p.keyboard === "reply");
  return (
    <div className="bb-chat">
      <div className="bb-chat__msgs">
        <div className="bc-preview">
          {page.media_id && <img src={mediaUrl(page.media_id)} alt="" />}
          <div className="bc-preview__text">{text}</div>
        </div>
        {page.keyboard === "inline" &&
          page.buttons.map((row, r) => (
            <div key={r} className="bb-inline">
              {row.map((b, c) => (
                <button key={c} className="bb-inline__btn" onClick={() => onPress(b)}>
                  {b.text}
                  {b.action === "url" && <ExternalLink size={11} />}
                </button>
              ))}
            </div>
          ))}
      </div>
      {replyPage && replyPage.buttons.length > 0 && (
        <div className="bb-reply">
          {replyPage.buttons.map((row, r) => (
            <div key={r} className="bb-reply__row">
              {row.map((b, c) => (
                <button key={c} className="bb-reply__btn" onClick={() => onPress(b)}>
                  {b.text}
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------
// Ommaviy xabar
// ------------------------------------------------------------

function BroadcastTab({ bot, toast, refetch }: { bot: BotDetail; toast: Toast; refetch: () => void }) {
  const [text, setText] = useState("");
  const [mediaId, setMediaId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const last = bot.last_broadcast;
  const sending = last?.status === "sending";

  const send = async () => {
    if (!(await confirmDialog(`Xabar ${bot.stats.subscribers} ta obunachiga yuborilsinmi?`))) return;
    setBusy(true);
    try {
      await api.botBroadcast(bot.id, text.trim(), mediaId);
      haptic("success");
      toast("Yuborish boshlandi");
      setText("");
      setMediaId(null);
      refetch();
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      {last && (
        <section className="card">
          <b>{sending ? "Yuborilmoqda…" : "Oxirgi xabar yuborildi"}</b>
          <div className="meter">
            <i style={{ width: `${last.total ? ((last.sent + last.failed) / last.total) * 100 : 100}%` }} />
          </div>
          <p className="hint">
            {last.sent} ta yetkazildi · {last.failed} ta yetmadi · jami {last.total}
          </p>
        </section>
      )}
      <section className="card stack">
        <span className="label">Obunachilarga xabar · {bot.stats.subscribers} kishi</span>
        <textarea
          className="input"
          rows={5}
          maxLength={mediaId ? 1024 : 4096}
          placeholder="Yangilik, aksiya yoki e'lon…"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        {mediaId ? (
          <div className="row">
            <div className="bc-photo">
              <img src={mediaUrl(mediaId)} alt="" />
            </div>
            <button className="btn btn--ghost btn--compact" onClick={() => setMediaId(null)}>
              <X size={16} /> Olib tashlash
            </button>
          </div>
        ) : (
          <button className="btn btn--ghost btn--compact" onClick={() => fileRef.current?.click()}>
            <ImagePlus size={16} /> Rasm qo'shish
          </button>
        )}
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          hidden
          onChange={async (e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            if (!f) return;
            try {
              setMediaId((await api.uploadMedia(await fileToJpegBase64(f))).id);
            } catch (err) {
              toast((err as Error).message, "err");
            }
          }}
        />
        <button className="btn btn--primary" disabled={busy || sending || !text.trim() || bot.status !== "active"} onClick={send}>
          <Send size={17} /> Yuborish
        </button>
        {bot.status !== "active" && <p className="hint">Xabar yuborish uchun botni yoqing.</p>}
      </section>
    </div>
  );
}

// ------------------------------------------------------------
// Sozlamalar
// ------------------------------------------------------------

function SettingsTab({ menu, update, onDelete }: { menu: BotMenu; update: (fn: (m: BotMenu) => void) => void; onDelete?: () => void }) {
  const field = (key: "fallback" | "feedback_prompt" | "feedback_done", label: string, hint: string) => (
    <label className="field">
      <span className="label">{label}</span>
      <textarea className="input" rows={2} maxLength={1000} value={menu[key]} onChange={(e) => update((m) => void (m[key] = e.target.value))} />
      <span className="field__hint hint">{hint}</span>
    </label>
  );
  return (
    <div className="stack">
      <section className="card stack">
        <button className="toggle-row" onClick={() => update((m) => void (m.forward_all = !m.forward_all))}>
          <span className="toggle-row__body toggle-row__body--col">
            <b>Murojaatlar rejimi</b>
            <span className="hint">Menyuda yo'q har qanday xabar (matn, rasm, ovoz) sizga keladi — qayta aloqa boti uchun</span>
          </span>
          <span className={`switch ${menu.forward_all ? "is-on" : ""}`}>
            <i />
          </span>
        </button>
        {field("feedback_prompt", "«Adminga yozish» bosilganda", "Foydalanuvchidan nima yozishini so'rang (buyurtma, telefon…).")}
        {field("feedback_done", "Xabar yetkazilgach", "Foydalanuvchiga tasdiq.")}
        <button className="toggle-row" onClick={() => update((m) => void (m.feedback_anonymous = !m.feedback_anonymous))}>
          <span className="toggle-row__body toggle-row__body--col">
            <b>Anonim xabarlar</b>
            <span className="hint">Kim yozgani sizga ko'rsatilmaydi (anonim savollar boti uchun)</span>
          </span>
          <span className={`switch ${menu.feedback_anonymous ? "is-on" : ""}`}>
            <i />
          </span>
        </button>
        {field("fallback", "Tushunarsiz xabarga javob", "Foydalanuvchi menyuda yo'q narsa yozsa.")}
      </section>
      <section className="card">
        <p className="hint">
          Xabar va buyurtmalar sizga <b>o'z botingiz</b> orqali keladi — unga bir marta /start bosing. Javob berish uchun kelgan
          xabarga «Reply» qiling.
        </p>
      </section>
      {onDelete && (
        <button className="btn btn--danger" onClick={onDelete}>
          <Trash2 size={17} /> Botni o'chirish
        </button>
      )}
    </div>
  );
}

// Foydalanuvchining o'z botidan ochilgan muharrir (/admin → «Menyu va tugmalar»): faqat shu bot, tabbarsiz.
export function StandaloneBotEditor({ botId, toast, startTab }: { botId: number; toast: Toast; startTab?: "webapp" }) {
  const { data } = useQuery({ queryKey: ["bots"], queryFn: api.bots });
  return (
    <BotEditor
      botId={botId}
      variables={data?.variables ?? []}
      toast={toast}
      standalone
      startTab={startTab}
      onBack={() => (tg ? tg.close() : window.history.back())}
    />
  );
}
