// Kodsiz Web App konstruktori: sahifalar, bloklar, uslub, sozlamalar, arizalar va jonli ko'rinish.
import { useQuery } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Copy,
  ExternalLink,
  Eye,
  EyeOff,
  Globe,
  Inbox,
  LayoutTemplate,
  Monitor,
  MousePointerClick,
  Paintbrush,
  Plus,
  Rocket,
  Settings2,
  Smartphone,
  Star,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, mediaUrl, type WASubmission, type WebAppInfo, type WebAppState } from "../api";
import { confirmDialog, haptic, tg } from "../tg";
import { WebAppRuntime } from "../webapp/Runtime";
import { BLOCK_SPECS, CATEGORIES, FORM_FIELD_SPEC, cloneBlock, newBlock, newField } from "../webapp/specs";
import { formatMoney, uid, type AppDoc, type BlockType, type WABlock, type WAPage } from "../webapp/types";
import { Inspector, Sheet } from "./Sheet";
import { useEscape, useSaveShortcut } from "../hooks";
import { DESKTOP_QUERY, isMac, useMediaQuery } from "../util";
import { SpecForm } from "./SpecForm";

type Toast = (text: string, kind?: "ok" | "err") => void;

function clone<T>(v: T): T {
  return JSON.parse(JSON.stringify(v));
}

function openLink(url: string) {
  if (tg?.openLink) tg.openLink(url);
  else window.open(url, "_blank");
}

const previewSubmit = async () => {
  await new Promise((r) => setTimeout(r, 300));
  return { message: "✅ (Sinov rejimi) Haqiqiy ilovada bu ma'lumot sizga botda keladi." };
};

// ============================================================
// Bot muharriridagi «Web App» bo'limi
// ============================================================

export function WebAppPanel({ botId, toast, autoOpen = false }: { botId: number; toast: Toast; autoOpen?: boolean }) {
  const { data, refetch } = useQuery({ queryKey: ["webapp", botId], queryFn: () => api.webApp(botId) });
  const [open, setOpen] = useState(autoOpen);
  const [creating, setCreating] = useState(false);

  if (!data) return <div className="spinner spinner--center" />;

  const create = async (template: string) => {
    setCreating(true);
    try {
      await api.createWebApp(botId, template);
      await refetch();
      haptic("success");
      setOpen(true);
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setCreating(false);
    }
  };

  if (!data.app)
    return (
      <div className="stack">
        <section className="card wb-intro">
          <span className="bb-hero__icon">
            <Globe size={28} />
          </span>
          <h2>Web App yarating</h2>
          <p className="hint">
            Botingiz ichida ochiladigan to'liq ilova — do'kon, menyu, yozilish formasi, portfolio. Kod yozmasdan: bloklarni qo'shasiz,
            uslubni tanlaysiz, «E'lon qilish» bosasiz.
          </p>
        </section>
        <span className="label">Shablonni tanlang</span>
        <TemplateGrid templates={data.templates} busy={creating} onPick={create} />
      </div>
    );

  const app = data.app;
  return (
    <div className="stack">
      <section className="card stack">
        <div className="wb-status">
          <span className={`wb-dot ${app.published ? "is-live" : ""}`} />
          <b>{app.published ? "E'lon qilingan" : "Qoralama"}</b>
          {app.published && app.has_changes && <span className="tag">e'lon qilinmagan o'zgarishlar bor</span>}
        </div>
        <p className="hint">
          {app.draft.pages.length} sahifa · {app.draft.pages.reduce((n, p) => n + p.blocks.length, 0)} blok
          {app.published && app.menu_button ? ` · menyu tugmasi: «${app.menu_button_text}»` : ""}
        </p>
        <button className="btn btn--primary" onClick={() => setOpen(true)}>
          <LayoutTemplate size={18} /> Konstruktorni ochish
        </button>
        {app.published && app.url && (
          <button className="btn btn--ghost" onClick={() => openLink(`https://t.me/${data.bot_username}`)}>
            <ExternalLink size={17} /> Botda ochib ko'rish
          </button>
        )}
      </section>
      {open && (
        <WebAppBuilder
          botId={botId}
          state={data}
          toast={toast}
          onClose={() => {
            setOpen(false);
            refetch();
          }}
        />
      )}
    </div>
  );
}

function TemplateGrid({ templates, busy, onPick }: { templates: WebAppState["templates"]; busy: boolean; onPick: (code: string) => void }) {
  return (
    <div className="bb-templates">
      {templates.map((t) => (
        <button key={t.code} className="bb-template" disabled={busy} onClick={() => onPick(t.code)}>
          <span className="bb-template__icon">{t.icon}</span>
          <b>{t.title}</b>
          <span className="hint">{t.desc}</span>
        </button>
      ))}
    </div>
  );
}

// ============================================================
// Konstruktor (to'liq ekran)
// ============================================================

type Tab = "pages" | "style" | "settings" | "inbox";

export function WebAppBuilder({ botId, state, toast, onClose }: { botId: number; state: WebAppState; toast: Toast; onClose: () => void }) {
  const [info, setInfo] = useState<WebAppInfo>(state.app!);
  const [doc, setDoc] = useState<AppDoc>(() => clone(state.app!.draft));
  const [saved, setSaved] = useState(() => JSON.stringify(state.app!.draft));
  const [tab, setTab] = useState<Tab>("pages");
  const [pageId, setPageId] = useState(doc.start);
  const [editing, setEditing] = useState<string | null>(null);
  const [palette, setPalette] = useState(false);
  const [preview, setPreview] = useState(false);
  const [busy, setBusy] = useState(false);
  const desktop = useMediaQuery(DESKTOP_QUERY);
  const [device, setDevice] = useState<"phone" | "wide">("phone");

  const dirty = JSON.stringify(doc) !== saved;
  const page = doc.pages.find((p) => p.id === pageId) ?? doc.pages[0];

  useEffect(() => {
    if (!doc.pages.some((p) => p.id === pageId)) setPageId(doc.start);
  }, [doc, pageId]);

  // Studiyaning pastki tabbar'i ko'rinmasin
  useEffect(() => {
    document.body.classList.add("wb-open");
    return () => document.body.classList.remove("wb-open");
  }, []);

  const update = (fn: (d: AppDoc) => void) =>
    setDoc((prev) => {
      const next = clone(prev);
      fn(next);
      return next;
    });
  const updatePage = (fn: (p: WAPage, d: AppDoc) => void) => update((d) => fn(d.pages.find((p) => p.id === page.id)!, d));

  const save = async (): Promise<boolean> => {
    setBusy(true);
    try {
      const res = await api.saveWebAppDraft(botId, doc);
      setInfo(res);
      setDoc(clone(res.draft));
      setSaved(JSON.stringify(res.draft));
      return true;
    } catch (e) {
      haptic("error");
      toast((e as Error).message, "err");
      return false;
    } finally {
      setBusy(false);
    }
  };

  const publish = async () => {
    if (dirty && !(await save())) return;
    setBusy(true);
    try {
      const res = await api.publishWebApp(botId);
      setInfo(res);
      haptic("success");
      toast("E'lon qilindi — ilova botda yangilandi");
    } catch (e) {
      haptic("error");
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  useSaveShortcut(() => {
    if (dirty && !busy) save();
  }, dirty);
  useEscape(editing ? () => setEditing(null) : palette ? () => setPalette(false) : preview ? () => setPreview(false) : null);

  const close = async () => {
    if (dirty && !(await confirmDialog("Saqlanmagan o'zgarishlar bor. Chiqilsinmi?"))) return;
    onClose();
  };

  const addBlock = (type: BlockType) => {
    if (page.blocks.length >= state.limits.blocks) {
      toast(`Bitta sahifada ko'pi bilan ${state.limits.blocks} ta blok`, "err");
      return;
    }
    const block = newBlock(type);
    updatePage((p) => p.blocks.push(block));
    setPalette(false);
    setEditing(block.id);
  };

  const editingBlock = page.blocks.find((b) => b.id === editing) ?? null;
  const ctx = { pages: doc.pages, toast };
  const status = !info.published ? "Qoralama" : dirty || info.has_changes ? "O'zgarishlar e'lon qilinmagan" : "E'lon qilingan";

  const tabs = (
    <div className="segmented">
      <button className={tab === "pages" ? "is-selected" : ""} onClick={() => setTab("pages")}>
        <LayoutTemplate size={15} /> Sahifa
      </button>
      <button className={tab === "style" ? "is-selected" : ""} onClick={() => setTab("style")}>
        <Paintbrush size={15} /> Uslub
      </button>
      <button className={tab === "settings" ? "is-selected" : ""} onClick={() => setTab("settings")}>
        <Settings2 size={15} /> Sozlama
      </button>
      <button className={tab === "inbox" ? "is-selected" : ""} onClick={() => setTab("inbox")}>
        <Inbox size={15} /> Arizalar
      </button>
    </div>
  );

  const tabContent = (
    <>
      {tab === "pages" && (
        <PagesTab
          doc={doc}
          page={page}
          setPageId={setPageId}
          update={update}
          updatePage={updatePage}
          onEdit={setEditing}
          onAdd={() => setPalette(true)}
          maxPages={state.limits.pages}
          botUsername={state.bot_username}
          livePreview={!desktop}
          selected={editing}
        />
      )}
      {tab === "style" && <StyleTab doc={doc} update={update} themes={state.themes} botUsername={state.bot_username} showPreview={!desktop} />}
      {tab === "settings" && (
        <SettingsTab
          botId={botId}
          doc={doc}
          update={update}
          info={info}
          setInfo={setInfo}
          templates={state.templates}
          toast={toast}
          onReplaced={(next) => {
            setInfo(next);
            setDoc(clone(next.draft));
            setSaved(JSON.stringify(next.draft));
            setPageId(next.draft.start);
          }}
          ctx={ctx}
        />
      )}
      {tab === "inbox" && <InboxTab botId={botId} currency={doc.settings.currency} />}
    </>
  );

  const blockEditor = editingBlock && (
    <BlockSheet
      inline={desktop}
      doc={doc}
      block={editingBlock}
      index={page.blocks.findIndex((b) => b.id === editingBlock.id)}
      count={page.blocks.length}
      botUsername={state.bot_username}
      ctx={ctx}
      onChange={(next) => updatePage((p) => (p.blocks = p.blocks.map((b) => (b.id === next.id ? next : b))))}
      onMove={(d) =>
        updatePage((p) => {
          const i = p.blocks.findIndex((b) => b.id === editingBlock.id);
          const j = i + d;
          if (j < 0 || j >= p.blocks.length) return;
          [p.blocks[i], p.blocks[j]] = [p.blocks[j], p.blocks[i]];
        })
      }
      onDuplicate={() => {
        const copy = cloneBlock(editingBlock);
        updatePage((p) => p.blocks.splice(p.blocks.findIndex((b) => b.id === editingBlock.id) + 1, 0, copy));
        setEditing(copy.id);
      }}
      onDelete={async () => {
        if (!(await confirmDialog(`«${BLOCK_SPECS[editingBlock.type].title}» bloki o'chirilsinmi?`))) return;
        updatePage((p) => (p.blocks = p.blocks.filter((b) => b.id !== editingBlock.id)));
        setEditing(null);
      }}
      onClose={() => setEditing(null)}
    />
  );

  return (
    <div className={`wb ${desktop ? "wb--desktop" : ""}`}>
      <header className="wb-bar">
        <button className="icon-btn icon-btn--round" onClick={close} aria-label="Yopish">
          <X size={18} />
        </button>
        <div className="wb-bar__title">
          <b>{desktop ? `Web App · ${doc.settings.title || state.bot_username}` : "Web App"}</b>
          <span className={`wb-bar__status ${info.published && !dirty && !info.has_changes ? "is-live" : ""}`}>{status}</span>
        </div>
        {!desktop && (
          <button className="icon-btn icon-btn--soft" onClick={() => setPreview(true)} aria-label="Ko'rish">
            <Eye size={19} />
          </button>
        )}
        {desktop && info.published && (
          <button className="btn btn--ghost btn--compact btn--inline" onClick={() => openLink(`https://t.me/${state.bot_username}`)}>
            <ExternalLink size={16} /> Botda ochish
          </button>
        )}
        {dirty && (
          <button className="btn btn--ghost btn--compact btn--inline" disabled={busy} onClick={save}>
            Saqlash {desktop && <span className="kbd">{isMac ? "⌘S" : "Ctrl+S"}</span>}
          </button>
        )}
        <button className="btn btn--primary btn--compact btn--inline" disabled={busy || (info.published && !dirty && !info.has_changes)} onClick={publish}>
          <Rocket size={16} /> {desktop ? "E'lon qilish" : "E'lon"}
        </button>
      </header>

      {desktop ? (
        <div className="wb-desk">
          <aside className="wb-left">
            {tabs}
            {tabContent}
          </aside>
          <main className="wb-stage">
            <div className="wb-stage__bar">
              <div className="segmented segmented--small">
                <button className={device === "phone" ? "is-selected" : ""} onClick={() => setDevice("phone")}>
                  <Smartphone size={14} /> Telefon
                </button>
                <button className={device === "wide" ? "is-selected" : ""} onClick={() => setDevice("wide")}>
                  <Monitor size={14} /> Keng oyna
                </button>
              </div>
              <span className="hint">
                {page.emoji} {page.title} · sinov rejimi
              </span>
            </div>
            <div className={`wb-stage__frame ${device === "wide" ? "is-wide" : ""}`}>
              <WebAppRuntime
                doc={doc}
                appId={`stage-${botId}`}
                mode="preview"
                mediaSrc={mediaUrl}
                botUsername={state.bot_username}
                branding={null}
                page={page.id}
                onPageChange={setPageId}
                onSubmit={previewSubmit}
                selectedBlock={editing}
                onSelectBlock={(id) => {
                  setPalette(false);
                  setTab("pages");
                  setEditing(id);
                }}
              />
            </div>
          </main>
          <aside className="wb-right">
            {blockEditor ? (
              blockEditor
            ) : palette ? (
              <div className="stack">
                <div className="bb-inspector__head">
                  <Plus size={20} />
                  <h2>Blok qo'shish</h2>
                  <button className="icon-btn icon-btn--round" onClick={() => setPalette(false)} aria-label="Yopish">
                    <X size={18} />
                  </button>
                </div>
                <Palette onAdd={addBlock} compact />
              </div>
            ) : (
              <div className="wb-right__empty">
                <MousePointerClick size={30} />
                <b>Sozlash paneli</b>
                <span className="hint">Blokni chapdagi ro'yxatdan yoki markazdagi ko'rinishda ✎ belgisi orqali tanlang.</span>
                <button className="btn btn--primary btn--compact" onClick={() => setPalette(true)}>
                  <Plus size={16} /> Blok qo'shish
                </button>
                <div className="wb-shortcuts">
                  <span>
                    <span className="kbd">{isMac ? "⌘S" : "Ctrl+S"}</span> saqlash
                  </span>
                  <span>
                    <span className="kbd">Esc</span> panelni yopish
                  </span>
                </div>
              </div>
            )}
          </aside>
        </div>
      ) : (
        <div className="wb-body">
          {tabs}
          {tabContent}
        </div>
      )}

      {!desktop && palette && (
        <Sheet title="Blok qo'shish" icon={<Plus size={20} />} onClose={() => setPalette(false)}>
          <Palette onAdd={addBlock} />
        </Sheet>
      )}

      {!desktop && blockEditor}

      {preview && !desktop && (
        <div className="wb-preview">
          <div className="wb-preview__bar">
            <span>Ko'rinish · sinov rejimi</span>
            <button className="icon-btn icon-btn--round" onClick={() => setPreview(false)} aria-label="Yopish">
              <X size={18} />
            </button>
          </div>
          <div className="wb-preview__frame">
            <WebAppRuntime
              doc={doc}
              appId={`preview-${botId}`}
              mode="preview"
              mediaSrc={mediaUrl}
              botUsername={state.bot_username}
              branding={null}
              page={pageId}
              onSubmit={previewSubmit}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function Palette({ onAdd, compact = false }: { onAdd: (t: BlockType) => void; compact?: boolean }) {
  return (
    <div className="stack">
      {CATEGORIES.map((cat) => (
        <div key={cat} className="stack wb-palette">
          <span className="label">{cat}</span>
          <div className={`wb-palette__grid ${compact ? "wb-palette__grid--compact" : ""}`}>
            {(Object.keys(BLOCK_SPECS) as BlockType[])
              .filter((t) => BLOCK_SPECS[t].category === cat)
              .map((t) => (
                <button key={t} className="wb-palette__item" onClick={() => onAdd(t)}>
                  <span className="wb-palette__icon">{BLOCK_SPECS[t].icon}</span>
                  <b>{BLOCK_SPECS[t].title}</b>
                  <span className="hint">{BLOCK_SPECS[t].desc}</span>
                </button>
              ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ------------------------------------------------------------
// Sahifalar
// ------------------------------------------------------------

function PagesTab({
  doc,
  page,
  setPageId,
  update,
  updatePage,
  onEdit,
  onAdd,
  maxPages,
  botUsername,
  livePreview,
  selected,
}: {
  doc: AppDoc;
  page: WAPage;
  setPageId: (id: string) => void;
  update: (fn: (d: AppDoc) => void) => void;
  updatePage: (fn: (p: WAPage, d: AppDoc) => void) => void;
  onEdit: (id: string) => void;
  onAdd: () => void;
  maxPages: number;
  botUsername: string;
  livePreview: boolean;
  selected: string | null;
}) {
  const [showPreview, setShowPreview] = useState(true);
  const [showSettings, setShowSettings] = useState(false);

  const addPage = () => {
    const id = uid("pg");
    update((d) => d.pages.push({ id, title: "Yangi sahifa", emoji: "📄", in_nav: true, blocks: [] }));
    setPageId(id);
    setShowSettings(true);
  };

  const deletePage = async () => {
    if (!(await confirmDialog(`«${page.title}» sahifasi o'chirilsinmi? Unga olib boradigan tugmalar «hech narsa qilmaydi» holatiga o'tadi.`))) return;
    const removed = page.id;
    update((d) => {
      d.pages = d.pages.filter((p) => p.id !== removed);
      const fix = (a: { type: string; page?: string | null } | undefined) => {
        if (a && a.type === "page" && a.page === removed) {
          a.type = "none";
          a.page = null;
        }
      };
      for (const p of d.pages)
        for (const b of p.blocks as any[]) {
          fix(b.action);
          fix(b.button?.action);
          for (const it of b.items ?? []) {
            fix(it.action);
            fix(it.button?.action);
          }
        }
    });
    setPageId(doc.start);
  };

  const movePage = (delta: number) =>
    update((d) => {
      const i = d.pages.findIndex((p) => p.id === page.id);
      const j = i + delta;
      if (j < 0 || j >= d.pages.length) return;
      [d.pages[i], d.pages[j]] = [d.pages[j], d.pages[i]];
    });

  return (
    <div className="stack">
      <div className="chips chips--scroll wb-pages">
        {doc.pages.map((p) => (
          <button key={p.id} className={`chip-btn ${p.id === page.id ? "is-selected" : ""}`} onClick={() => setPageId(p.id)}>
            {p.id === doc.start && <Star size={12} />} {p.emoji} {p.title}
          </button>
        ))}
        {doc.pages.length < maxPages && (
          <button className="chip-btn" onClick={addPage}>
            <Plus size={14} /> Sahifa
          </button>
        )}
      </div>

      {livePreview && <section className="card card--flush">
        <button className="wb-collapse" onClick={() => setShowPreview(!showPreview)}>
          <Eye size={16} /> Jonli ko'rinish
          <span className="hint">{showPreview ? "yashirish" : "ko'rsatish"}</span>
        </button>
        {showPreview && (
          <div className="wb-frame">
            <WebAppRuntime
              doc={doc}
              appId="inline-preview"
              mode="preview"
              mediaSrc={mediaUrl}
              botUsername={botUsername}
              branding={null}
              page={page.id}
              onPageChange={setPageId}
              onSubmit={previewSubmit}
            />
          </div>
        )}
      </section>}

      <section className="card card--flush">
        <button className="wb-collapse" onClick={() => setShowSettings(!showSettings)}>
          <Settings2 size={16} /> Sahifa sozlamalari
          <span className="hint">{showSettings ? "yashirish" : "ochish"}</span>
        </button>
        {showSettings && (
          <div className="wb-page-settings">
            <div className="row">
              <input className="input sf-emoji" maxLength={8} value={page.emoji} onChange={(e) => updatePage((p) => void (p.emoji = e.target.value))} />
              <input className="input" maxLength={40} value={page.title} onChange={(e) => updatePage((p) => void (p.title = e.target.value))} />
            </div>
            <button className="sf-toggle" onClick={() => updatePage((p) => void (p.in_nav = !p.in_nav))}>
              <span>
                Pastki menyuda ko'rsatish
                <span className="sf-hint">2 va undan ko'p sahifa belgilansa, pastda menyu paydo bo'ladi</span>
              </span>
              <span className={`switch ${page.in_nav ? "is-on" : ""}`}>
                <i />
              </span>
            </button>
            <div className="wb-row-actions">
              <button className="btn btn--ghost btn--compact" onClick={() => movePage(-1)} aria-label="Chapga">
                <ArrowLeft size={16} />
              </button>
              <button className="btn btn--ghost btn--compact" onClick={() => movePage(1)} aria-label="O'ngga">
                <ArrowRight size={16} />
              </button>
              {page.id !== doc.start && (
                <button className="btn btn--ghost btn--compact" onClick={() => update((d) => void (d.start = page.id))}>
                  <Star size={16} /> Bosh sahifa
                </button>
              )}
              {page.id !== doc.start && (
                <button className="btn btn--danger btn--compact" onClick={deletePage}>
                  <Trash2 size={16} />
                </button>
              )}
            </div>
          </div>
        )}
      </section>

      <div className="bb-section-head">
        <h3 className="section-title">Bloklar</h3>
        <span className="hint">{page.blocks.length} ta</span>
      </div>
      {page.blocks.length === 0 ? (
        <p className="hint center">Sahifa bo'sh — birinchi blokni qo'shing.</p>
      ) : (
        <section className="card card--list">
          {page.blocks.map((b, i) => (
            <div key={b.id} className={`wb-block ${b.hidden ? "is-hidden" : ""} ${selected === b.id ? "is-selected" : ""}`}>
              <button className="wb-block__main" onClick={() => onEdit(b.id)}>
                <span className="wb-block__icon">{BLOCK_SPECS[b.type].icon}</span>
                <span className="list-item__body">
                  <span className="list-item__title">{BLOCK_SPECS[b.type].title}</span>
                  <span className="list-item__sub">{BLOCK_SPECS[b.type].summary(b) || "—"}</span>
                </span>
              </button>
              {b.hidden && <EyeOff size={15} className="wb-block__hidden" />}
              <button
                className="icon-btn"
                disabled={i === 0}
                aria-label="Yuqoriga"
                onClick={() => updatePage((p) => ([p.blocks[i - 1], p.blocks[i]] = [p.blocks[i], p.blocks[i - 1]]))}
              >
                <ArrowUp size={16} />
              </button>
              <button
                className="icon-btn"
                disabled={i === page.blocks.length - 1}
                aria-label="Pastga"
                onClick={() => updatePage((p) => ([p.blocks[i + 1], p.blocks[i]] = [p.blocks[i], p.blocks[i + 1]]))}
              >
                <ArrowDown size={16} />
              </button>
            </div>
          ))}
        </section>
      )}
      <button className="btn btn--primary wb-sticky-action" onClick={onAdd}>
        <Plus size={18} /> Blok qo'shish
      </button>
    </div>
  );
}

function BlockSheet({
  inline = false,
  doc,
  block,
  index,
  count,
  botUsername,
  ctx,
  onChange,
  onMove,
  onDuplicate,
  onDelete,
  onClose,
}: {
  inline?: boolean;
  doc: AppDoc;
  block: WABlock;
  index: number;
  count: number;
  botUsername: string;
  ctx: { pages: WAPage[]; toast: Toast };
  onChange: (b: WABlock) => void;
  onMove: (d: number) => void;
  onDuplicate: () => void;
  onDelete: () => void;
  onClose: () => void;
}) {
  const spec = BLOCK_SPECS[block.type];
  // Faqat shu blokdan iborat sahifa — blok qanday chiqishini darhol ko'rsatadi
  const single = useMemo<AppDoc>(
    () => ({ ...doc, start: "single", pages: [{ id: "single", title: "", emoji: "", in_nav: false, blocks: [{ ...block, hidden: false }] }] }),
    [doc, block],
  );
  return (
    <Inspector inline={inline} title={spec.title} icon={<span className="wb-sheet-icon">{spec.icon}</span>} onClose={onClose}>
      <div className="stack">
        {!inline && (
          <div className="wb-frame wb-frame--block">
            <WebAppRuntime doc={single} appId="block-preview" mode="preview" mediaSrc={mediaUrl} botUsername={botUsername} branding={null} onSubmit={previewSubmit} />
          </div>
        )}
        <SpecForm spec={spec.fields} value={block} onChange={(next) => onChange(next as WABlock)} ctx={ctx} />
        <button className="sf-toggle" onClick={() => onChange({ ...block, hidden: !block.hidden } as WABlock)}>
          <span>
            Yashirish
            <span className="sf-hint">Blok saqlanadi, lekin foydalanuvchilarga ko'rinmaydi</span>
          </span>
          <span className={`switch ${block.hidden ? "is-on" : ""}`}>
            <i />
          </span>
        </button>
        <div className="wb-row-actions">
          <button className="btn btn--ghost btn--compact" disabled={index === 0} onClick={() => onMove(-1)} aria-label="Yuqoriga">
            <ArrowUp size={16} />
          </button>
          <button className="btn btn--ghost btn--compact" disabled={index === count - 1} onClick={() => onMove(1)} aria-label="Pastga">
            <ArrowDown size={16} />
          </button>
          <button className="btn btn--ghost btn--compact" onClick={onDuplicate}>
            <Copy size={16} /> Nusxa
          </button>
          <button className="btn btn--danger btn--compact" onClick={onDelete}>
            <Trash2 size={16} /> O'chirish
          </button>
        </div>
        {!inline && (
          <button className="btn btn--primary" onClick={onClose}>
            Tayyor
          </button>
        )}
      </div>
    </Inspector>
  );
}

// ------------------------------------------------------------
// Uslub
// ------------------------------------------------------------

const FONTS: [AppDoc["theme"]["font"], string][] = [
  ["system", "Oddiy"],
  ["rounded", "Yumaloq"],
  ["serif", "Klassik"],
  ["mono", "Texnik"],
];

function StyleTab({
  doc,
  update,
  themes,
  botUsername,
  showPreview,
}: {
  doc: AppDoc;
  update: (fn: (d: AppDoc) => void) => void;
  themes: WebAppState["themes"];
  botUsername: string;
  showPreview: boolean;
}) {
  const t = doc.theme;
  const setTheme = (patch: Partial<AppDoc["theme"]>) => update((d) => void (d.theme = { ...d.theme, ...patch }));
  const color = (key: "primary" | "background" | "surface" | "text", label: string) => (
    <label className="wb-color">
      <input type="color" value={t[key]} onChange={(e) => setTheme({ [key]: e.target.value, preset: "custom" })} />
      <span>
        <b>{label}</b>
        <span className="hint">{t[key]}</span>
      </span>
    </label>
  );
  return (
    <div className="stack">
      <span className="label">Tayyor mavzular</span>
      <div className="wb-themes">
        {Object.entries(themes).map(([code, p]) => (
          <button
            key={code}
            className={`wb-theme ${t.preset === code ? "is-selected" : ""}`}
            style={{ background: p.background, color: p.text }}
            onClick={() => setTheme({ preset: code, adaptive: p.adaptive, primary: p.primary, background: p.background, surface: p.surface, text: p.text })}
          >
            <span className="wb-theme__dots">
              <i style={{ background: p.primary }} />
              <i style={{ background: p.surface }} />
            </span>
            <b>{p.title}</b>
          </button>
        ))}
      </div>

      <section className="card stack">
        <button className="sf-toggle" onClick={() => setTheme({ adaptive: !t.adaptive })}>
          <span>
            Telegram mavzusiga moslashish
            <span className="sf-hint">Foydalanuvchining Telegram ranglari (yorug'/qorong'i) ishlatiladi</span>
          </span>
          <span className={`switch ${t.adaptive ? "is-on" : ""}`}>
            <i />
          </span>
        </button>
        <div className="wb-colors">
          {color("primary", "Asosiy rang")}
          {color("background", "Fon")}
          {color("surface", "Kartochkalar")}
          {color("text", "Matn")}
        </div>
        <label className="sf-field">
          <span className="sf-label">Burchaklar yumaloqligi · {t.radius}px</span>
          <input type="range" min={0} max={28} value={t.radius} onChange={(e) => setTheme({ radius: Number(e.target.value) })} />
        </label>
        <div className="sf-field">
          <span className="sf-label">Shrift</span>
          <div className="segmented segmented--small">
            {FONTS.map(([v, l]) => (
              <button key={v} className={t.font === v ? "is-selected" : ""} onClick={() => setTheme({ font: v })}>
                {l}
              </button>
            ))}
          </div>
        </div>
      </section>

      {showPreview && (
        <>
          <span className="label">Ko'rinish</span>
          <div className="wb-frame">
            <WebAppRuntime doc={doc} appId="style-preview" mode="preview" mediaSrc={mediaUrl} botUsername={botUsername} branding={null} onSubmit={previewSubmit} />
          </div>
        </>
      )}
    </div>
  );
}

// ------------------------------------------------------------
// Sozlamalar
// ------------------------------------------------------------

function SettingsTab({
  botId,
  doc,
  update,
  info,
  setInfo,
  templates,
  toast,
  onReplaced,
  ctx,
}: {
  botId: number;
  doc: AppDoc;
  update: (fn: (d: AppDoc) => void) => void;
  info: WebAppInfo;
  setInfo: (i: WebAppInfo) => void;
  templates: WebAppState["templates"];
  toast: Toast;
  onReplaced: (i: WebAppInfo) => void;
  ctx: { pages: WAPage[]; toast: Toast };
}) {
  const [menuButton, setMenuButton] = useState(info.menu_button);
  const [menuText, setMenuText] = useState(info.menu_button_text);
  const [replacing, setReplacing] = useState(false);
  const menuDirty = menuButton !== info.menu_button || menuText !== info.menu_button_text;

  const saveMenu = async () => {
    try {
      setInfo(await api.saveWebAppSettings(botId, menuButton, menuText.trim() || "Ochish"));
      toast("Menyu tugmasi saqlandi");
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <div className="stack">
      <section className="card stack">
        <span className="label">Ilova</span>
        <SpecForm
          spec={[
            { kind: "text", key: "title", label: "Ilova nomi", max: 64 },
            { kind: "text", key: "currency", label: "Valyuta", max: 12, placeholder: "so'm" },
          ]}
          value={doc.settings}
          onChange={(next) => update((d) => void (d.settings = { ...d.settings, ...next }))}
          ctx={ctx}
        />
      </section>

      <section className="card stack">
        <span className="label">Buyurtma formasi (savatcha)</span>
        <p className="hint">Mahsulotlar bloki bo'lsa, foydalanuvchi savatchadan shu formani to'ldirib buyurtma beradi.</p>
        <SpecForm
          spec={[
            { kind: "list", key: "checkout_fields", label: "Maydonlar", max: 12, title: (f: any) => `${f.required ? "* " : ""}${f.label}`, make: newField, item: FORM_FIELD_SPEC },
            { kind: "textarea", key: "checkout_success", label: "Buyurtmadan keyin", max: 300, rows: 2 },
          ]}
          value={doc.settings}
          onChange={(next) => update((d) => void (d.settings = { ...d.settings, ...next }))}
          ctx={ctx}
        />
      </section>

      <section className="card stack">
        <span className="label">Botdagi menyu tugmasi</span>
        <button className="sf-toggle" onClick={() => setMenuButton(!menuButton)}>
          <span>
            Ilovani menyu tugmasidan ochish
            <span className="sf-hint">Bot chatining pastki chap burchagidagi tugma ilovani ochadi</span>
          </span>
          <span className={`switch ${menuButton ? "is-on" : ""}`}>
            <i />
          </span>
        </button>
        {menuButton && <input className="input" maxLength={32} value={menuText} onChange={(e) => setMenuText(e.target.value)} placeholder="Ochish" />}
        {menuDirty && (
          <button className="btn btn--primary btn--compact" onClick={saveMenu}>
            Saqlash
          </button>
        )}
        <p className="hint">Bot menyusidagi tugmalarga ham «Web App» amalini berib, ilovani ochish mumkin.</p>
      </section>

      {info.published && info.url && (
        <section className="card stack">
          <span className="label">Havola</span>
          <code className="wb-url">{info.url}</code>
          <button
            className="btn btn--ghost btn--compact"
            onClick={async () => {
              if (!(await confirmDialog("Ilova e'londan olinsinmi? Foydalanuvchilar uni ocha olmaydi (qoralama saqlanadi)."))) return;
              try {
                setInfo(await api.unpublishWebApp(botId));
                toast("Ilova e'londan olindi");
              } catch (e) {
                toast((e as Error).message, "err");
              }
            }}
          >
            E'londan olish
          </button>
        </section>
      )}

      <section className="card stack">
        <span className="label">Boshqa shablon bilan boshlash</span>
        <p className="hint">Qoralama tanlangan shablon bilan almashtiriladi. E'lon qilingan ilova «E'lon» bosilmaguncha o'zgarmaydi.</p>
        {replacing ? (
          <TemplateGrid
            templates={templates}
            busy={false}
            onPick={async (code) => {
              if (!(await confirmDialog("Joriy qoralama o'chib, shablon bilan almashtirilsinmi?"))) return;
              try {
                const res = await api.createWebApp(botId, code);
                onReplaced(res.app!);
                setReplacing(false);
                toast("Shablon qo'yildi");
              } catch (e) {
                toast((e as Error).message, "err");
              }
            }}
          />
        ) : (
          <button className="btn btn--ghost btn--compact" onClick={() => setReplacing(true)}>
            <LayoutTemplate size={16} /> Shablonlarni ko'rish
          </button>
        )}
      </section>
    </div>
  );
}

// ------------------------------------------------------------
// Arizalar va buyurtmalar
// ------------------------------------------------------------

function InboxTab({ botId, currency }: { botId: number; currency: string }) {
  const [filter, setFilter] = useState<"new" | "all">("new");
  const { data, refetch } = useQuery({
    queryKey: ["webapp-inbox", botId, filter],
    queryFn: () => api.webAppSubmissions(botId, filter === "new" ? "new" : undefined),
    refetchInterval: 20000,
  });
  const toggle = async (s: WASubmission) => {
    await api.setSubmissionStatus(botId, s.id, s.status === "new" ? "done" : "new");
    haptic("select");
    refetch();
  };
  return (
    <div className="stack">
      <div className="segmented segmented--small">
        <button className={filter === "new" ? "is-selected" : ""} onClick={() => setFilter("new")}>
          Yangi
        </button>
        <button className={filter === "all" ? "is-selected" : ""} onClick={() => setFilter("all")}>
          Hammasi
        </button>
      </div>
      {!data ? (
        <div className="spinner spinner--center" />
      ) : data.items.length === 0 ? (
        <p className="hint center">{filter === "new" ? "Yangi ariza yo'q." : "Hali ariza yoki buyurtma kelmagan."}</p>
      ) : (
        data.items.map((s) => (
          <section key={s.id} className={`card wb-sub ${s.status === "done" ? "is-done" : ""}`}>
            <div className="wb-sub__head">
              <b>
                {s.kind === "order" ? "🛒" : "📝"} {s.title} #{s.id}
              </b>
              <span className="hint">{s.created_at ? new Date(s.created_at).toLocaleString("ru-RU") : ""}</span>
            </div>
            <span className="hint">
              👤 {s.user.name || "Foydalanuvchi"}
              {s.user.username ? ` · @${s.user.username}` : ""}
            </span>
            {s.data.items?.map((it) => (
              <div key={it.id} className="wb-sub__row">
                <span>
                  {it.title} × {it.qty}
                </span>
                <span>{formatMoney(it.sum, currency)}</span>
              </div>
            ))}
            {s.total !== null && (
              <div className="wb-sub__row wb-sub__total">
                <span>Jami</span>
                <b>{formatMoney(s.total, currency)}</b>
              </div>
            )}
            {Object.entries(s.data.fields ?? {}).map(([k, v]) => (
              <div key={k} className="wb-sub__field">
                <span className="hint">{k}</span>
                <span>{v}</span>
              </div>
            ))}
            <div className="wb-row-actions">
              {s.user.username && (
                <button className="btn btn--ghost btn--compact" onClick={() => openLink(`https://t.me/${s.user.username}`)}>
                  Yozish
                </button>
              )}
              <button className="btn btn--ghost btn--compact" onClick={() => toggle(s)}>
                {s.status === "new" ? "✅ Bajarildi" : "↩️ Yangi deb belgilash"}
              </button>
            </div>
          </section>
        ))
      )}
      <p className="hint center">Har bir ariza sizga botda ham keladi — «Reply» qilib javob bering.</p>
    </div>
  );
}
