# Bot konstruktori: «dasturchidan tez va sifatli» tizim — to'liq reja

## Maqsad

Har qanday vaziyat uchun botni (do'kon, restoran, yozilish, o'quv markazi, konkurs, qo'llab-quvvatlash, kanal,
so'rovnoma, ko'chmas mulk...) istalgan uslubda (⌨️ klaviatura, 💬 inline, 🔀 aralash) bir necha daqiqada tuzish.
Natija tajribali dasturchi qilganidan **tezroq va sifatliroq** bo'lsin. **Sifat birinchi o'rinda.**

## Nima uchun hozirgi AI natijasi yomon (tashxis)

| # | Muammo | Oqibati |
|---|---|---|
| 1 | AI bitta so'rovda butun botni katta JSON qilib yozadi, kuchsiz model (gpt-4o-mini) bilan | sayoz, shablon, mazmunsiz natija |
| 2 | Ko'rsatmada «narxlar `... so'm`» deb joy qoldirish so'ralgan edi | matnlar ma'nosiz |
| 3 | AI past darajadagi «g'isht»lar (sahifa, tugma) bilan ishlaydi; UX qoidalari kafolatlanmagan | chalkash navigatsiya, «ishlatish tushunarsiz» |
| 4 | Biznes haqida hech narsa so'ralmaydi | AI taxmin qiladi |
| 5 | Natijani qo'llashdan oldin sinab ko'rib bo'lmaydi | yomon natija darhol foydalanuvchiga chiqadi |
| 6 | Dvigatelda real stsenariylar yo'q: savatcha/buyurtma, yozilish, test, reyting, avtomatik xabarlar | AI xohlasa ham murakkab bot qura olmaydi |

## Arxitektura: dasturchi kabi ishlaydigan 5 qatlam

1. **Dvigatel** — bot nimalarni qila oladi (tugmalar, postlar, o'zgaruvchilar, formalar, savatcha, yozilish, test...).
2. **Modullar kutubxonasi** — sinovdan o'tgan tayyor stsenariylar (dasturchi yozgandek), parametrlar bilan:
   «katalog + savatcha + buyurtma», «yozilish», «test», «referal konkurs», «FAQ», «kontaktlar», «profil»...
   AI ularni noldan o'ylab topmaydi — tanlaydi va mazmun bilan to'ldiradi. **UX sifati kod bilan kafolatlanadi.**
3. **AI quruvchi (konveyer)** — bitta katta so'rov o'rniga bosqichma-bosqich, xuddi dasturchi kabi:
   brif → aniqlashtiruvchi savollar → arxitektura rejasi → har bo'lim uchun mazmun → yig'ish (kod) →
   sifat tekshiruvi va avtomatik tuzatish (linter) → **sinov rejimi** → qo'llash. O'zgartirishlar — nuqtali (faqat so'ralgan qism).
4. **Egasi uchun qulaylik** — usta (wizard: biznes turi → 4-5 savol → tayyor bot), sinov rejimi, vizual xarita,
   🎛/📝 muharrirlar, 🤖 suhbat.
5. **Sifat nazorati** — 40 ta turli brif bo'yicha avtomatik baholash; har bir o'zgarishda natija yomonlashmasin.

## Modullar (stsenariylar)

| Modul | Nima qiladi | Holat |
|---|---|---|
| 📂 Menyu va bo'limlar | istalgan chuqurlik, klaviatura/inline/aralash | ✅ bor |
| 📝 Postlar | istalgan media, formatlash, inline tugmalar | ✅ bor |
| 📋 Forma / ariza | ketma-ket savollar, javob egasiga, CSV | ✅ bor |
| ❓ Savol posti | javob o'zgaruvchiga saqlanadi | ✅ bor |
| 🔢 O'zgaruvchilar, shartlar | ball, profil, shartli tugmalar | ✅ bor |
| 👥 Referal, 📢 majburiy obuna, 🔑 kalit so'zlar, 💬 qayta aloqa | | ✅ bor |
| 🛒 **Katalog + savatcha + buyurtma** | mahsulot kartalari (rasm, narx), miqdor ➖➕, savatcha, rasmiylashtirish, buyurtma raqami, holatlar (qabul qilindi → yo'lda → yetkazildi), mijozga xabar | 🆕 2-bosqich |
| 🗂 **Dinamik ro'yxatlar** | mahsulot/xizmatlar bazada; egasi chatda «➕ mahsulot» bilan qo'shadi, AI emas | 🆕 2-bosqich |
| 📅 **Yozilish** | xizmat → usta → kun → bo'sh vaqt → tasdiq; admin tasdiqlaydi; eslatma | 🆕 3-bosqich |
| ⏰ **Avtomatik xabarlar** | xush kelibsiz seriyasi, eslatmalar, rejalashtirilgan postlar | 🆕 3-bosqich |
| 🧠 **Test / viktorina** | to'g'ri javob, ball, natija, qayta urinish | 🆕 4-bosqich |
| 🏆 **Reyting** | top takliflar / ballar | 🆕 4-bosqich |
| 🎁 **Kunlik bonus, cooldown, kapcha** | | 🆕 4-bosqich |
| 🧾 **Murojaat holatlari** | tiket raqami, holat, javob | 🆕 4-bosqich |
| 🌐 **Ko'p til** | foydalanuvchi tilni tanlaydi, matnlar tarjima | 🆕 5-bosqich |
| 💳 **To'lov** | Click / Payme / Telegram Stars | 🆕 6-bosqich |

## Bosqichlar

Belgilar: ✅ tayyor · 🔜 keyingi · ⏳ reja.

1. ✅ **AI quruvchi v2** — konveyer (reja → mazmun → yig'ish → linter), aniqlashtiruvchi savollar,
   alohida kuchli «quruvchi modeli», joy tutuvchilarsiz aniq mazmun, **🧪 sinov rejimi**, sifat hisoboti.
2. ✅ **Do'kon moduli** — bo'lim moduli `catalog` (ro'yxat yoki kartalar, sahifalash), `cart`, `orders`;
   mahsulot kartasi ➖/➕, savatcha (yetkazish narxi, «N dan bepul», minimal summa), rasmiylashtirish
   (sozlanadigan maydonlar: ism, telefon, manzil/joylashuv...), har bot uchun #1, #2... raqamli buyurtmalar,
   egasiga holat tugmalari (✅ qabul · 🚚 yo'lda · ✔️ yetkazildi · ❌ bekor), mijozga holat xabari,
   «📦 Buyurtmalarim», `{cart_count}` `{cart_total}`. Egasi chatda: /admin → 🛒 Do'kon — kategoriyalar,
   rasm + izoh bilan mahsulot qo'shish («Latte / 28000 / tavsif»), tahrirlash, yashirish, buyurtmalar, sozlamalar.
   **AI** sotuvchi bizneslar uchun avtomatik do'kon quradi (kategoriyalar + 4–12 real mahsulot + sozlamalar),
   tahrirlashda egasining mahsulotlari va rasmlari saqlanadi; sinov rejimida buyurtma saqlanmaydi.
3. ✅ **Web App AI v2 — butun tizimlar** — bo'sh ilova uchun: reja (sahifalar, navigatsiya, dizayn, ma'lumotlar
   to'plamlari) → har sahifa bloklari parallel → tekshiruv. AI to'plamlar yaratadi (maydonlar + 6–20 boshlang'ich
   yozuv), ro'yxat bloklarini ularga bog'laydi, batafsil sahifalar (`{{maydon}}`), formalarni to'plamga yozadi
   («Mening arizalarim» — `read: own`). «Qo'llash» to'plamlarni yaratadi va ilovani yangilaydi.
4. 🔜 **Yozilish (booking) moduli** — xizmatlar × mutaxassislar × ish jadvali → bo'sh vaqtlar (inline kalendar),
   band qilish, egasiga tasdiqlash, mijozga eslatma (24 soat va 1 soat oldin), bekor qilish/ko'chirish,
   «Mening yozilishlarim». AI: salon, klinika, avtoservis, repetitor uchun avtomatik.
5. ⏳ **Avtomatik xabarlar va voronkalar** — /start dan keyin N soatda, foydalanuvchi harakatsiz bo'lsa,
   tashlab ketilgan savatcha eslatmasi, tug'ilgan kun, segmentlar (o'zgaruvchi sharti bo'yicha) uchun tarqatish,
   rejalashtirilgan postlar. Worker + scheduler orqali.
6. ⏳ **O'yin va jalb qilish modullari** — test/viktorina (ball, natija sahifasi), reyting (TOP-10 `{ball}` bo'yicha),
   kunlik bonus, konkurs (tasodifiy g'olib), kapcha (bot himoyasi), promokodlar.
7. ⏳ **Murojaatlar (tiketlar)** — raqamli murojaat, holatlar, operatorlar (bir nechta admin), shablon javoblar,
   murojaat tarixi.
8. ⏳ **To'lovlar** — Telegram Payments (Click/Payme provayder tokeni), do'kon va yozilish uchun oldindan to'lov,
   to'lov holati buyurtmada; obuna (pullik kanal/klub) — muddat tugashi bilan avtomatik chiqarish.
9. ⏳ **Ko'p til va usta (wizard)** — foydalanuvchi tilni tanlaydi, AI barcha matnlarni tarjima qiladi;
   egasi uchun 5 savolli usta va vizual xarita (Mini App).
10. ⏳ **Analitika** — bo'limlar bo'yicha bosishlar, voronka (start → katalog → savat → buyurtma), konversiya,
    eng ko'p sotilganlar; AI tavsiyalari («savatcha tashlab ketilmoqda — eslatma yoqing»).
11. ⏳ **Sifat to'plami** — 40 ta turli brif (do'kon, restoran, klinika, kurs, kanal, o'yin...), avtomatik
    baholash (linter + LLM-hakam), har o'zgarishda regressiya, natijalar asosida promptlarni yaxshilash.

## Sifat mezonlari (har bir yaratilgan bot uchun)

- Har bir bo'limga yetib borish mumkin, har joydan orqaga yo'l bor, «boshi berk» joy yo'q.
- Matnlar aniq biznesga xos, `...`, `[ ]`, «lorem» kabi joy tutuvchilar yo'q; noma'lum faktlar (narx, telefon)
  aniq ko'rinishda yoziladi va egasiga «tekshiring» ro'yxati beriladi.
- Tugmalar qisqa (≤ 24 belgi), emoji bilan, qatorlarda muvozanatli.
- Tanlangan uslub (klaviatura / inline / aralash) izchil qo'llangan.
- Natija ≤ 60 soniyada; qo'llashdan oldin sinab ko'rish va bir bosishda qaytarish mumkin.
