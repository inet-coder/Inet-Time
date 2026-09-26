import { Check, CircleAlert, Download, Eye, EyeOff, Info, Radio, Users } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { api, type BirthdayState, type PresenceMode, type PresenceState, type State } from "../api";
import { haptic } from "../tg";

type Callbacks = { state: State; onDone: (text: string) => void; onError: (text: string) => void };

const MONTHS = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"];

// --- 🎂 Tug'ilgan kun ---

export function BirthdayEditor({ state, onDone, onError }: Callbacks) {
  const accountId = state.account!.id;
  const [data, setData] = useState<BirthdayState | null>(null);
  const [day, setDay] = useState(1);
  const [month, setMonth] = useState(1);
  const [year, setYear] = useState("");
  const [busy, setBusy] = useState(false);

  const load = (d: BirthdayState) => {
    setData(d);
    if (d.day && d.month) {
      setDay(d.day);
      setMonth(d.month);
      setYear(d.year ? String(d.year) : "");
    }
  };

  useEffect(() => {
    api.birthday(accountId).then(load).catch((e: Error) => onError(e.message));
  }, [accountId, onError]);

  const run = async (fn: () => Promise<BirthdayState>, ok: string) => {
    setBusy(true);
    try {
      load(await fn());
      haptic("success");
      onDone(ok);
      return true;
    } catch (e) {
      haptic("error");
      onError((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  };

  // onDone oynani yopadi — shuning uchun sana saqlash uchun alohida, yopmaydigan variant.
  const saveDate = async () => {
    setBusy(true);
    try {
      load(await api.saveBirthday(accountId, { day, month, year: year ? Number(year) : null }));
      haptic("success");
    } catch (e) {
      haptic("error");
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const importFromTelegram = async () => {
    setBusy(true);
    try {
      load(await api.importBirthday(accountId));
      haptic("success");
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const useTemplate = (template: string) =>
    run(async () => {
      await api.enable({ account_id: accountId, service_code: "auto_bio", items: [{ template }] });
      return data!;
    }, "🎂 Bio'ga qo'yildi — har kuni o'zi yangilanadi");

  if (!data) return <div className="spinner spinner--center" />;
  const saved = data.birthday && data.day === day && data.month === month && (data.year ? String(data.year) : "") === year;

  return (
    <>
      <label className="label">Tug'ilgan kuningiz</label>
      <div className="date-row">
        <select className="input" value={day} onChange={(e) => setDay(Number(e.target.value))}>
          {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        <select className="input" value={month} onChange={(e) => setMonth(Number(e.target.value))}>
          {MONTHS.map((m, i) => (
            <option key={m} value={i + 1}>
              {m}
            </option>
          ))}
        </select>
        <input
          className="input"
          inputMode="numeric"
          placeholder="Yil"
          maxLength={4}
          value={year}
          onChange={(e) => setYear(e.target.value.replace(/\D/g, ""))}
        />
      </div>
      <p className="hint field__hint">Yil ixtiyoriy — faqat {"{age}"} (yosh) uchun kerak.</p>
      <div className="grid2">
        <button className="btn btn--primary btn--compact" disabled={busy || !!saved} onClick={saveDate}>
          {saved ? (
            <>
              <Check size={16} /> Saqlangan
            </>
          ) : (
            "Saqlash"
          )}
        </button>
        <button className="btn btn--ghost btn--compact" disabled={busy} onClick={importFromTelegram}>
          <Download size={16} /> Telegram'dan
        </button>
      </div>

      <label className="label">Bio uchun tayyor shablonlar</label>
      {!data.birthday && (
        <div className="notice">
          <Info size={18} />
          <span>Avval sanani saqlang — shablonlar tayyor ko'rinishi bilan chiqadi.</span>
        </div>
      )}
      <div className="presets">
        {data.templates.map((t) => (
          <button key={t.template} className="preset preset--live" disabled={busy || !t.preview} onClick={() => useTemplate(t.template)}>
            <span>{t.preview ?? t.template}</span>
            {t.error && data.birthday && <small className="hint">{t.error}</small>}
          </button>
        ))}
      </div>
      <p className="hint field__hint">Bosganingiz Avto bio sifatida yoqiladi. Boshqa qiziqarli shablonlar — «Avto bio» kartasida.</p>
    </>
  );
}

// --- 👁 Faollik holati ---

const MODES: { mode: PresenceMode; icon: ReactNode; title: string; desc: string; shows: string }[] = [
  { mode: "online", icon: <Radio size={20} />, title: "Doim onlayn", desc: "24/7 Online yoqiladi", shows: "online" },
  { mode: "recently", icon: <EyeOff size={20} />, title: "Yaqinda onlayn edi", desc: "Aniq vaqt hech kimga ko'rinmaydi", shows: "yaqinda onlayn edi" },
  { mode: "contacts", icon: <Users size={20} />, title: "Faqat kontaktlarga", desc: "Kontaktlar aniq vaqtni, qolganlar «yaqinda»ni ko'radi", shows: "kontaktlarga: 14:05 da · boshqalarga: yaqinda" },
  { mode: "default", icon: <Eye size={20} />, title: "Standart", desc: "Hamma aniq vaqtni ko'radi", shows: "bugun 14:05 da onlayn edi" },
];

export function PresenceEditor({ state, onDone, onError }: Callbacks) {
  const accountId = state.account!.id;
  const [data, setData] = useState<PresenceState | null>(null);
  const [busy, setBusy] = useState<PresenceMode | null>(null);

  useEffect(() => {
    api.presence(accountId).then(setData).catch((e: Error) => onError(e.message));
  }, [accountId, onError]);

  const choose = async (mode: PresenceMode) => {
    if (!data || mode === data.mode) return;
    setBusy(mode);
    try {
      setData(await api.savePresence(accountId, mode));
      haptic("success");
      onDone(`Faollik holati: ${MODES.find((m) => m.mode === mode)!.title}`);
    } catch (e) {
      haptic("error");
      onError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  if (!data) return <div className="spinner spinner--center" />;
  const current = MODES.find((m) => m.mode === data.mode)!;
  return (
    <>
      <div className="presence-preview">
        <span className="hint">Boshqalar ko'radi:</span>
        <b className={data.mode === "online" ? "is-online" : ""}>{current.shows}</b>
      </div>
      <div className="mode-list">
        {MODES.map((m) => {
          const locked = m.mode === "online" && !data.online_unlocked;
          return (
            <button
              key={m.mode}
              className={`mode ${data.mode === m.mode ? "is-selected" : ""}`}
              disabled={!!busy || locked}
              onClick={() => choose(m.mode)}
            >
              <span className="mode__icon">{m.icon}</span>
              <span className="mode__body">
                <b>{m.title}</b>
                <span className="hint">{locked ? "🔒 Tarifingizda yo'q" : m.desc}</span>
              </span>
              {busy === m.mode ? <span className="spinner spinner--sm" /> : data.mode === m.mode && <Check size={20} className="mode__check" />}
            </button>
          );
        })}
      </div>
      <div className="notice notice--warn">
        <CircleAlert size={18} />
        <span>Telegram qoidasi: vaqtingizni yashirsangiz, siz ham boshqalarning aniq vaqtini ko'rmaysiz (Premium'dan tashqari).</span>
      </div>
    </>
  );
}
