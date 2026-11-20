# Telegram Bot API bo'yicha to'liq imkoniyatlar rejasi

Maqsad: konstruktorda **Telegram Bot API'ning hamma narsasi** (xabar turlari, tugmalar, guruh/kanal boshqaruvi, inline rejim,
to'lovlar, Business, Mini App...) kodsiz, chatning o'zida yoki AI bilan ishlatiladigan bo'lsin — shunda **istalgan tizim**
(do'kon, CRM, guruh moderatori, pullik klub, o'yin, yordam xizmati, biznes-chatbot...) yig'ib bo'ladi.

Bu hujjat — "hechnima qolib ketmasligi" uchun: (1) hozirgi qamrov auditi, (2) Bot API bo'limlari bo'yicha to'liq jadval,
(3) raqamlangan imkoniyatlar katalogi (282 ta batafsil band), (4) arxitektura qarori, (5) bajarish tartibi va tekshiruv mezonlari.

---

## 1. Hozirgi qamrov (audit)

Runner hozir ≈ **28 ta** Bot API metodini ishlatadi (Bot API'da ≈ 160+ metod bor): `sendMessage`, `sendPhoto/Video/Animation/Document/Audio/
Voice/VideoNote/Sticker`, `copyMessage`, `editMessageText`, `editMessageReplyMarkup`, `deleteMessage`, `answerCallbackQuery`, `getUpdates`,
`getMe`, `getChat`, `getChatMember`, `setMyCommands`, `setChatMenuButton`, `sendInvoice`, `answerPreCheckoutQuery`, `sendChatAction`, `deleteWebhook`.
Qabul qilinadigan update'lar: `message`, `callback_query`, `my_chat_member`, `pre_checkout_query` (22 turdan 4 tasi).
Faqat **shaxsiy chat** (private) — guruh/kanal xabarlari e'tiborsiz. Taxminiy qamrov: **metodlar ≈ 17%**, update turlari ≈ 18%.

Kuchli tomonlar (poydevor): sahifa/tugma dvigateli, o'zgaruvchilar, formalar, referal, majburiy obuna, do'kon + to'lov, yozilish,
avto xabarlar, o'yinlar, tiketlar, integratsiyalar, kanal postlari, AI quruvchi, sifat to'plami.

Asosiy bo'shliqlar: (a) kontent turlari (albom, joylashuv, so'rovnoma, dice...), (b) tugma turlari (login, copy, switch_inline...),
(c) **guruh va kanal boshqaruvi**, (d) **inline rejim**, (e) to'lov v2 (Stars, obuna, yetkazish usullari), (f) **Telegram Business**,
(g) umumiy **oqim (flow) dvigateli** — modullar orasidagi bo'shliqlarni yopadigan "yelim", (h) masshtab (webhook, sharding, tezlik cheklovi),
(i) CRM/ma'lumot jadvallari va AI yordamchi.

---

## 2. Bot API bo'limlari bo'yicha qamrov jadvali

Belgilar: ✅ bor · 🟡 qisman · ❌ yo'q · ⛔ ataylab qilinmaydi.

### 2.1 Update'lar (qabul qilish)
| Update | Holat | Reja |
|---|---|---|
| message | 🟡 faqat private; matn/foto/kontakt/joylashuv ba'zi kirishlarda | F01, K31, G01 |
| edited_message | ❌ | F01 |
| channel_post, edited_channel_post | ❌ | G13 |
| callback_query | ✅ | B13 |
| inline_query, chosen_inline_result | ❌ | I01–I04 |
| shipping_query | ❌ | P04 |
| pre_checkout_query | ✅ | P14 |
| purchased_paid_media | ❌ | P22 |
| poll, poll_answer | ❌ | K09 |
| my_chat_member | 🟡 faqat bloklanish | G01 |
| chat_member | ❌ | G02, G25 |
| chat_join_request | ❌ | G17 |
| chat_boost, removed_chat_boost | ❌ | G27 |
| message_reaction, message_reaction_count | ❌ | K13 |
| business_connection, business_message, edited_business_message, deleted_business_messages | ❌ | S01–S05 |

### 2.2 Xabar yuborish metodlari
| Metod | Holat | Reja |
|---|---|---|
| sendMessage | ✅ (parse_mode HTML) | K16–K19, K24–K25 |
| forwardMessage(s), copyMessage(s) | 🟡 copyMessage | K20 |
| sendPhoto/Video/Animation/Audio/Document/Voice/VideoNote/Sticker | ✅ | K14–K15, K28–K29 |
| sendMediaGroup | ❌ | K01 |
| sendLocation, editMessageLiveLocation, stopMessageLiveLocation | ❌ | K02–K03 |
| sendVenue, sendContact | ❌ | K04–K05 |
| sendPoll, stopPoll | ❌ | K06–K08 |
| sendDice | ❌ | K10 |
| sendChatAction | 🟡 | K11 |
| sendPaidMedia | ❌ | K26, P22 |
| sendInvoice | 🟡 provayder tokeni bilan | P01–P09 |
| sendGame | ⛔ (HTML5 o'yin — o'z viktorinamiz bor) | — |
| sendGift, sendMessageDraft va yangi metodlar | ❌ | P23 (yangilari changelog bilan tekshiriladi, O14) |
| setMessageReaction | ❌ | K12 |

### 2.3 Xabarni o'zgartirish
| Metod | Holat | Reja |
|---|---|---|
| editMessageText / ReplyMarkup | ✅ | — |
| editMessageCaption / Media | ❌ | K22, K38 |
| deleteMessage / deleteMessages | 🟡 | K23 |
| pin/unpinChatMessage, unpinAllChatMessages | ❌ | K21 |

### 2.4 Tugmalar
| Tur | Holat | Reja |
|---|---|---|
| inline: url, callback_data, web_app | ✅ | — |
| inline: login_url, copy_text, switch_inline_query(+current/chosen_chat), pay, callback_game | ❌ | B01–B03, B09 |
| reply: text, request_contact, request_location, web_app | ✅ | — |
| reply: request_poll, request_users, request_chat, request_managed_bot* | ❌ | B04–B05 |
| resize, is_persistent, input_field_placeholder | 🟡 | B06–B07 |
| one_time_keyboard, selective, force_reply, remove_keyboard | 🟡 | B06–B07 |
| tugma rangi/ikonkasi (yangi Bot API) | ❌ | B08 (tekshiriladi) |

### 2.5 Chat boshqaruvi (guruh, supergroup, kanal)
`banChatMember, unbanChatMember, restrictChatMember, promoteChatMember, setChatAdministratorCustomTitle, banChatSenderChat, unbanChatSenderChat,
setChatPermissions, exportChatInviteLink, createChatInviteLink, editChatInviteLink, createChatSubscriptionInviteLink, editChatSubscriptionInviteLink,
revokeChatInviteLink, approveChatJoinRequest, declineChatJoinRequest, setChatPhoto, deleteChatPhoto, setChatTitle, setChatDescription, leaveChat,
getChat, getChatAdministrators, getChatMemberCount, getChatMember, setChatStickerSet, deleteChatStickerSet` — hammasi ❌ (faqat getChat/getChatMember ✅).
Forum: `createForumTopic, editForumTopic, closeForumTopic, reopenForumTopic, deleteForumTopic, unpinAllForumTopicMessages, editGeneralForumTopic,
closeGeneralForumTopic, reopenGeneralForumTopic, hideGeneralForumTopic, unhideGeneralForumTopic, unpinAllGeneralForumTopicMessages,
getForumTopicIconStickers` — ❌ → G19–G20.

### 2.6 Bot profili va sozlamalari
| Metod | Holat | Reja |
|---|---|---|
| setMyCommands/getMyCommands/deleteMyCommands (scope + til) | 🟡 faqat default | M04 |
| setMyName / getMyName | ❌ | M01 |
| setMyDescription / setMyShortDescription | ❌ | M02 |
| setMyProfilePhoto (yangi) | ❌ | M03 |
| setChatMenuButton / getChatMenuButton | 🟡 | M05 |
| setMyDefaultAdministratorRights | ❌ | M06 |
| getMyStarBalance, getStarTransactions, refundStarPayment | ❌ | P09 |
| setWebhook / getWebhookInfo | ❌ (long polling) | O01 |

### 2.7 Inline rejim
`answerInlineQuery` (InlineQueryResult: Article, Photo, Gif, Mpeg4Gif, Video, Audio, Voice, Document, Location, Venue, Contact, Game, Cached*),
`answerWebAppQuery`, `savePreparedInlineMessage` — ❌ → I01–I06, W02.

### 2.8 To'lovlar
`sendInvoice` 🟡, `createInvoiceLink` ❌, `answerShippingQuery` ❌, `answerPreCheckoutQuery` ✅, Stars (XTR), obuna, paid media, refund ❌ → P-bo'lim.

### 2.9 Business
`getBusinessConnection`, `sendMessage(business_connection_id)`, `readBusinessMessage`, `deleteBusinessMessages`, `setBusinessAccountName/Username/Bio/
ProfilePhoto/GiftSettings`, `getBusinessAccountStarBalance`, `transferBusinessAccountStars`, `getBusinessAccountGifts`, `convertGiftToStars`,
`upgradeGift`, `transferGift`, `postStory`, `editStory`, `deleteStory` — ❌ → S-bo'lim.

### 2.10 Fayllar, stikerlar, boshqa
`getFile` ❌ (foydalanuvchi fayllarini qabul qilish) → K30; stiker to'plamlari (`getStickerSet, createNewStickerSet, addStickerToSet, ...`) ❌ → K27;
`getUserProfilePhotos` ❌ → D03; `getCustomEmojiStickers` ❌ → K24; Telegram Passport ⛔; HTML5 Games ⛔ (hozircha).

---

## 3. Imkoniyatlar katalogi

Belgilar: ★ qiymat (1–3), **S** kichik (≤1 kun), **M** o'rta (2–4 kun), **L** katta (≥1 hafta). Har bir imkoniyat 4 qatlamdan o'tadi:
sxema → runner → egasi interfeysi (chat/Mini App) → AI hujjati + test (6-bo'limga qarang).

### K — Kontent (xabar turlari va formatlash) — 40
| ID | Imkoniyat | Bot API | ★ | Hajm |
|---|---|---|---|---|
| K01 | Albom (media guruh): 2–10 rasm/video/hujjat/audio | sendMediaGroup | 3 | M |
| K02 | Joylashuv xabari (+ jonli joylashuv, yo'nalish, yaqinlik ogohlantirishi) | sendLocation | 3 | S |
| K03 | Jonli joylashuvni yangilash (kuryer kuzatuvi) | editMessageLiveLocation, stopMessageLiveLocation | 2 | M |
| K04 | Joy (venue): nom, manzil, xarita | sendVenue | 2 | S |
| K05 | Kontakt kartasi (menejer raqami bir bosishda) | sendContact | 3 | S |
| K06 | So'rovnoma: ommaviy/anonim, ko'p javobli, muddat bilan | sendPoll | 3 | S |
| K07 | Viktorina-so'rovnoma (to'g'ri javob + izoh, Telegram o'zining quiz'i) | sendPoll(type=quiz) | 3 | S |
| K08 | So'rovnomani yopish | stopPoll | 1 | S |
| K09 | Javoblarni yig'ish (kim nima tanladi) | poll_answer | 2 | M |
| K10 | Dice o'yinlari 🎲🎯🏀⚽🎳🎰 + natijaga qarab mukofot | sendDice | 3 | S |
| K11 | "Yozmoqda…" / "rasm yuklanmoqda…" indikatori (AI va uzoq amallarda) | sendChatAction | 2 | S |
| K12 | Bot foydalanuvchi xabariga reaksiya qo'yadi (👍 qabul qildim) | setMessageReaction | 2 | S |
| K13 | Reaksiyalarni qabul qilish (kanal/guruh faolligi, reaksiya bo'yicha oqim) | message_reaction(_count) | 2 | M |
| K14 | Yashirin (spoiler) rasm/video | has_spoiler | 1 | S |
| K15 | Izoh media tepasida | show_caption_above_media | 1 | S |
| K16 | Havola ko'rinishi boshqaruvi (katta rasm, tepada, o'chirish) | link_preview_options | 2 | S |
| K17 | Jim xabar (ovozsiz) | disable_notification | 2 | S |
| K18 | Xabar effektlari 🔥🎉 (shaxsiy chatda) | message_effect_id | 1 | S |
| K19 | Javob sifatida yuborish / iqtibos | reply_parameters | 1 | S |
| K20 | Forward / ko'p nusxalash (forwardMessages, copyMessages) | forwardMessage(s), copyMessages | 2 | S |
| K21 | Xabarni mahkamlash/yechish | pinChatMessage, unpin* | 2 | S |
| K22 | Xabar mediasi/izohini almashtirish | editMessageMedia/Caption | 2 | S |
| K23 | Avto-o'chirish (N daqiqadan keyin), "tozalash" | deleteMessage(s) | 2 | S |
| K24 | Premium emoji (custom emoji) matnda va tugmada | custom_emoji entity, getCustomEmojiStickers | 2 | M |
| K25 | Kengaytiriladigan iqtibos, spoiler, MarkdownV2 qo'llab-quvvatlash, `pre` til, sana-vaqt entity | entities | 1 | S |
| K26 | Pullik media (Stars bilan ochiladigan rasm/video) | sendPaidMedia | 2 | M |
| K27 | Stiker to'plamlari yaratish/boshqarish (brend stikerlari) | createNewStickerSet, addStickerToSet, … | 1 | L |
| K28 | Video: muqova, boshlanish vaqti, o'lcham; audio: ijrochi/nom/muqova | send* parametrlari | 1 | S |
| K29 | Media URL bo'yicha yuborish (yuklamasdan) | file=HTTP URL | 2 | S |
| K30 | Foydalanuvchi yuborgan faylni olish va saqlash (hujjat, rasm, ovoz) | getFile | 3 | M |
| K31 | Kirish turlari kengayishi: hujjat, video, ovoz, stiker, kontakt, so'rovnoma, dice qiymati | message turlari | 3 | M |
| K32 | Ovoz → matn (STT) | getFile + AI | 2 | M |
| K33 | Rasm tahlili (chek, hujjat, mahsulot) | getFile + AI vision | 2 | M |
| K34 | Foydalanuvchi profil rasmi | getUserProfilePhotos | 1 | S |
| K35 | Shablon tili: shartli bloklar, standart qiymat, hisob-kitob, sana arifmetikasi, tasodifiy variant, ko'plik shakli | — | 3 | M |
| K36 | Format yordamchilari: pul, sana, "N kun oldin", qisqartirish | — | 2 | S |
| K37 | Media kutubxonasi: nomlangan fayllar, qayta ishlatish, file_id keshi | — | 2 | M |
| K38 | Slayder/karusel (◀️ ▶️ bilan rasmlar almashinadi) | editMessageMedia | 3 | M |
| K39 | Uzun matn avtomatik bo'laklash (4096/1024) va "Davomi" tugmasi | — | 2 | S |
| K40 | Xabar qoralamalari/shablonlari kutubxonasi (egasi qayta ishlatadi) | — | 1 | S |

### B — Tugmalar va interfeys komponentlari — 24
| ID | Imkoniyat | Bot API | ★ | Hajm |
|---|---|---|---|---|
| B01 | Telegram orqali kirish tugmasi (saytga) | login_url | 2 | S |
| B02 | "Nusxalash" tugmasi (promokod, karta raqami) | copy_text | 3 | S |
| B03 | Ulashish/inline tugmalari: boshqa chatda botni ochish | switch_inline_query* | 3 | S |
| B04 | So'rovnoma yaratish so'rovi | request_poll | 1 | S |
| B05 | Foydalanuvchi/chat tanlash tugmasi (referal, admin tayinlash, guruh ulash) | request_users, request_chat | 2 | M |
| B06 | Majburiy javob (force_reply), kiritish maslahati | force_reply, input_field_placeholder | 2 | S |
| B07 | Bir martalik klaviatura, tanlangan foydalanuvchilarga, doimiy | one_time_keyboard, selective, is_persistent | 2 | S |
| B08 | Tugma rangi va ikonkasi (yangi Bot API imkoniyati — tekshiriladi) | button style/icon | 2 | S |
| B09 | "To'lash" tugmasi invoice ostida | pay | 2 | S |
| B10 | O'yin tugmasi | callback_game | 1 | M |
| B11 | Mini App: inline va reply (startapp parametri bilan) | web_app | 3 | S |
| B12 | tg:// va t.me havolalari (foydalanuvchiga yozish, profil, chat) | url | 2 | S |
| B13 | 64 baytlik callback_data cheklovini yechish (qisqa kod → saqlangan ma'lumot) | callback_data | 3 | M |
| B14 | UI komponentlar: sahifalash, ko'p tanlov (☑️), stepper (➖➕), kalendar, vaqt tanlash, raqam klaviaturasi, baho ⭐, Ha/Yo'q, yorliqlar | — | 3 | L |
| B15 | Tugmalar ro'yxati jadvaldan (dinamik) | — | 3 | M |
| B16 | Ko'rinish shartlari kengayishi: vaqt, hafta kuni, rol, teg, segment, obuna | — | 2 | M |
| B17 | Bosilganda: joyida almashtirish / yangi xabar / alert / jim | answerCallbackQuery | 2 | S |
| B18 | Qayta bosishdan himoya va bir martalik tugma | — | 2 | S |
| B19 | Har tugma statistikasi (bosishlar, o'tish xaritasi) | — | 3 | M |
| B20 | Foydalanuvchiga moslangan klaviatura (rol/holat bo'yicha) | — | 2 | M |
| B21 | Tugma amallari kengayishi: joylashuv yuborish, kontakt yuborish, dice tashlash, so'rovnoma yuborish, hisob-faktura | — | 2 | M |
| B22 | Tugma qatorlari: avtomatik joylashtirish (grid), tenglash, uzun matnni qisqartirish | — | 1 | S |
| B23 | Tugma matnida o'zgaruvchi va emoji almashtirish (holat belgilari) | — | 2 | S |
| B24 | Klaviatura "tarixi": Orqaga stekini murakkab oqimlarda to'g'ri yuritish | — | 2 | M |

### F — Oqim (flow) dvigateli: "istalgan tizim" uchun yelim — 40
Bu bo'lim eng muhim: modullar (do'kon, yozilish...) tayyor yechimlar, **oqim dvigateli** esa tayyor modulda yo'q har qanday mantiqni
kodsiz yig'ish imkonini beradi (trigger → shart → amal). Hamma yangi Bot API imkoniyatlari ham shu dvigatelga trigger/amal sifatida ulanadi.

| ID | Imkoniyat | ★ | Hajm |
|---|---|---|---|
| F01 | **Trigger reyestri**: buyruq, matn (aniq/ichida/regex), tugma, har qanday kirish turi (foto, ovoz, hujjat, joylashuv, kontakt, stiker, so'rovnoma, dice), yangi foydalanuvchi, qaytgan foydalanuvchi, deep-link payload, to'lov, qaytarish, kanalga qo'shilish so'rovi, a'zo o'zgarishi, reaksiya, so'rovnoma javobi, inline so'rov, jadval (cron), kiruvchi webhook, o'zgaruvchi o'zgarishi, buyurtma/yozilish/tiket hodisalari | 3 | L |
| F02 | **Shartlar** (agar/aks holda): o'zgaruvchi, teg, segment, vaqt/hafta kuni, Telegram atributlari (til, premium, username), a'zolik, buyurtmalar soni/summasi, jadval yozuvi | 3 | M |
| F03 | **Amallar reyestri**: istalgan turdagi xabar yuborish/tahrirlash/o'chirish, o'zgaruvchi (qo'yish, qo'shish, hisoblash, tasodifiy), teg, segment, kutish (delay), boshqa oqimga o'tish, tarmoqlanish, takrorlash, A/B bo'lish, HTTP so'rov, AI chaqirish, bildirish, ban, hisob-faktura, buyurtma/yozilish/tiket yaratish, kanalga post, jadvalga yozish | 3 | L |
| F04 | Kutish nuqtasi (input): har qanday xabar turi, tekshiruv, qayta so'rash, muddat, bekor qilish | 3 | M |
| F05 | Foydalanuvchi holati (state machine), pauza/davom, javob bermasa N soatdan keyin eslatma/yopish | 3 | M |
| F06 | Qayta ishlatiladigan bloklar (sub-oqim/funksiya) | 2 | M |
| F07 | Vizual muharrir (Mini App): tugunlar kanvasi; chat-muharrir bilan sinxron | 3 | L |
| F08 | Oqim shablonlari kutubxonasi (≥100): anketa, lead-magnit, onboarding, voronka, kalkulyator, so'rovnoma, test, FAQ, to'lov, qaytarish... | 3 | L |
| F09 | Kalkulyator oqimi (formula): narx/muddat hisoblash | 2 | M |
| F10 | O'zgaruvchi turlari: son, matn, sana, ro'yxat, JSON, mantiqiy; hisoblanadigan; foydalanuvchi/global/suhbat doirasi | 3 | M |
| F11 | Teglar va maxsus maydonlar (CRM asosi) | 3 | M |
| F12 | Segment quruvchi (shartlar kombinatsiyasi, saqlanadigan, dinamik) | 3 | M |
| F13 | Voronka (drip): kechikishli ketma-ket xabarlar, chiqish sharti ("sotib oldi → to'xtat") | 3 | M |
| F14 | Jadval bo'yicha oqim (cron: har dushanba 9:00, oyning 1-kuni) | 2 | S |
| F15 | Kiruvchi webhook: tashqi tizim botga hodisa/xabar yuboradi (`POST /hooks/<kalit>`) | 3 | M |
| F16 | Nosozliklarni topish: oqim jurnali (nima ishladi), qadam-baqadam sinov, sandbox har oqim uchun | 3 | M |
| F17 | Oqimlar versiyasi va qaytarish | 2 | S |
| F18 | Oqim ruxsatlari: faqat admin/operator/segment | 2 | S |
| F19 | Flood himoya: foydalanuvchi N soniyada ko'p so'rasa sekinlatish | 2 | S |
| F20 | Ichki hodisa shinasi: modullar (do'kon, yozilish, tiket) hodisalari oqimga trigger bo'ladi | 3 | M |
| F21 | HTTP amali: GET/POST, sarlavhalar, javobdan o'zgaruvchi olish (JSONPath), xavfsizlik (SSRF) | 3 | M |
| F22 | Matematik/mantiqiy amallar, sana arifmetikasi, matn funksiyalari (kesish, almashtirish, regex) | 2 | M |
| F23 | Ro'yxat amallari: qo'shish, o'chirish, saralash, tasodifiy element, uzunlik | 2 | S |
| F24 | Kutish: "N daqiqadan keyin", "ertaga 9:00 da", "xabarga javob bergunicha" | 3 | M |
| F25 | Qaytib kelgan foydalanuvchi: oxirgi holatdan davom ettirish | 2 | S |
| F26 | Tarmoq: bir vaqtning o'zida bir necha amal (parallel), kutib birlashtirish | 1 | M |
| F27 | Oqim ichida "AI agent" tuguni: shu yerda AI suhbat qilsin (bilimlar bazasi bilan) | 3 | L |
| F28 | Mini App natijasi (sendData) oqimga trigger | 2 | S |
| F29 | Oqimni qo'lda ishga tushirish (egasi tugma bilan, "shu foydalanuvchiga yubor") | 2 | S |
| F30 | Foydalanuvchilar guruhiga ommaviy oqim ishga tushirish | 2 | M |
| F31 | Eksport/import oqimlari — ⛔ (egasi qarori: kerak emas) | — | — |
| F32 | Oqim statistikasi: boshlandi/tugadi/qaysi qadamda tashlab ketildi | 3 | M |
| F33 | Test-rejim: oqimni "sun'iy foydalanuvchi" bilan avtomatik yuritish (regressiya) | 2 | M |
| F34 | Oqim chegaralari: maksimal qadamlar, aylanma (cycle) himoyasi | 2 | S |
| F35 | Oqim izohlari va hujjati (AI tushuntiradi: "bu oqim nima qiladi") | 1 | S |
| F36 | Telegram "typing" va kechikish orqali tabiiy muloqot uslubi | 1 | S |
| F37 | Ommaviy tugma amali: bir bosishda bir necha amal ketma-ket | 3 | S |
| F38 | Oqim o'zgaruvchilarini admin chatda tahrirlash | 1 | S |
| F39 | Modul amallari: "buyurtma yarat", "yozilishni tasdiqla", "tiketni yop" kabi mavjud modullar API'si | 3 | M |
| F40 | Qoidalar jadvali ("agar X bo'lsa Y qil") — oddiy egasi uchun soddalashtirilgan ko'rinish | 3 | M |

### G — Guruh va kanal boshqaruvi — 40
| ID | Imkoniyat | Bot API | ★ | Hajm |
|---|---|---|---|---|
| G01 | **Guruh rejimi**: bot guruh/supergroup/kanalda ishlaydi (chat turi bo'yicha oqimlar, maxfiylik rejimi tekshiruvi) | message, my_chat_member, getMe | 3 | L |
| G02 | Yangi a'zoga salom (rasm/tugma bilan), ketganlarga xabar | chat_member | 3 | S |
| G03 | Kapcha guruhda: yozishni cheklash → tugma bilan tasdiq → muddat o'tsa chiqarish | restrictChatMember, banChatMember | 3 | M |
| G04 | Antispam: havola, forward, @mention, so'z filtri (regex), flood, stiker/media cheklovi, qora ro'yxat | deleteMessage | 3 | L |
| G05 | Ogohlantirish (warn) tizimi: N dan keyin mute/ban | restrictChatMember | 3 | M |
| G06 | Moderator buyruqlari: /ban /mute /kick /unban /del (javob orqali) | ban/restrict/unban | 3 | M |
| G07 | Qoidalar /rules va mahkamlangan xabar | pinChatMessage | 2 | S |
| G08 | Xizmat xabarlarini tozalash ("X qo'shildi") | deleteMessage | 2 | S |
| G09 | Guruh statistikasi (faol a'zolar, xabarlar, o'sish) | getChatMemberCount | 2 | M |
| G10 | XP/daraja tizimi, kunlik/haftalik faollik reytingi | — | 2 | M |
| G11 | Guruhda viktorina/konkurs/so'rovnoma avtomatik | sendPoll | 2 | M |
| G12 | Guruhni sozlash paneli (inline) — egasi guruhning o'zida | — | 3 | M |
| G13 | Kanal: tahrirlash/o'chirish, takroriy post, kontent kalendari, RSS/sayt → kanal | edit*/delete* | 3 | M |
| G14 | Post ostida 👍👎 hisoblagich tugmalar, ovoz berish | callback | 2 | S |
| G15 | Kanal obunachi statistikasi (kunlik o'sish grafigi) | getChatMemberCount | 2 | S |
| G16 | Taklif havolalari: har manba uchun alohida havola, muddat/limit, **qaysi manbadan necha kishi** | createChatInviteLink, editChatInviteLink, revokeChatInviteLink | 3 | M |
| G17 | Kanalga qo'shilish so'rovlarini avtomatik ko'rib chiqish (kapcha/anketa/to'lov) | chat_join_request, approve/declineChatJoinRequest | 3 | M |
| G18 | **Pullik kanal/klub**: to'lov → bir martalik havola → muddat tugasa chiqarish + eslatma; Stars obunasi | createChatSubscriptionInviteLink, banChatMember | 3 | L |
| G19 | Forum mavzulari: har mijoz — alohida mavzu (yordam stoli) | createForumTopic, edit/close/reopen/delete | 3 | M |
| G20 | Operator guruhi: murojaatlar guruhga tushadi, javob guruhdan | forum + copyMessage | 3 | M |
| G21 | Admin tayinlash, maxsus unvon, ruxsatlar | promoteChatMember, setChatAdministratorCustomTitle, setChatPermissions | 2 | M |
| G22 | Guruh nomi/tavsifi/rasmini boshqarish | setChatTitle/Description/Photo | 1 | S |
| G23 | Kanal izohlari (muhokama guruhi) moderatsiyasi | — | 2 | M |
| G24 | Guruhda kalit so'zga avto-javob | — | 2 | S |
| G25 | Majburiy obuna v2: bir nechta kanal, "istalgan biri", real vaqt (chat_member), imtiyozli davr | chat_member | 2 | M |
| G26 | Kanal giveaway natijalarini o'qish | Giveaway, GiveawayWinners | 1 | S |
| G27 | Boost qilganlarga mukofot | chat_boost | 1 | S |
| G28 | Bir post — bir nechta kanalga | copyMessage | 2 | S |
| G29 | Guruhdagi buyruqlar doirasi (faqat adminlarga ko'rinadigan buyruqlar) | setMyCommands(scope) | 2 | S |
| G30 | Guruh "yopiq vaqt" (kechasi yozish taqiqi) | setChatPermissions | 1 | S |
| G31 | Kanalga yuborilgan postga avtomatik izoh/tugma qo'shish | editMessageReplyMarkup | 2 | S |
| G32 | Guruh a'zolari ro'yxatini sinxronlash (admin ro'yxati) | getChatAdministrators | 1 | S |
| G33 | Moderatsiya jurnali (kim kimni nima uchun) | — | 2 | S |
| G34 | Shikoyat tugmasi (report) → adminlarga | — | 2 | S |
| G35 | Guruhda savdo/yozilish bot sifatida (buyurtma guruhda) | — | 1 | M |
| G36 | Telegram "yangiliklar" kanali + muhokama bot (Livegram uslubi) | — | 1 | M |
| G37 | Kuzatuvchi bot: kanaldagi yangi postni boshqa chatga/hisobotga ko'chirish | channel_post | 2 | M |
| G38 | Guruh o'yinlari (so'z topish, matematik misol musobaqasi) | — | 1 | M |
| G39 | Avtomatik "ommaviy qo'shilish" himoyasi (raid mode) | restrict/ban | 2 | M |
| G40 | Guruh/kanalni botga bog'lash ustasi (chatda 3 qadam) | request_chat | 3 | S |

### I — Inline rejim, deep-link va manba kuzatuvi — 16
| ID | Imkoniyat | Bot API | ★ | Hajm |
|---|---|---|---|---|
| I01 | Inline so'rovlarni qabul qilish va natija qaytarish (maqola, rasm, gif, video, hujjat, joy, kontakt, stiker) | inline_query, answerInlineQuery | 3 | L |
| I02 | **Katalogni inline qidirish**: "@bot latte" → mahsulot kartochkasi istalgan chatga (virusli savdo) | answerInlineQuery | 3 | M |
| I03 | Inline FAQ/ma'lumotnoma, xizmat/narx qidiruvi | answerInlineQuery | 2 | M |
| I04 | Tanlangan natijani kuzatish | chosen_inline_result | 1 | S |
| I05 | "Botni ochish" tugmasi inline natija ustida | switch_pm_text | 2 | S |
| I06 | Inline xabarni tahrirlash (inline_message_id) | editMessageText | 1 | S |
| I07 | Deep-link turlari: `?start=`, `?startgroup=`, `?startchannel=`, `?startapp=`, `t.me/bot/app`, `?attach=` | — | 3 | S |
| I08 | **Manba kuzatuvi**: har havola uchun kampaniya kodi (instagram, reklama), qayerdan kelganlar statistikasi, konversiya | — | 3 | M |
| I09 | QR-kod yaratish (bot, mahsulot, promokod havolasi) | — | 2 | S |
| I10 | Referal chuqurligi (2 daraja), referal bo'yicha reyting va mukofot qoidalari | — | 2 | M |
| I11 | Payload orqali ma'lumot uzatish (promokod, mahsulot, tadbir) | start parametri | 3 | S |
| I12 | Ulashish tugmasi: tayyor matn + havola, "do'stga yubor" | switch_inline_query | 2 | S |
| I13 | Tayyor inline xabar (Mini App ulashishi uchun) | savePreparedInlineMessage | 1 | S |
| I14 | Inline rejim sozlamalari: placeholder, geolokatsiya so'rash | setInlineQueryPlaceholder (BotFather) / inline_location | 1 | S |
| I15 | Inline natijalar keshi va sahifalash (next_offset) | answerInlineQuery | 2 | S |
| I16 | Inline orqali Mini App natijasini yuborish | answerWebAppQuery | 1 | S |

### P — To'lov v2, savdo va monetizatsiya — 24
| ID | Imkoniyat | Bot API | ★ | Hajm |
|---|---|---|---|---|
| P01 | **Telegram Stars (XTR)** bilan to'lov: provayder tokensiz, raqamli tovarlar | sendInvoice(currency=XTR) | 3 | M |
| P02 | Stars obunasi (30 kunlik avto-to'lov) | createInvoiceLink(subscription_period) | 3 | M |
| P03 | Hisob-faktura havolasi: kanal/sayt/Mini App'da to'lash | createInvoiceLink | 3 | S |
| P04 | Yetkazish usullari va narxi (manzilga qarab) | shipping_query, answerShippingQuery | 2 | M |
| P05 | Invoice ichida ism/telefon/email/manzil yig'ish | need_*, send_*_to_provider | 2 | S |
| P06 | Choychaqa (tip) | max_tip_amount, suggested_tip_amounts | 1 | S |
| P07 | Fiskal chek (provider_data): soliq/OFD integratsiyasi | provider_data | 2 | M |
| P08 | Invoice rasmi va tavsifi | photo_url/size | 1 | S |
| P09 | Stars hisobi va qaytarish: tranzaksiyalar, refund, balans | getStarTransactions, refundStarPayment, getMyStarBalance | 2 | M |
| P10 | **Raqamli tovar yetkazish**: to'lovdan keyin fayl/kod/havola (kodlar ombori: litsenziya, promokod, akkaunt) | — | 3 | M |
| P11 | Ichki hamyon/balans: to'ldirish, balansdan to'lash, ballni pulga almashtirish | — | 2 | L |
| P12 | Yozilishga oldindan to'lov (depozit) va bekor qilish siyosati | invoice | 3 | M |
| P13 | To'lanmagan buyurtma: muddat, avto-bekor, eslatma | — | 3 | S |
| P14 | To'lov hodisalari oqimga trigger (muvaffaqiyatli, qaytarilgan) | successful_payment, refunded_payment | 2 | S |
| P15 | Sovg'a sertifikatlari: sotish, kod, ishlatish | — | 2 | M |
| P16 | Chegirma qoidalari: birinchi buyurtma, summa bo'yicha, kategoriya, vaqt (happy hour), "N+1", pog'onali | — | 3 | M |
| P17 | Mahsulot variantlari (o'lcham/rang), qo'shimchalar (sous, porsiya), SKU, variant bo'yicha ombor | — | 3 | L |
| P18 | Katalog qidiruvi, filtr, saralash, sevimlilar, ko'rilganlar | — | 3 | M |
| P19 | Buyurtma jarayoni: kuryer tayinlash, jonli kuzatuv, baho, "takrorlash", chek (rasm/PDF) | K03 | 3 | L |
| P20 | Filiallar va yetkazish zonalari (joylashuv → zona/narx), ish vaqti | — | 3 | L |
| P21 | Egasiga kunlik/haftalik savdo hisoboti, eng ko'p sotilganlar | — | 2 | S |
| P22 | Pullik media savdosi, sotib olinganlarni kuzatish | sendPaidMedia, purchased_paid_media | 2 | M |
| P23 | Telegram sovg'alari (gift) yuborish/qabul qilish | sendGift, getAvailableGifts | 1 | M |
| P24 | O'zbekiston to'lov tizimlari (Click/Payme) bilan to'g'ridan-to'g'ri ulanish (invoice havolasi) | — | 3 | L |

### S — Telegram Business chatbot — 12
Egasi o'z **shaxsiy Telegram akkauntini** (Business → Chatbots) botga ulaydi: bot uning nomidan mijozlarga javob beradi.
| ID | Imkoniyat | Bot API | ★ | Hajm |
|---|---|---|---|---|
| S01 | Biznes ulanishini qabul qilish va saqlash | business_connection | 3 | M |
| S02 | Biznes chatlarda avto-javob: FAQ, ish vaqtidan tashqari, AI | business_message, sendMessage(business_connection_id) | 3 | L |
| S03 | O'qildi belgisi, xabarni o'chirish | readBusinessMessage, deleteBusinessMessages | 2 | S |
| S04 | Odamga uzatish (handoff): egasi yozsa bot jim, qayta yoqish | — | 3 | M |
| S05 | Tahrirlangan/o'chirilgan xabarlar monitoringi | edited_business_message, deleted_business_messages | 1 | S |
| S06 | Biznes akkaunt profilini boshqarish (ism, bio, rasm) — "Avto bio" bilan birlashish | setBusinessAccount* | 2 | M |
| S07 | Story'larni rejalashtirish/joylash | postStory, editStory, deleteStory | 2 | M |
| S08 | Biznes chatni CRM/tiketga aylantirish | — | 3 | M |
| S09 | Mijoz kartochkasi biznes chatdan (tarix, teglar) | — | 2 | M |
| S10 | Biznes akkaunt Stars balansi va sovg'alari | getBusinessAccountStarBalance, getBusinessAccountGifts | 1 | M |
| S11 | Salomlashish/ketish xabarlari (Business sozlamalari bilan uyg'un) | — | 2 | S |
| S12 | Biznes chat uchun yozilish/buyurtma oqimlari (modullar biznes chatda ishlaydi) | — | 3 | L |

### M — Bot profili va sozlamalari — 14
| ID | Imkoniyat | Bot API | ★ | Hajm |
|---|---|---|---|---|
| M01 | Bot nomini chatdan o'zgartirish (BotFather'siz) | setMyName | 2 | S |
| M02 | Tavsif (bo'sh chatda) va qisqa tavsif (profil) | setMyDescription, setMyShortDescription | 2 | S |
| M03 | Bot profil rasmi | setMyProfilePhoto | 1 | S |
| M04 | Buyruqlar doirasi va tillar (admin/operator/guruh uchun alohida menyu) | setMyCommands(scope, language_code) | 3 | M |
| M05 | Menyu tugmasi har chat uchun (buyruqlar / Mini App) | setChatMenuButton | 2 | S |
| M06 | Guruhga qo'shilganda so'raladigan admin huquqlari | setMyDefaultAdministratorRights | 1 | S |
| M07 | Bot imkoniyatlari tekshiruvi (inline, guruh, maxfiylik rejimi, asosiy Mini App) | getMe | 2 | S |
| M08 | Botni BotFather'siz yaratish (agar Bot API "managed bots" imkoniyatini bersa — tekshiriladi) | — | 3 | M |
| M09 | Webhook holati ko'rsatish | getWebhookInfo | 1 | S |
| M10 | "Botni sozlash ustasi"ni kengaytirish (profil, tavsif, buyruqlar, rasm) | — | 3 | M |
| M11 | Bot "o'zi haqida" sahifasi: ommaviy profil, havola kartasi, QR | — | 1 | S |
| M12 | Egasini/rollarni almashtirish | — | 2 | S |
| M13 | Token almashganda avtomatik tiklash ko'rsatmasi | — | 2 | S |
| M14 | Asosiy Mini App (profildagi "Ilovani ochish") bog'lash | getMe.has_main_web_app | 2 | S |

### O — Masshtab, tezlik va ishonchlilik — 20
| ID | Imkoniyat | ★ | Hajm |
|---|---|---|---|
| O01 | **Webhook rejimi** (setWebhook, secret_token, allowed_updates) — long polling o'rniga/yonida | 3 | L |
| O02 | Update navbati (Redis Streams) + ishchilar puli; har chat ichida tartib saqlanadi | 3 | L |
| O03 | Global va chat bo'yicha tezlik cheklovchi (30/s, 1/s chat, 20/daq guruh), 429 `retry_after` hamma joyda | 3 | M |
| O04 | **Tarqatish v2**: har kimga shaxsiylashtirish ({name}), parallel, to'xtatish/davom, A/B, havola bosishlari, `allow_paid_broadcast` | 3 | L |
| O05 | Update takrorlanishidan himoya (update_id) | 2 | S |
| O06 | Katta fayllar (lokal Bot API server, 2 GB), file_id keshi | 1 | L |
| O07 | Ko'rsatkichlar (Prometheus): kechikish, xato, metod bo'yicha; ogohlantirish | 3 | M |
| O08 | Tarif bo'yicha limitlar: xabar/oy, tarqatish hajmi, AI so'rovlar — va panelda hisoblagich | 3 | M |
| O09 | Menyu/oqim zaxira nusxalari va tiklash (davr bo'yicha) | 2 | S |
| O10 | **Botlarni runnerlarga bo'lish (sharding)**: hozir bitta lider hamma botni yuritadi → barqaror hash bilan bir nechta runner | 3 | L |
| O11 | Yangilashda update yo'qotmasdan qayta ishga tushish (offset saqlash) | 3 | S |
| O12 | Egasi uchun "bot salomatligi": oxirgi update, xatolar, webhook holati | 2 | S |
| O13 | Eskirgan loglar/redis kalitlarini tozalash vazifalari | 2 | S |
| O14 | **API qamrov matritsasi (avto)**: rasmiy Bot API sxemasidan metod/turlar ro'yxatini olib, reyestr bilan solishtiradigan vosita; yangi Bot API chiqqanda CI "nima qo'shilmagan" ro'yxatini beradi | 3 | M |
| O15 | Katta ro'yxatlar uchun indekslar va so'rov optimizatsiyasi (obunachilar, buyurtmalar) | 2 | M |
| O16 | Ma'lumotlar bazasi: partitsiyalash (log, statistika) | 1 | M |
| O17 | Redis → muhim holatni bazaga (cart, state) tiklanish uchun | 2 | M |
| O18 | Runner nosozligida avtomatik qayta tiklash va ogohlantirish | 3 | S |
| O19 | Yuklama sinovi (10k foydalanuvchi, 100 bot) va natijalar hisoboti | 2 | M |
| O20 | Maxsus domen/proksi (Telegram bloklangan hududlar uchun yo'naltirish) | 1 | M |

### D — Ma'lumotlar, CRM, AI va analitika — 30
| ID | Imkoniyat | ★ | Hajm |
|---|---|---|---|
| D01 | **Bot jadvallari** (Web App'dagi kabi): egasi chatda/Mini App'da jadval yaratadi (mahsulot, mijoz, tadbir, vakansiya), CRUD, qidiruv, CSV | 3 | L |
| D02 | Dinamik ro'yxat bo'limi (sahifalash, filtr, kartochka) — har qanday jadvaldan | 3 | M |
| D03 | Foydalanuvchi kartochkasi: tarix (buyurtma, yozilish, murojaat), teglar, izohlar, qo'lda xabar | 3 | M |
| D04 | **Mini-CRM**: lidlar voronkasi (yangi → aloqa → kelishuv → yopildi), mas'ul, eslatma, kanban (Mini App) | 3 | L |
| D05 | Saqlangan segmentlar bo'yicha tarqatish va oqimlar | 3 | S |
| D06 | Jonli suhbat (operator foydalanuvchi bilan to'g'ridan-to'g'ri, bot jim) | 3 | M |
| D07 | **AI yordamchi (RAG)**: egasi matn/PDF/sayt yuklaydi → bot shundan javob beradi, bilmasa operatorga uzatadi; kvota | 3 | L |
| D08 | AI qoralama: operatorga javob taklifi; post yozish; tavsif yaratish | 2 | M |
| D09 | AI ma'no bo'yicha yo'naltirish (kalit so'z o'rniga) | 3 | M |
| D10 | AI buyurtma qabul qilish ("ikki latte va tort" → savat) | 3 | M |
| D11 | Ovoz → matn, rasm tahlili (K32–K33) | 2 | M |
| D12 | Analitika v2: DAU/WAU/MAU, kogortalar, ushlab qolish, manbalar, voronkalar, issiq soatlar, LTV, daromad grafigi (Mini App dashboard) | 3 | L |
| D13 | A/B test: xabar/tugma variantlari + statistik ishonchlilik | 2 | M |
| D14 | Anketa/so'rovnoma natijalari (diagramma), NPS/CSAT avtomatik so'rov | 2 | M |
| D15 | Hisobotlar: kunlik/haftalik avtomatik egasiga, Excel/JSON eksport | 2 | S |
| D16 | Foydalanuvchi ma'lumotini o'chirish (/deletemydata), rozilik (consent), maxfiylik sahifasi | 3 | S |
| D17 | Tayyor integratsiyalar: amoCRM, Bitrix24, Notion, Airtable, Trello, Slack, e-pochta (SMTP) — webhook asosida | 3 | M |
| D18 | SMS (Eskiz.uz, Playmobile) va e-pochta bildirishnomalari | 2 | M |
| D19 | Telefon tasdiqlash (OTP) | 2 | M |
| D20 | Kalendar: .ics fayl yuborish, Google Calendar sinxronlash (yozilishlar) | 2 | M |
| D21 | Xarita: manzil → masofa/yetkazish narxi, eng yaqin filial (geokodlash) | 3 | M |
| D22 | Tashqi ma'lumot bloklari: valyuta kursi (CBU), ob-havo, namoz vaqtlari, kripto narx | 2 | S |
| D23 | Hujjat generatsiyasi: sertifikat/diplom/chek (ism bilan rasm/PDF), QR/shtrix-kod | 2 | M |
| D24 | Foydalanuvchi yuborgan fayllar ombori (CV, hujjat) egasi ko'radi/yuklaydi | 2 | M |
| D25 | Tarixiy xabarlar qidiruvi (egasi uchun) | 1 | M |
| D26 | Foydalanuvchi faolligi "issiq" ball (lead scoring) | 2 | M |
| D27 | Kunlik "kun gapi/maslahat" kontent generatori (AI + jadval) | 1 | S |
| D28 | Mijozlarga avtomatik tug'ilgan kun/yubiley xabarlari (sana maydoni) | 2 | S |
| D29 | Takroriy (qaytuvchi) mijozlarni aniqlash va mukofotlash | 2 | S |
| D30 | Bir nechta bot uchun umumiy hisobot (agentlik rejimi) | 2 | L |

### W — Mini App bilan chuqur bog'lanish — 10
| ID | Imkoniyat | Bot API / WebApp | ★ | Hajm |
|---|---|---|---|---|
| W01 | `sendData` → botga ma'lumot → oqim/jadvalga yozish | web_app_data | 3 | M |
| W02 | Inline orqali ochilgan ilova natijasini chatga yuborish | answerWebAppQuery | 2 | S |
| W03 | Ilova ichidan to'lash (invoice havolasi, Stars) | createInvoiceLink, openInvoice | 3 | M |
| W04 | `startapp` parametri va to'g'ridan-to'g'ri havola (t.me/bot/app) | — | 3 | S |
| W05 | Bot jadvallari va Web App ma'lumotlar bazasi — yagona manba | — | 3 | L |
| W06 | Web App buyurtmalari = bot buyurtmalari (bitta modul, bitta panel) | — | 3 | M |
| W07 | Ilova blokleri: MainButton, BackButton, haptic, shareToStory, requestContact, joylashuv, QR-skaner, fullscreen, "bosh ekranga qo'shish", bulutli saqlash | WebApp API | 2 | L |
| W08 | Mavzu/rang sinxronlash va xavfsiz hudud | WebApp API | 2 | S |
| W09 | Web App uchun sifat to'plami (AI ilovalar baholash) | — | 2 | M |
| W10 | Bot ↔ ilova umumiy foydalanuvchi profili (ballar, teglar) | — | 3 | M |

### A — Xavfsizlik, rollar va moderatsiya — 12
| ID | Imkoniyat | ★ | Hajm |
|---|---|---|---|
| A01 | Rollar matritsasi: egasi, admin, menejer, operator, kontent muharriri, moliya (ko'rish) — har modul uchun ko'rish/tahrirlash | 3 | L |
| A02 | Audit jurnali: kim nimani o'zgartirdi (menyu, to'lov, token, webhook) | 3 | M |
| A03 | Xavfli amallarga ikki bosqichli tasdiq (token, ommaviy xabar >1000, o'chirish) | 2 | S |
| A04 | Global spam/ban ro'yxatlari, shikoyat tugmasi | 2 | M |
| A05 | Platforma moderatsiyasi: taqiqlangan kontent (firibgarlik, 18+, spam) — AI/regex tekshiruv, botni to'xtatish | 3 | L |
| A06 | Sirlar ombori: provayder tokeni, tashqi API kalitlari, webhook sirlari (umumlashtirish) | 3 | M |
| A07 | HTTP amallari himoyasi (SSRF, vaqt chegarasi, hajm chegarasi) — F21 uchun | 3 | S |
| A08 | Ma'lumotni saqlash muddati va o'chirish siyosati | 2 | S |
| A09 | Fishing/qora ro'yxatdagi havolalar filtri | 2 | S |
| A10 | Token bekor qilinishini aniqlash va egasini ogohlantirish (qisman bor) | 2 | S |
| A11 | Faol sessiyalar/qurilmalar (Mini App) va chiqarib yuborish | 1 | M |
| A12 | Xavfsizlik testlari (ruxsatsiz callback, IDOR, injection) avtomatik | 3 | M |

**Jami: 282 ta batafsil imkoniyat** (K40 + B24 + F40 + G40 + I16 + P24 + S12 + M14 + O20 + D30 + W10 + A12). Yangi Bot API versiyalari chiqqach
O14 vositasi qoplanmagan metodlar ro'yxatini beradi va katalog shu ro'yxat bilan to'ldiriladi.

---

## 4. Arxitektura qarori: "imkoniyat reyestri" (ming-minglab imkoniyat uchun)

Imkoniyatlarni bittalab qo'lda (sxema + runner + interfeys + AI hujjati + test) yozish tez to'xtaydi. Yechim — **ma'lumotga asoslangan reyestr**:

```
core/capabilities/
  registry.py      # @capability(id="send_poll", kind="action", schema=SendPoll, bot_api=["sendPoll"], …)
  actions/…        # har amal: pydantic sxema + handler(runner, ctx, params)
  triggers/…       # har trigger: update filtri + parametr sxemasi
  content/…        # xabar turlari (media guruh, joylashuv, so'rovnoma…)
```
Reyestr bitta joydan **avtomatik** hosil qiladi:
1. **Tekshiruv** — sxema bo'yicha menyu hujjatini validatsiya (`validate_menu` kengayadi).
2. **Runner** — update → trigger moslash → shart → amallar zanjiri (F-dvigatel); har amal bir xil tezlik cheklovchi, jurnal, sinov rejimidan o'tadi.
3. **Egasi interfeysi** — chatdagi muharrir sxemadan forma yasaydi (maydon turlari: matn, son, tanlov, sahifa, o'zgaruvchi, vaqt, jadval...), Mini App'da ham shu sxema.
4. **AI hujjati** — AI uchun prompt reyestrdan generatsiya qilinadi (`BOT_SYSTEM` qo'lda yozilmaydi): yangi imkoniyat qo'shilishi bilan AI uni avtomatik biladi.
5. **Qamrov matritsasi** (O14) — `bot_api=[…]` maydonlaridan "qaysi Bot API metodi/turi qoplangan" hisoboti; CI'da yangi Bot API versiyasi chiqsa, qoplanmaganlar ro'yxati chiqadi.
6. **Sifat to'plami** — har imkoniyat uchun kamida 1 brif + 1 simulyatsiya testi (shablon testlar sxemadan generatsiya).

Mavjud modullar (do'kon, yozilish, o'yinlar, tiketlar...) o'chirilmaydi: ular reyestrga "kompozit imkoniyat" sifatida ulanadi
(ularning hodisalari — F20 — oqim triggerlari bo'ladi, amallari — F39 — oqim amallari bo'ladi). Shunda egasi tayyor modulni ham, uni
kengaytiradigan o'z mantiqini ham bir muhitda qo'shadi.

Oddiy foydalanuvchi uchun interfeys qoidasi o'zgarmaydi: **uch daraja** — tayyor tizim (30 soniya) → AI (60 soniya) → qo'lda sozlash;
oqim dvigateli "murakkab" qatlamda turadi, oddiy egasiga F40 ("agar X bo'lsa Y qil") ko'rinishida soddalashtirib ko'rsatiladi.

---

## 5. Bajarish tartibi

**Holat:** 1-bosqich (poydevor) boshlandi — Sprint 1 bajarildi: imkoniyat reyestri (`core/capabilities.py`), oqim dvigateli (`apps/botrunner/flows.py`,
F01–F05, F10 qisman, F16 qisman, F37), O14 qamrov matritsasi (`tools/api_coverage.py` → `docs/api-coverage.md`), K02 K05 K06 K07 K10 K11 K12 K31(qisman) B02.
Qamrov: metodlar 21% → (hozirgi raqam `docs/api-coverage.md` da).

Har bosqich oxirida: sifat to'plami + regressiya + hujjat + deploy ko'rsatmasi. Bog'liqliklar bo'yicha:

| Bosqich | Mazmuni | Nima uchun shu tartibda |
|---|---|---|
| **1. Poydevor** | O14 (qamrov matritsasi), imkoniyat reyestri, F01–F05, F10, F16, F20, F39 (oqim dvigateli yadrosi), O05, O11 | Qolgan hamma narsa shu ustiga quriladi; qamrov matritsasi "nima qolib ketdi"ni doim ko'rsatadi |
| **2. Kontent va tugmalar** | K01–K25, K28–K31, K35–K39, B01–B24 | Eng ko'p ta'sir, kam xavf; hammasi oqim amali/kontent turi sifatida |
| **3. Ma'lumot va CRM** | D01–D05, F11–F15, F21–F24, A07 | Jadval + teg + segment + HTTP — "istalgan tizim" uchun asosiy ingredient |
| **4. Guruh va kanal** | G01–G12, G16–G22, G25, G40, M04 | Telegram botlarning katta qismi (moderator, klub, kanal) — hozir butunlay yo'q |
| **5. To'lov v2 va savdo** | P01–P05, P10, P12–P14, P16–P18, G18, W03 | Monetizatsiya: Stars, obuna, raqamli tovar, depozit |
| **6. Inline va o'sish** | I01–I12, B03, K20, D17–D18 | Virusli savdo va manba kuzatuvi |
| **7. Business chatbot** | S01–S12, M01–M10 | Yangi yo'nalish: shaxsiy akkaunt uchun avto-javob |
| **8. Masshtab** | O01–O04, O07–O10, O12, O15–O19 | 1000+ bot/million foydalanuvchi uchun |
| **9. AI v2** | D06–D11, F27, K32–K33, D12–D14 | RAG, buyurtma qabul qilish, analitika |
| **10. Mini App va xavfsizlik** | W01–W10, A01–A12, D16, D19–D30 | Chuqur bog'lanish, rollar, audit, moderatsiya |

Birinchi sprint tavsiyasi (≈ 2 hafta): **O14 + reyestr + oqim yadrosi (F01–F05) + 5 ta eng sodda imkoniyat** (K02 joylashuv, K06 so'rovnoma,
K10 dice, B02 nusxalash, K11 typing) — reyestr haqiqatan "bitta sxema → hamma qatlam" ishlashini isbotlaydi.

---

## 6. Har bir imkoniyat uchun "tayyor" mezoni (Definition of Done)

1. **Sxema**: pydantic modeli, chegaralar Telegram limitlariga mos (4096/1024 belgi, 64 bayt callback, 8 tugma/qator, 100 tugma, 10 media, 30 xabar/s…).
2. **Runner**: handler + xato tarmoqlari (403 bloklangan, 400 noto'g'ri, 429 `retry_after`), sinov rejimida ishlaydi (sandbox: yon ta'sirsiz).
3. **Egasi interfeysi**: chat-muharrirda qo'shish/o'zgartirish/o'chirish; "bu nima?" izohi; xato matni — nima qilish kerakligini aytadi.
4. **AI**: reyestrdan avtomatik prompt; AI shu imkoniyatni to'g'ri ishlata oladi (kamida 1 brif sifat to'plamida).
5. **Test**: simulyatsiya (mijoz + egasi oqimi), xavfsizlik tekshiruvi (ruxsatsiz foydalanish), regressiya.
6. **Hujjat**: README bandi + imkoniyat reyestrida `bot_api` bog'lanishi (qamrov matritsasi yangilanadi).
7. **Statistika**: kamida bitta hodisa hisoblagichi (foydalanilyaptimi?).

## 7. Telegram cheklovlari (hamma qatlamda hisobga olinadi)

Bir chatga ≈ 1 xabar/s, guruhga ≈ 20 xabar/daq, botga umumiy ≈ 30 xabar/s (pullik tarqatish bilan ≈ 1000/s); matn 4096, izoh 1024;
inline tugma callback_data 64 bayt; qatorda 8, jami 100 tugma; media guruh 2–10; fayl yuborish 50 MB (lokal serverda 2 GB), yuklab olish 20 MB;
so'rovnoma 2–10 variant; buyruq nomi 32 belgi, 100 buyruq; inline natija 50 ta; foydalanuvchi botni bloklasa — xabar yuborib bo'lmaydi (403);
guruhda maxfiylik rejimi (privacy mode) botning ko'ra oladigan xabarlarini cheklaydi; Bot API versiyasi tez o'zgaradi — yangi imkoniyatlar
(O14 vositasi) har oy tekshiriladi.
