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

1. **AI quruvchi v2 (hozir)** — konveyer (reja → mazmun → yig'ish → linter), aniqlashtiruvchi savollar,
   alohida kuchli «quruvchi modeli», joy tutuvchilarsiz aniq mazmun, **🧪 sinov rejimi** (egasi yangi botni
   foydalanuvchilarga ko'rsatmasdan sinaydi), sifat hisoboti.
2. **Katalog + savatcha + buyurtmalar + dinamik ro'yxatlar.**
3. **Yozilish + eslatmalar + avtomatik xabarlar.**
4. **Test/viktorina, reyting, kunlik bonus, kapcha, murojaat holatlari.**
5. **Usta (wizard) + vizual xarita (Mini App) + ko'p til.**
6. **To'lovlar.**
7. **Sifat to'plami** — 40 brif, avtomatik baholash, doimiy yaxshilash.

## Sifat mezonlari (har bir yaratilgan bot uchun)

- Har bir bo'limga yetib borish mumkin, har joydan orqaga yo'l bor, «boshi berk» joy yo'q.
- Matnlar aniq biznesga xos, `...`, `[ ]`, «lorem» kabi joy tutuvchilar yo'q; noma'lum faktlar (narx, telefon)
  aniq ko'rinishda yoziladi va egasiga «tekshiring» ro'yxati beriladi.
- Tugmalar qisqa (≤ 24 belgi), emoji bilan, qatorlarda muvozanatli.
- Tanlangan uslub (klaviatura / inline / aralash) izchil qo'llangan.
- Natija ≤ 60 soniyada; qo'llashdan oldin sinab ko'rish va bir bosishda qaytarish mumkin.
