"""Viktorina matnini tahlil qilish (toza funksiya):

    Poytaxt qaysi shahar?
    +Toshkent
    -Samarqand
    -Buxoro
    ? Toshkent 1930 yildan poytaxt     (ixtiyoriy izoh)

Savollar bo'sh qator bilan ajratiladi. «+» — to'g'ri javob (bitta), «-» — noto'g'ri."""


def parse_quiz(text: str) -> tuple[list[dict], str | None]:
    """(savollar, xato matni)."""
    blocks = [b for b in (text or "").replace("\r", "").split("\n\n") if b.strip()]
    out: list[dict] = []
    for n, block in enumerate(blocks, 1):
        lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
        question = lines[0]
        options: list[str] = []
        answer = None
        explain = ""
        for ln in lines[1:]:
            if ln[0] in "+-" and len(ln) > 1:
                if ln[0] == "+":
                    if answer is not None:
                        return [], f"{n}-savolda bittadan ortiq to'g'ri javob (+) bor"
                    answer = len(options)
                options.append(ln[1:].strip()[:60])
            elif ln[0] == "?":
                explain = ln[1:].strip()[:300]
            else:
                return [], f"{n}-savol: «{ln[:30]}» qatori noto'g'ri — javoblar + yoki - bilan boshlansin"
        if len(options) < 2 or len(options) > 6:
            return [], f"{n}-savolda 2 dan 6 gacha javob (+ / -) bo'lsin"
        if answer is None:
            return [], f"{n}-savolda to'g'ri javob (+) belgilanmagan"
        out.append({"q": question[:300], "options": options[:6], "answer": answer, "explain": explain, "points": 1})
    if not out:
        return [], "Savol topilmadi"
    return out[:40], None
