export function money(amount: number): string {
  return `${Math.round(amount).toLocaleString("ru-RU").replace(/,/g, " ")} so'm`;
}

export function intervalText(seconds: number): string {
  if (seconds % 86400 === 0) return `${seconds / 86400} kun`;
  if (seconds % 3600 === 0) return `${seconds / 3600} soat`;
  return `${Math.round(seconds / 60)} daqiqa`;
}

export function whenText(iso: string | null, timezone: string): string {
  if (!iso) return "";
  const at = new Date(iso);
  const minutes = Math.round((at.getTime() - Date.now()) / 60000);
  const hhmm = at.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", timeZone: timezone });
  if (minutes <= 0) return "hozir";
  if (minutes < 60) return `${minutes} daqiqadan keyin`;
  const sameDay =
    at.toLocaleDateString("ru-RU", { timeZone: timezone }) === new Date().toLocaleDateString("ru-RU", { timeZone: timezone });
  return sameDay ? `bugun ${hhmm} da` : `ertaga ${hhmm} da`;
}

export function daysLeft(iso: string | null): number {
  if (!iso) return 0;
  return Math.max(0, Math.ceil((new Date(iso).getTime() - Date.now()) / 86400000));
}

export async function fileToJpegBase64(file: File, maxSide = 1280): Promise<string> {
  // Telefon rasmlari katta — yuklashdan oldin kichraytiramiz (profil rasmi uchun 1280px yetarli).
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.88).split(",")[1];
}

export function dateText(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString("ru-RU") : "";
}

// <input type="date"> qiymati (YYYY-MM-DD) <-> ISO. Tanlangan kun oxirigacha amal qiladi (Toshkent vaqti).
export function toDateInput(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("sv-SE", { timeZone: "Asia/Tashkent" });
}

export function fromDateInput(value: string): string | null {
  return value ? `${value}T23:59:59+05:00` : null;
}
