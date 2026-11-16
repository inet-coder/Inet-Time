import { useEffect, useRef } from "react";

/** Ctrl/⌘+S — saqlash (kompyuterda). Har doim eng so'nggi funksiya chaqiriladi. */
export function useSaveShortcut(onSave: () => void, enabled: boolean) {
  const ref = useRef(onSave);
  ref.current = onSave;
  useEffect(() => {
    if (!enabled) return;
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        ref.current();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [enabled]);
}

/** Esc — ochiq panelni yopish. */
export function useEscape(onEscape: (() => void) | null) {
  const ref = useRef(onEscape);
  ref.current = onEscape;
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && ref.current) {
        // Matn kiritilayotgan bo'lsa ham yopiladi — lekin avval fokus olib tashlanadi
        (document.activeElement as HTMLElement | null)?.blur?.();
        ref.current();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
}
