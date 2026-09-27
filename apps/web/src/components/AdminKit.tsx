import { useQueryClient } from "@tanstack/react-query";
import { Minus, Plus } from "lucide-react";
import type { ReactNode } from "react";
import { haptic } from "../tg";

// Admin bo'limlari uchun umumiy kichik komponentlar.

export type Toast = (text: string, kind?: "ok" | "err") => void;
// Mutatsiyadan keyin tegishli ro'yxatlar va foydalanuvchi holati (narxlar) yangilansin.
export function useRefresh() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ["admin"] });
    qc.invalidateQueries({ queryKey: ["state"] });
  };
}

export async function run(toast: Toast, fn: () => Promise<unknown>, ok: string): Promise<boolean> {
  try {
    await fn();
    haptic("success");
    toast(ok);
    return true;
  } catch (e) {
    haptic("error");
    toast((e as Error).message, "err");
    return false;
  }
}

// --- Kichik UI bo'laklari ---

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="field">
      <label className="label">{label}</label>
      {children}
      {hint && <p className="hint field__hint">{hint}</p>}
    </div>
  );
}

export function Toggle({ on, onChange, children }: { on: boolean; onChange: (v: boolean) => void; children: ReactNode }) {
  return (
    <button className="toggle-row" onClick={() => onChange(!on)}>
      <span className="toggle-row__body">{children}</span>
      <span className={`switch ${on ? "is-on" : ""}`}>
        <i />
      </span>
    </button>
  );
}

export function Stepper({ value, min, max, onChange }: { value: number; min: number; max: number; onChange: (v: number) => void }) {
  const set = (v: number) => onChange(Math.max(min, Math.min(max, v)));
  return (
    <div className="stepper">
      <button onClick={() => set(value - 1)} disabled={value <= min} aria-label="Kamaytirish">
        <Minus size={16} />
      </button>
      <input inputMode="numeric" value={value} onChange={(e) => set(Number(e.target.value.replace(/\D/g, "")) || min)} />
      <button onClick={() => set(value + 1)} disabled={value >= max} aria-label="Oshirish">
        <Plus size={16} />
      </button>
    </div>
  );
}

export function NumberInput({ value, onChange, placeholder, suffix }: { value: string; onChange: (v: string) => void; placeholder?: string; suffix?: string }) {
  return (
    <div className="input-suffix">
      <input className="input" inputMode="numeric" value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value.replace(/\D/g, ""))} />
      {suffix && <span>{suffix}</span>}
    </div>
  );
}

export function Empty({ icon, text }: { icon: ReactNode; text: string }) {
  return (
    <div className="card placeholder">
      {icon}
      <span>{text}</span>
    </div>
  );
}

export function StatCard({ icon, value, label, tone }: { icon: ReactNode; value: ReactNode; label: string; tone?: string }) {
  return (
    <div className={`stat stat--${tone ?? "default"}`}>
      <span className="stat__icon">{icon}</span>
      <span className="stat__value">{value}</span>
      <span className="stat__label">{label}</span>
    </div>
  );
}

