// Web App renderer: e'lon qilingan ilova (Telegram ichida) va konstruktordagi jonli ko'rinish — BIR XIL kod.
// Shu sababli egasi konstruktorda nimani ko'rsa, foydalanuvchilar ham aynan shuni ko'radi.
import {
  ArrowLeft,
  Check,
  ChevronDown,
  ChevronRight,
  Globe,
  Camera,
  MapPin,
  Minus,
  Phone,
  Plus,
  Send,
  ShoppingBag,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { tg } from "../tg";
import {
  formatMoney,
  youtubeId,
  type AppDoc,
  type FormField,
  type Product,
  type SubmitPayload,
  type WAAction,
  type WABlock,
  type WAPage,
  type WATheme,
} from "./types";
import "./runtime.css";

export type RuntimeProps = {
  doc: AppDoc;
  appId: number | string;
  mediaSrc: (id: number) => string;
  botUsername: string | null;
  branding: string | null;
  mode: "live" | "preview";
  onSubmit: (payload: SubmitPayload) => Promise<{ message: string }>;
  /** Konstruktor: qaysi sahifa ko'rsatilsin (tahrirlanayotgan sahifa) */
  page?: string;
  onPageChange?: (pageId: string) => void;
};

const FONT_STACKS: Record<WATheme["font"], string> = {
  system: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif',
  rounded: 'ui-rounded, "SF Pro Rounded", "Nunito", "Varela Round", -apple-system, "Segoe UI", sans-serif',
  serif: 'ui-serif, "New York", Georgia, "Times New Roman", serif',
  mono: 'ui-monospace, "SF Mono", Menlo, Consolas, monospace',
};

function luminance(hex: string): number {
  const v = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => {
    const c = parseInt(v.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function isHex(v: string | undefined): v is string {
  return !!v && /^#[0-9a-fA-F]{6}$/.test(v);
}

export function themeStyle(theme: WATheme, useTelegram: boolean): CSSProperties {
  let { primary, background, surface, text } = theme;
  const tp = useTelegram && theme.adaptive ? tg?.themeParams : undefined;
  if (tp) {
    if (isHex(tp.button_color)) primary = tp.button_color;
    if (isHex(tp.secondary_bg_color)) background = tp.secondary_bg_color;
    else if (isHex(tp.bg_color)) background = tp.bg_color;
    if (isHex(tp.section_bg_color)) surface = tp.section_bg_color;
    else if (isHex(tp.bg_color)) surface = tp.bg_color;
    if (isHex(tp.text_color)) text = tp.text_color;
  }
  return {
    "--wa-primary": primary,
    "--wa-on-primary": luminance(primary) > 0.5 ? "#111111" : "#ffffff",
    "--wa-bg": background,
    "--wa-surface": surface,
    "--wa-text": text,
    "--wa-radius": `${theme.radius}px`,
    "--wa-font": FONT_STACKS[theme.font] ?? FONT_STACKS.system,
    colorScheme: luminance(background) < 0.2 ? "dark" : "light",
  } as CSSProperties;
}

function haptic(kind: "light" | "success" | "error" = "light") {
  const h = tg?.HapticFeedback;
  try {
    if (!h) return;
    if (kind === "light") h.impactOccurred("light");
    else h.notificationOccurred(kind);
  } catch {
    /* eski versiya */
  }
}

function openUrl(url: string) {
  if (url.startsWith("https://t.me/") || url.startsWith("tg://")) {
    if (tg) tg.openTelegramLink(url);
    else window.open(url, "_blank");
  } else if (tg?.openLink) tg.openLink(url);
  else window.open(url, "_blank", "noopener");
}

// Oddiy formatlash: **qalin**, havolalar, qator tashlash. HTML hech qachon ishlatilmaydi.
function Rich({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <>
      {lines.map((line, i) => (
        <span key={i}>
          {i > 0 && <br />}
          {line.split(/(\*\*[^*]+\*\*|https?:\/\/[^\s]+)/g).map((part, j) => {
            if (part.startsWith("**") && part.endsWith("**") && part.length > 4) return <b key={j}>{part.slice(2, -2)}</b>;
            if (/^https?:\/\//.test(part))
              return (
                <a key={j} href={part} onClick={(e) => (e.preventDefault(), openUrl(part))}>
                  {part.replace(/^https?:\/\//, "")}
                </a>
              );
            return part;
          })}
        </span>
      ))}
    </>
  );
}

// --- Savatcha ---

type Cart = Record<string, number>;

function useCart(appId: number | string, persist: boolean): [Cart, (id: string, delta: number) => void, () => void] {
  const key = `wa-cart-${appId}`;
  const [cart, setCart] = useState<Cart>(() => {
    if (!persist) return {};
    try {
      return JSON.parse(localStorage.getItem(key) || "{}");
    } catch {
      return {};
    }
  });
  useEffect(() => {
    if (!persist) return;
    try {
      localStorage.setItem(key, JSON.stringify(cart));
    } catch {
      /* xotira yo'q */
    }
  }, [cart, key, persist]);
  const change = useCallback((id: string, delta: number) => {
    setCart((c) => {
      const qty = Math.max(0, Math.min(999, (c[id] ?? 0) + delta));
      const next = { ...c };
      if (qty === 0) delete next[id];
      else next[id] = qty;
      return next;
    });
  }, []);
  return [cart, change, () => setCart({})];
}

// --- Asosiy komponent ---

type View = { kind: "page" } | { kind: "cart" } | { kind: "done"; message: string };

export function WebAppRuntime(props: RuntimeProps) {
  const { doc, mode, page } = props;
  const visiblePages = doc.pages;
  const pageIds = useMemo(() => new Set(visiblePages.map((p) => p.id)), [visiblePages]);
  const [current, setCurrent] = useState<string>(page && pageIds.has(page) ? page : doc.start);
  const [history, setHistory] = useState<string[]>([]);
  const [view, setView] = useState<View>({ kind: "page" });
  const [lightbox, setLightbox] = useState<number | null>(null);
  const [cart, changeCart, clearCart] = useCart(props.appId, mode === "live");
  const rootRef = useRef<HTMLDivElement>(null);

  // Konstruktor boshqa sahifani tanlasa — o'sha sahifa ko'rsatiladi.
  useEffect(() => {
    if (page && pageIds.has(page)) {
      setCurrent(page);
      setHistory([]);
      setView({ kind: "page" });
    }
  }, [page, pageIds]);
  useEffect(() => {
    if (!pageIds.has(current)) setCurrent(doc.start);
  }, [pageIds, current, doc.start]);

  const products = useMemo(() => {
    const out: Record<string, Product> = {};
    for (const p of doc.pages) for (const b of p.blocks) if (b.type === "products" && !b.hidden) for (const it of b.items) out[it.id] = it;
    return out;
  }, [doc]);
  const cartLines = Object.entries(cart)
    .filter(([id]) => products[id])
    .map(([id, qty]) => ({ product: products[id], qty }));
  const cartCount = cartLines.reduce((n, l) => n + l.qty, 0);
  const cartTotal = cartLines.reduce((n, l) => n + l.qty * l.product.price, 0);
  const currency = doc.settings.currency;

  const scrollTop = () => {
    if (mode === "preview") rootRef.current?.scrollTo({ top: 0 });
    else window.scrollTo({ top: 0 });
  };

  const go = useCallback(
    (id: string) => {
      if (!pageIds.has(id)) return;
      setHistory((h) => [...h, current]);
      setCurrent(id);
      setView({ kind: "page" });
      props.onPageChange?.(id);
      scrollTop();
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [current, pageIds, props.onPageChange],
  );

  const back = useCallback(() => {
    if (view.kind !== "page") {
      setView({ kind: "page" });
      return;
    }
    setHistory((h) => {
      const prev = h[h.length - 1];
      if (prev) {
        setCurrent(prev);
        props.onPageChange?.(prev);
      }
      return h.slice(0, -1);
    });
    scrollTop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view.kind, props.onPageChange]);

  const canGoBack = history.length > 0 || view.kind !== "page";

  // Telegram'ning o'z «orqaga» tugmasi (faqat haqiqiy ilovada)
  useEffect(() => {
    if (mode !== "live" || !tg?.BackButton) return;
    try {
      if (canGoBack) tg.BackButton.show();
      else tg.BackButton.hide();
      tg.BackButton.onClick(back);
      return () => tg!.BackButton.offClick(back);
    } catch {
      return undefined;
    }
  }, [mode, canGoBack, back]);

  const runAction = (action: WAAction | undefined) => {
    if (!action || action.type === "none") return;
    haptic();
    switch (action.type) {
      case "page":
        if (action.page) go(action.page);
        break;
      case "url":
        if (action.url) openUrl(action.url);
        break;
      case "bot":
        if (props.botUsername) {
          openUrl(`https://t.me/${props.botUsername}`);
          if (mode === "live") tg?.close();
        }
        break;
      case "phone":
        if (action.phone) window.location.href = `tel:${action.phone.replace(/[^+\d]/g, "")}`;
        break;
      case "share":
        if (props.botUsername)
          openUrl(`https://t.me/share/url?url=${encodeURIComponent(`https://t.me/${props.botUsername}`)}&text=${encodeURIComponent(doc.settings.title)}`);
        break;
      case "cart":
        setView({ kind: "cart" });
        break;
    }
  };

  const navPages = visiblePages.filter((p) => p.in_nav);
  const pageObj: WAPage = visiblePages.find((p) => p.id === current) ?? visiblePages[0];
  const ctx: BlockCtx = { ...props, runAction, cart, changeCart, currency, openLightbox: setLightbox };

  return (
    <div ref={rootRef} className={`wa wa--${mode}`} style={themeStyle(doc.theme, mode === "live")}>
      {canGoBack && mode === "preview" && (
        <div className="wa-topbar">
          <button className="wa-icon-btn" onClick={back} aria-label="Orqaga">
            <ArrowLeft size={20} />
          </button>
          <span>{view.kind === "cart" ? "Savatcha" : pageObj.title}</span>
        </div>
      )}

      <main className="wa-main">
        {view.kind === "page" &&
          pageObj.blocks.filter((b) => !b.hidden).map((b) => <BlockView key={b.id} block={b} ctx={ctx} />)}
        {view.kind === "page" && pageObj.blocks.filter((b) => !b.hidden).length === 0 && (
          <div className="wa-empty">Bu sahifa hozircha bo'sh</div>
        )}
        {view.kind === "cart" && (
          <CartView
            ctx={ctx}
            lines={cartLines}
            total={cartTotal}
            onDone={(message) => {
              clearCart();
              setView({ kind: "done", message });
              haptic("success");
            }}
          />
        )}
        {view.kind === "done" && (
          <div className="wa-done">
            <span className="wa-done__icon">
              <Check size={34} />
            </span>
            <p>
              <Rich text={view.message} />
            </p>
            <button
              className="wa-btn wa-btn--primary"
              onClick={() => {
                setHistory([]);
                setCurrent(doc.start);
                setView({ kind: "page" });
              }}
            >
              Bosh sahifaga
            </button>
          </div>
        )}
        {props.branding && (
          <button className="wa-branding" onClick={() => openUrl(`https://t.me/${props.branding!.replace("@", "")}`)}>
            ⚡ {props.branding} orqali yaratilgan
          </button>
        )}
      </main>

      {cartCount > 0 && view.kind === "page" && (
        <button className="wa-cartbar" onClick={() => (haptic(), setView({ kind: "cart" }))}>
          <ShoppingBag size={19} />
          <span>Savatcha · {cartCount}</span>
          <b>{formatMoney(cartTotal, currency)}</b>
        </button>
      )}

      {navPages.length >= 2 && view.kind === "page" && (
        <nav className="wa-tabbar">
          {navPages.map((p) => (
            <button
              key={p.id}
              className={p.id === current ? "is-active" : ""}
              onClick={() => {
                haptic();
                setHistory([]);
                setCurrent(p.id);
                props.onPageChange?.(p.id);
                scrollTop();
              }}
            >
              <span className="wa-tabbar__emoji">{p.emoji || "•"}</span>
              {p.title}
            </button>
          ))}
        </nav>
      )}

      {lightbox !== null && (
        <div className="wa-lightbox" onClick={() => setLightbox(null)}>
          <img src={props.mediaSrc(lightbox)} alt="" />
          <button className="wa-icon-btn wa-lightbox__close" aria-label="Yopish">
            <X size={22} />
          </button>
        </div>
      )}
    </div>
  );
}

// --- Bloklar ---

type BlockCtx = RuntimeProps & {
  runAction: (a: WAAction | undefined) => void;
  cart: Cart;
  changeCart: (id: string, delta: number) => void;
  currency: string;
  openLightbox: (id: number) => void;
};

function BlockView({ block, ctx }: { block: WABlock; ctx: BlockCtx }): JSX.Element | null {
  switch (block.type) {
    case "hero":
      return (
        <section className={`wa-hero wa-hero--${block.align}`}>
          {block.media_id ? (
            <img className="wa-hero__img" src={ctx.mediaSrc(block.media_id)} alt="" />
          ) : block.emoji ? (
            <span className="wa-hero__emoji">{block.emoji}</span>
          ) : null}
          <h1>{block.title}</h1>
          {block.subtitle && (
            <p>
              <Rich text={block.subtitle} />
            </p>
          )}
          {block.button && (
            <button className="wa-btn wa-btn--primary" onClick={() => ctx.runAction(block.button!.action)}>
              {block.button.text}
            </button>
          )}
        </section>
      );
    case "heading": {
      const Tag = (`h${block.size}` as "h1" | "h2" | "h3");
      return <Tag className={`wa-heading wa-heading--${block.size} wa-align-${block.align}`}>{block.text}</Tag>;
    }
    case "text":
      return (
        <p className={`wa-text wa-align-${block.align} ${block.muted ? "wa-text--muted" : ""}`}>
          <Rich text={block.text} />
        </p>
      );
    case "image":
      if (!block.media_id) return null;
      return (
        <figure className="wa-image">
          <img
            src={ctx.mediaSrc(block.media_id)}
            alt=""
            style={block.ratio !== "auto" ? { aspectRatio: block.ratio.replace(":", " / "), objectFit: "cover" } : undefined}
            onClick={() => (block.action.type === "none" ? ctx.openLightbox(block.media_id!) : ctx.runAction(block.action))}
          />
          {block.caption && <figcaption>{block.caption}</figcaption>}
        </figure>
      );
    case "gallery":
      return (
        <div className={`wa-gallery wa-gallery--${block.columns}`}>
          {block.media_ids.map((id) => (
            <img key={id} src={ctx.mediaSrc(id)} alt="" onClick={() => ctx.openLightbox(id)} />
          ))}
        </div>
      );
    case "button":
      return (
        <button className={`wa-btn wa-btn--${block.style}`} onClick={() => ctx.runAction(block.action)}>
          {block.text}
        </button>
      );
    case "features":
      return (
        <div className={`wa-features wa-features--${block.columns}`}>
          {block.items.map((f, i) => (
            <div key={i} className="wa-card wa-feature">
              {f.emoji && <span className="wa-feature__emoji">{f.emoji}</span>}
              <b>{f.title}</b>
              {f.text && (
                <span className="wa-muted">
                  <Rich text={f.text} />
                </span>
              )}
            </div>
          ))}
        </div>
      );
    case "links":
      return (
        <div className="wa-card wa-links">
          {block.items.map((it, i) => (
            <button key={i} className="wa-link" onClick={() => ctx.runAction(it.action)} disabled={it.action.type === "none"}>
              {it.emoji && <span className="wa-link__emoji">{it.emoji}</span>}
              <span className="wa-link__body">
                <b>{it.title}</b>
                {it.subtitle && <span className="wa-muted">{it.subtitle}</span>}
              </span>
              {it.action.type !== "none" && <ChevronRight size={18} className="wa-muted" />}
            </button>
          ))}
        </div>
      );
    case "products":
      return (
        <section className="wa-products">
          {block.title && <h2 className="wa-heading wa-heading--2">{block.title}</h2>}
          <div className={`wa-products__grid wa-products__grid--${block.columns}`}>
            {block.items.map((p) => (
              <ProductCard key={p.id} product={p} ctx={ctx} wide={block.columns === 1} />
            ))}
          </div>
        </section>
      );
    case "form":
      return <FormView block={block} ctx={ctx} />;
    case "contacts":
      return (
        <div className="wa-card wa-links">
          {block.phone && (
            <button className="wa-link" onClick={() => ctx.runAction({ type: "phone", phone: block.phone })}>
              <Phone size={18} className="wa-link__icon" />
              <span className="wa-link__body">
                <b>{block.phone}</b>
                <span className="wa-muted">Qo'ng'iroq qilish</span>
              </span>
            </button>
          )}
          {block.telegram && (
            <button className="wa-link" onClick={() => openUrl(`https://t.me/${block.telegram}`)}>
              <Send size={18} className="wa-link__icon" />
              <span className="wa-link__body">
                <b>@{block.telegram}</b>
                <span className="wa-muted">Telegram</span>
              </span>
            </button>
          )}
          {block.instagram && (
            <button className="wa-link" onClick={() => openUrl(`https://instagram.com/${block.instagram}`)}>
              <Camera size={18} className="wa-link__icon" />
              <span className="wa-link__body">
                <b>@{block.instagram}</b>
                <span className="wa-muted">Instagram</span>
              </span>
            </button>
          )}
          {block.website && (
            <button className="wa-link" onClick={() => openUrl(block.website!)}>
              <Globe size={18} className="wa-link__icon" />
              <span className="wa-link__body">
                <b>{block.website.replace(/^https?:\/\//, "")}</b>
                <span className="wa-muted">Veb-sayt</span>
              </span>
            </button>
          )}
          {(block.address || block.map_url) && (
            <button className="wa-link" onClick={() => block.map_url && openUrl(block.map_url)} disabled={!block.map_url}>
              <MapPin size={18} className="wa-link__icon" />
              <span className="wa-link__body">
                <b>{block.address || "Xaritada ko'rish"}</b>
                {block.map_url && <span className="wa-muted">Xaritada ochish</span>}
              </span>
            </button>
          )}
        </div>
      );
    case "faq":
      return (
        <div className="wa-card wa-faq">
          {block.items.map((it, i) => (
            <FaqItem key={i} q={it.q} a={it.a} />
          ))}
        </div>
      );
    case "pricing":
      return (
        <div className="wa-pricing">
          {block.items.map((p, i) => (
            <div key={i} className={`wa-card wa-plan ${p.highlight ? "is-highlight" : ""}`}>
              <b className="wa-plan__name">{p.name}</b>
              {p.price && (
                <div className="wa-plan__price">
                  {p.price}
                  {p.period && <span className="wa-muted"> / {p.period}</span>}
                </div>
              )}
              {p.features.length > 0 && (
                <ul>
                  {p.features.map((f, j) => (
                    <li key={j}>
                      <Check size={15} /> {f}
                    </li>
                  ))}
                </ul>
              )}
              {p.button && (
                <button className={`wa-btn ${p.highlight ? "wa-btn--primary" : "wa-btn--secondary"}`} onClick={() => ctx.runAction(p.button!.action)}>
                  {p.button.text}
                </button>
              )}
            </div>
          ))}
        </div>
      );
    case "stats":
      return (
        <div className="wa-stats">
          {block.items.map((s, i) => (
            <div key={i} className="wa-card wa-stat">
              <b>{s.value}</b>
              <span className="wa-muted">{s.label}</span>
            </div>
          ))}
        </div>
      );
    case "countdown":
      return <CountdownView title={block.title} date={block.date} done={block.done_text} />;
    case "video": {
      const id = youtubeId(block.url);
      if (!id) return null;
      return (
        <figure className="wa-video">
          <iframe
            src={`https://www.youtube-nocookie.com/embed/${id}`}
            title="video"
            allow="accelerometer; encrypted-media; gyroscope; picture-in-picture; fullscreen"
            allowFullScreen
            loading="lazy"
          />
          {block.caption && <figcaption>{block.caption}</figcaption>}
        </figure>
      );
    }
    case "divider":
      return block.style === "line" ? <hr className={`wa-divider wa-divider--${block.size}`} /> : <div className={`wa-space wa-space--${block.size}`} />;
    default:
      return null;
  }
}

function ProductCard({ product: p, ctx, wide }: { product: Product; ctx: BlockCtx; wide: boolean }) {
  const qty = ctx.cart[p.id] ?? 0;
  return (
    <div className={`wa-card wa-product ${wide ? "wa-product--wide" : ""}`}>
      <div className="wa-product__media">
        {p.media_id ? <img src={ctx.mediaSrc(p.media_id)} alt="" /> : <span>{p.emoji || "🛍"}</span>}
        {p.badge && <i className="wa-badge">{p.badge}</i>}
      </div>
      <div className="wa-product__body">
        <b className="wa-product__title">{p.title}</b>
        {p.text && <span className="wa-muted wa-product__text">{p.text}</span>}
        <div className="wa-product__price">
          <b>{formatMoney(p.price, ctx.currency)}</b>
          {p.old_price ? <s className="wa-muted">{formatMoney(p.old_price, ctx.currency)}</s> : null}
        </div>
        {qty === 0 ? (
          <button className="wa-btn wa-btn--primary wa-btn--sm" onClick={() => (haptic(), ctx.changeCart(p.id, 1))}>
            <Plus size={16} /> Savatga
          </button>
        ) : (
          <div className="wa-stepper">
            <button onClick={() => (haptic(), ctx.changeCart(p.id, -1))} aria-label="Kamaytirish">
              <Minus size={16} />
            </button>
            <b>{qty}</b>
            <button onClick={() => (haptic(), ctx.changeCart(p.id, 1))} aria-label="Ko'paytirish">
              <Plus size={16} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function FaqItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`wa-faq__item ${open ? "is-open" : ""}`}>
      <button onClick={() => setOpen(!open)}>
        <b>{q}</b>
        <ChevronDown size={18} />
      </button>
      {open && (
        <p className="wa-muted">
          <Rich text={a} />
        </p>
      )}
    </div>
  );
}

function useNow(ms: number): number {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(t);
  }, [ms]);
  return now;
}

function CountdownView({ title, date, done }: { title: string; date: string; done: string }) {
  const now = useNow(1000);
  const target = new Date(date).getTime();
  const left = Math.max(0, target - now);
  const parts = [
    [Math.floor(left / 86400000), "kun"],
    [Math.floor(left / 3600000) % 24, "soat"],
    [Math.floor(left / 60000) % 60, "daqiqa"],
    [Math.floor(left / 1000) % 60, "soniya"],
  ] as const;
  return (
    <div className="wa-card wa-countdown">
      {title && <b>{title}</b>}
      {Number.isNaN(target) ? null : left === 0 ? (
        <p className="wa-countdown__done">{done}</p>
      ) : (
        <div className="wa-countdown__grid">
          {parts.map(([n, label]) => (
            <div key={label}>
              <strong>{String(n).padStart(2, "0")}</strong>
              <span className="wa-muted">{label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// --- Formalar ---

function validateField(f: FormField, value: string | boolean | undefined): string | null {
  const v = typeof value === "string" ? value.trim() : value;
  if (f.type === "checkbox") return f.required && !v ? "Belgilang" : null;
  if (!v) return f.required ? "To'ldiring" : null;
  const s = String(v);
  if (f.type === "phone" && !/^\+?[0-9 ()-]{5,20}$/.test(s)) return "Telefon raqami noto'g'ri";
  if (f.type === "email" && !/^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(s)) return "Email noto'g'ri";
  if (f.type === "number" && Number.isNaN(Number(s.replace(",", ".")))) return "Son kiriting";
  return null;
}

function Fields({
  fields,
  values,
  errors,
  onChange,
}: {
  fields: FormField[];
  values: Record<string, string | boolean>;
  errors: Record<string, string>;
  onChange: (id: string, v: string | boolean) => void;
}) {
  return (
    <>
      {fields.map((f) => {
        const v = values[f.id];
        const err = errors[f.id];
        const label = (
          <span className="wa-label">
            {f.label}
            {f.required && <i>*</i>}
          </span>
        );
        if (f.type === "checkbox")
          return (
            <label key={f.id} className={`wa-check ${err ? "is-err" : ""}`}>
              <input type="checkbox" checked={!!v} onChange={(e) => onChange(f.id, e.target.checked)} />
              <span>
                {f.label}
                {f.required && <i>*</i>}
              </span>
            </label>
          );
        if (f.type === "radio")
          return (
            <div key={f.id} className="wa-field">
              {label}
              <div className="wa-chips">
                {f.options.map((o) => (
                  <button key={o} type="button" className={v === o ? "is-selected" : ""} onClick={() => onChange(f.id, o)}>
                    {o}
                  </button>
                ))}
              </div>
              {err && <span className="wa-error">{err}</span>}
            </div>
          );
        return (
          <label key={f.id} className="wa-field">
            {label}
            {f.type === "textarea" ? (
              <textarea className={`wa-input ${err ? "is-err" : ""}`} rows={3} placeholder={f.placeholder} value={String(v ?? "")} maxLength={2000} onChange={(e) => onChange(f.id, e.target.value)} />
            ) : f.type === "select" ? (
              <select className={`wa-input ${err ? "is-err" : ""}`} value={String(v ?? "")} onChange={(e) => onChange(f.id, e.target.value)}>
                <option value="">— tanlang —</option>
                {f.options.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            ) : (
              <input
                className={`wa-input ${err ? "is-err" : ""}`}
                type={f.type === "phone" ? "tel" : f.type === "email" ? "email" : f.type === "number" ? "number" : f.type === "date" ? "date" : "text"}
                inputMode={f.type === "phone" ? "tel" : f.type === "number" ? "decimal" : undefined}
                placeholder={f.placeholder}
                value={String(v ?? "")}
                maxLength={500}
                onChange={(e) => onChange(f.id, e.target.value)}
              />
            )}
            {err && <span className="wa-error">{err}</span>}
          </label>
        );
      })}
    </>
  );
}

function useFormState(fields: FormField[]) {
  const [values, setValues] = useState<Record<string, string | boolean>>(() => {
    // Telegram foydalanuvchisi ismini oldindan to'ldiramiz (qulaylik)
    const name = tg?.initDataUnsafe.user?.first_name;
    const init: Record<string, string | boolean> = {};
    const nameField = fields.find((f) => f.type === "text" && /ism|name/i.test(f.id + f.label));
    if (name && nameField) init[nameField.id] = name;
    return init;
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const validate = () => {
    const next: Record<string, string> = {};
    for (const f of fields) {
      const e = validateField(f, values[f.id]);
      if (e) next[f.id] = e;
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  };
  const onChange = (id: string, v: string | boolean) => {
    setValues((s) => ({ ...s, [id]: v }));
    setErrors((e) => {
      const { [id]: _, ...rest } = e;
      return rest;
    });
  };
  return { values, errors, validate, onChange, reset: () => setValues({}) };
}

function FormView({ block, ctx }: { block: Extract<WABlock, { type: "form" }>; ctx: BlockCtx }) {
  const form = useFormState(block.fields);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    if (!form.validate()) {
      haptic("error");
      return;
    }
    setBusy(true);
    try {
      const res = await ctx.onSubmit({ kind: "form", block_id: block.id, values: form.values });
      setDone(res.message || block.success_text);
      form.reset();
      haptic("success");
    } catch (e) {
      setError((e as Error).message);
      haptic("error");
    } finally {
      setBusy(false);
    }
  };

  if (done)
    return (
      <div className="wa-card wa-form wa-form--done">
        <span className="wa-done__icon wa-done__icon--sm">
          <Check size={24} />
        </span>
        <p>
          <Rich text={done} />
        </p>
        <button className="wa-btn wa-btn--secondary wa-btn--sm" onClick={() => setDone(null)}>
          Yana yuborish
        </button>
      </div>
    );
  return (
    <div className="wa-card wa-form">
      {block.title && <h3 className="wa-heading wa-heading--3">{block.title}</h3>}
      <Fields fields={block.fields} values={form.values} errors={form.errors} onChange={form.onChange} />
      {error && <div className="wa-error wa-error--box">{error}</div>}
      <button className="wa-btn wa-btn--primary" disabled={busy} onClick={submit}>
        {busy ? "Yuborilmoqda…" : block.submit_text}
      </button>
    </div>
  );
}

function CartView({
  ctx,
  lines,
  total,
  onDone,
}: {
  ctx: BlockCtx;
  lines: { product: Product; qty: number }[];
  total: number;
  onDone: (message: string) => void;
}) {
  const fields = ctx.doc.settings.checkout_fields;
  const form = useFormState(fields);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (lines.length === 0)
    return (
      <div className="wa-empty">
        <ShoppingBag size={36} />
        <p>Savatcha bo'sh</p>
      </div>
    );

  const submit = async () => {
    setError(null);
    if (!form.validate()) {
      haptic("error");
      return;
    }
    setBusy(true);
    try {
      const res = await ctx.onSubmit({ kind: "order", items: lines.map((l) => ({ id: l.product.id, qty: l.qty })), values: form.values });
      onDone(res.message || ctx.doc.settings.checkout_success);
    } catch (e) {
      setError((e as Error).message);
      haptic("error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="wa-cart">
      <h2 className="wa-heading wa-heading--2">Savatcha</h2>
      <div className="wa-card wa-cart__lines">
        {lines.map(({ product: p, qty }) => (
          <div key={p.id} className="wa-cart__line">
            <div className="wa-cart__thumb">{p.media_id ? <img src={ctx.mediaSrc(p.media_id)} alt="" /> : <span>{p.emoji || "🛍"}</span>}</div>
            <div className="wa-cart__info">
              <b>{p.title}</b>
              <span className="wa-muted">{formatMoney(p.price * qty, ctx.currency)}</span>
            </div>
            <div className="wa-stepper wa-stepper--sm">
              <button onClick={() => ctx.changeCart(p.id, -1)} aria-label="Kamaytirish">
                <Minus size={14} />
              </button>
              <b>{qty}</b>
              <button onClick={() => ctx.changeCart(p.id, 1)} aria-label="Ko'paytirish">
                <Plus size={14} />
              </button>
            </div>
          </div>
        ))}
        <div className="wa-cart__total">
          <span>Jami</span>
          <b>{formatMoney(total, ctx.currency)}</b>
        </div>
      </div>
      <div className="wa-card wa-form">
        <h3 className="wa-heading wa-heading--3">Buyurtmani rasmiylashtirish</h3>
        <Fields fields={fields} values={form.values} errors={form.errors} onChange={form.onChange} />
        {error && <div className="wa-error wa-error--box">{error}</div>}
        <button className="wa-btn wa-btn--primary" disabled={busy} onClick={submit}>
          {busy ? "Yuborilmoqda…" : `Buyurtma berish · ${formatMoney(total, ctx.currency)}`}
        </button>
      </div>
    </div>
  );
}
