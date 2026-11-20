"""Telegram Bot API qamrov matritsasi (O14): qaysi metod va update turlari botrunner'da ishlatiladi.

    python tools/api_coverage.py                       # jadvalni ko'rsatadi
    python tools/api_coverage.py --write docs/api-coverage.md
    python tools/api_coverage.py --spec api.json       # rasmiy sxemadan (methods: {nom: ...}) yangi metodlarni qo'shadi
    python tools/api_coverage.py --min 0.25            # qamrov 25% dan past bo'lsa xato bilan chiqadi (CI)

Qoplangan = metod nomi runner kodida (apps/botrunner, packages/core) qo'shtirnoq ichida uchraydi YOKI imkoniyat reyestrida (core/capabilities)
e'lon qilingan. Ro'yxat bazaviy (Bot API 8.x); yangi versiyalar uchun --spec bilan rasmiy sxemani bering — yangi metodlar «qoplanmagan»
bo'lib chiqadi va rejaga (docs/telegram-api-roadmap.md) qo'shiladi."""

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

SECTIONS: dict[str, list[str]] = {
    "Update'lar va webhook": ["getUpdates", "setWebhook", "deleteWebhook", "getWebhookInfo", "logOut", "close"],
    "Bot haqida": ["getMe", "setMyCommands", "deleteMyCommands", "getMyCommands", "setMyName", "getMyName", "setMyDescription", "getMyDescription", "setMyShortDescription", "getMyShortDescription", "setChatMenuButton", "getChatMenuButton", "setMyDefaultAdministratorRights", "getMyDefaultAdministratorRights"],
    "Xabar yuborish": ["sendMessage", "forwardMessage", "forwardMessages", "copyMessage", "copyMessages", "sendPhoto", "sendAudio", "sendDocument", "sendVideo", "sendAnimation", "sendVoice", "sendVideoNote", "sendPaidMedia", "sendMediaGroup", "sendLocation", "sendVenue", "sendContact", "sendPoll", "sendDice", "sendChatAction", "setMessageReaction", "sendSticker", "sendGame"],
    "Xabarni o'zgartirish": ["editMessageText", "editMessageCaption", "editMessageMedia", "editMessageLiveLocation", "stopMessageLiveLocation", "editMessageReplyMarkup", "stopPoll", "deleteMessage", "deleteMessages"],
    "Fayl va foydalanuvchi": ["getFile", "getUserProfilePhotos", "setUserEmojiStatus", "getUserChatBoosts", "getBusinessConnection"],
    "Chat boshqaruvi": ["banChatMember", "unbanChatMember", "restrictChatMember", "promoteChatMember", "setChatAdministratorCustomTitle", "banChatSenderChat", "unbanChatSenderChat", "setChatPermissions", "exportChatInviteLink", "createChatInviteLink", "editChatInviteLink", "createChatSubscriptionInviteLink", "editChatSubscriptionInviteLink", "revokeChatInviteLink", "approveChatJoinRequest", "declineChatJoinRequest", "setChatPhoto", "deleteChatPhoto", "setChatTitle", "setChatDescription", "pinChatMessage", "unpinChatMessage", "unpinAllChatMessages", "leaveChat", "getChat", "getChatAdministrators", "getChatMemberCount", "getChatMember", "setChatStickerSet", "deleteChatStickerSet"],
    "Forum mavzulari": ["getForumTopicIconStickers", "createForumTopic", "editForumTopic", "closeForumTopic", "reopenForumTopic", "deleteForumTopic", "unpinAllForumTopicMessages", "editGeneralForumTopic", "closeGeneralForumTopic", "reopenGeneralForumTopic", "hideGeneralForumTopic", "unhideGeneralForumTopic", "unpinAllGeneralForumTopicMessages"],
    "Callback va inline": ["answerCallbackQuery", "answerInlineQuery", "answerWebAppQuery", "savePreparedInlineMessage"],
    "To'lovlar va Stars": ["sendInvoice", "createInvoiceLink", "answerShippingQuery", "answerPreCheckoutQuery", "getMyStarBalance", "getStarTransactions", "refundStarPayment", "editUserStarSubscription", "getAvailableGifts", "sendGift"],
    "Stikerlar": ["getStickerSet", "getCustomEmojiStickers", "uploadStickerFile", "createNewStickerSet", "addStickerToSet", "setStickerPositionInSet", "deleteStickerFromSet", "replaceStickerInSet", "setStickerEmojiList", "setStickerKeywords", "setStickerMaskPosition", "setStickerSetTitle", "setStickerSetThumbnail", "setCustomEmojiStickerSetThumbnail", "deleteStickerSet"],
    "Business": ["readBusinessMessage", "deleteBusinessMessages", "setBusinessAccountName", "setBusinessAccountUsername", "setBusinessAccountBio", "setBusinessAccountProfilePhoto", "removeBusinessAccountProfilePhoto", "setBusinessAccountGiftSettings", "getBusinessAccountStarBalance", "transferBusinessAccountStars", "getBusinessAccountGifts", "convertGiftToStars", "upgradeGift", "transferGift", "postStory", "editStory", "deleteStory"],
    "O'yinlar va Passport (ataylab qilinmaydi)": ["setGameScore", "getGameHighScores", "setPassportDataErrors"],
}
UPDATES = ["message", "edited_message", "channel_post", "edited_channel_post", "business_connection", "business_message", "edited_business_message", "deleted_business_messages", "message_reaction", "message_reaction_count", "inline_query", "chosen_inline_result", "callback_query", "shipping_query", "pre_checkout_query", "purchased_paid_media", "poll", "poll_answer", "my_chat_member", "chat_member", "chat_join_request", "chat_boost", "removed_chat_boost"]
IGNORED = {"setGameScore", "getGameHighScores", "setPassportDataErrors", "sendGame", "logOut", "close", "setUserEmojiStatus"}
DYNAMIC = {"sendVideo", "sendAnimation", "sendDocument", "sendAudio", "sendVoice", "sendVideoNote", "sendSticker"}  # "send" + tur.capitalize()
HANDLED_UPDATES_HINT = {"message", "callback_query"}  # allowed_updates ro'yxatida bo'lmasa ham doim ishlanadi


def source_text() -> str:
    parts = []
    for base in (ROOT / "apps" / "botrunner", ROOT / "packages" / "core" / "core"):
        for p in base.rglob("*.py"):
            if "capabilities.py" in p.name or "bot_ai.py" in p.name or "botbuilder.py" in p.name:
                continue  # prompt/hujjat matnlari "qoplangan" deb hisoblanmasin
            parts.append(p.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def covered_methods(text: str) -> set[str]:
    from core import capabilities

    found = {m for names in SECTIONS.values() for m in names if re.search(rf'"{m}"', text)}
    return found | DYNAMIC | capabilities.bot_api_methods()


def covered_updates(text: str) -> set[str]:
    m = re.search(r'"allowed_updates":\s*\[([^\]]*)\]', text)
    allowed = set(re.findall(r'"(\w+)"', m.group(1))) if m else set()
    return (allowed | HANDLED_UPDATES_HINT) & set(UPDATES)


def build(spec_path: str | None) -> tuple[str, float]:
    sections = {k: list(v) for k, v in SECTIONS.items()}
    if spec_path:
        data = json.loads(pathlib.Path(spec_path).read_text())
        known = {m for names in sections.values() for m in names}
        extra = sorted(set(data.get("methods", {})) - known)
        if extra:
            sections["Yangi (spec'dan)"] = extra
    text = source_text()
    cov = covered_methods(text)
    upd = covered_updates(text)
    scored = [m for k, names in sections.items() for m in names if m not in IGNORED]
    done = [m for m in scored if m in cov]
    pct = len(done) / len(scored)
    out = [
        "# Telegram Bot API qamrovi (avtomatik hisobot)",
        "",
        "`python tools/api_coverage.py --write docs/api-coverage.md` bilan yangilanadi.",
        "",
        f"**Metodlar: {len(done)}/{len(scored)} ({pct * 100:.0f}%)** · update turlari: {len(upd)}/{len(UPDATES)} ({len(upd) / len(UPDATES) * 100:.0f}%)",
        "",
        "## Update turlari",
        "",
        " ".join(f"{'✅' if u in upd else '❌'} `{u}`" for u in UPDATES),
        "",
    ]
    for name, methods in sections.items():
        have = [m for m in methods if m in cov]
        out += [f"## {name} ({len(have)}/{len(methods)})", "", " ".join(f"{'✅' if m in cov else ('⛔' if m in IGNORED else '❌')} `{m}`" for m in methods), ""]
    return "\n".join(out), pct


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec")
    ap.add_argument("--write")
    ap.add_argument("--min", type=float, default=0.0)
    args = ap.parse_args()
    report, pct = build(args.spec)
    if args.write:
        pathlib.Path(args.write).write_text(report, encoding="utf-8")
    print(report.split("## ")[0].strip())
    if pct < args.min:
        print(f"\n❌ Qamrov {pct * 100:.0f}% — talab qilingan {args.min * 100:.0f}% dan past", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
