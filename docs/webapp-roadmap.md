# Kodsiz Web App konstruktori — professional tizimga yo'l xaritasi

Maqsad: foydalanuvchi kod yozmasdan **istalgan** Telegram Mini App'ni — istalgan ko'rinishda, istalgan
mantiq bilan — yarata olsin. Keyingi bosqichda esa AI oddiy suhbat orqali xuddi shu qurilish bloklaridan
ilova yig'ib bersin.

Asosiy tamoyil: **bitta hujjat formati** (`packages/core/core/webapp_builder.py`). Konstruktor, ochiq ilova,
kutubxona va kelajakdagi AI — hammasi shu JSON daraxt bilan ishlaydi. Shuning uchun AI yaratgan ilovani
foydalanuvchi qo'lda davom ettira oladi va aksincha.

## ✅ Bajarilgan

| Bosqich | Nima qo'shildi |
|---|---|
| 0. Asos | Sahifalar, 19 ta tayyor blok, mavzular, qoralama/e'lon, buyurtma va formalar, arizalar qutisi |
| 1. Erkin dizayn | Elementlar daraxti (konteyner, matn, rasm, tugma, ikonka...), universal uslub, 12 shrift, keng oyna uchun alohida qiymatlar, bekor qilish/qaytarish, versiyalar |
| 2. Ma'lumotlar | To'plamlar (o'z jadvallari), 11 maydon turi, CSV, «Ma'lumotlar ro'yxati», takrorlovchi konteyner, `{{maydon}}`, batafsil sahifalar, formalar to'plamga yozadi |
| 3. Komponentlar va kreativ dizayn | Pastda batafsil |

### 3-bosqich: komponentlar tizimi va kreativ dizayn

**Kutubxona** — 75 ta tayyor komponent, 15 ta toifada (bannerlar, navigatsiya, kartalar, karusel,
afzalliklar, do'kon, narxlar, sharhlar, raqamlar, kontent, chaqiruv, jamoa/profil, media/xarita,
pastki qism, elementlar). Har biri **jonli ko'rinishda** (haqiqiy dvigatelda chizilgan kichik nusxa)
ko'rsatiladi, qidiruv bor; tanlangani yangi bo'lim sifatida, tanlangan konteyner ichiga yoki elementdan
keyin qo'yiladi. Komponent — oddiy elementlar daraxti: qo'yilgandan keyin har bir qismi o'zgaradi.

**Mening komponentlarim** — istalgan konteynerni ⭐ bilan saqlash va istalgan ilovada qayta ishlatish
(`web_components` jadvali, 100 tagacha, rasmlar egasi tekshiriladi).

**Yangi konteyner turlari:** karusel (avtomatik aylanish, nuqtalar), qatlamlar (ustma-ust — rasm ustida
matn), yorliqlar (3 uslub), akkordeon, cheksiz yuguruvchi lenta.

**Yangi elementlar:** YouTube video, progress (chiziq/halqa), reyting yulduzlari, taymer, Google xarita.

**Uslub dvigateli:**
- mavzu ranglari (`$primary`, `$surface`, `$text`...) — mavzu yoki tun rejimi o'zgarsa komponent moslashadi;
- aniq kenglik/balandlik/foiz, proporsiya, «bo'sh joyni egallash», to'rda ustun/qator egallash (bento);
- erkin / yopishqoq / ekranga yopishgan joylashuv, qatlam tartibi;
- burish, masshtab, siljitish, qiyshaytirish; xiralash, yorqinlik, oq-qora; «shisha» effekti;
- doiraviy va konus gradientlar, fon shaffofligi, matn gradienti, rangli va «qattiq» soyalar, chiziq turlari;
- kursiv, tagi/ustidan chiziq, qatorlar sonini cheklash;
- **hover holati** (kompyuterda sichqoncha, telefonda bosish) silliq o'tish bilan;
- 11 ta paydo bo'lish animatsiyasi + kechikish, 8 ta doimiy harakat (suzish, puls, sakrash...).

**Muharrir:** qatlamlarni sudrab ko'chirish (oldiga / ichiga / keyiniga), yo'l (breadcrumb), qatlam
nomlari, «konteynerga o'rash», guruh sarlavhasida o'zgartirilgan qiymatlar soni.

## 🔜 Keyingi bosqichlar

### 4. Mantiq va holat (interaktivlik)
- O'zgaruvchilar (sahifa/ilova darajasida), hisoblangan qiymatlar (`{{narx * soni}}`).
- Shartli ko'rsatish: «agar foydalanuvchi ro'yxatdan o'tgan bo'lsa», «agar savat bo'sh bo'lsa».
- Amallar zanjiri: bosilganda → o'zgaruvchini o'zgartir → yozuv qo'sh → sahifaga o't → xabar ko'rsat.
- Erkin dizayndagi kiritish maydonlari (input, tanlov, sana, slayder) va istalgan formani yig'ish.
- Modal oynalar, pastdan chiqadigan oyna, toast xabarlar.
- Foydalanuvchi profili (Telegram ismi, rasmi), «Mening buyurtmalarim».

### 5. Ilova tuzilmasi
- Global sarlavha va pastki menyu (barcha sahifalarda), yon menyu.
- Sahifa o'tish animatsiyalari, sahifa parametrlari.
- Dizayn tizimi: global ranglar palitrasi, matn uslublari (H1/H2/... bir joydan), tugma uslublari.
- Komponent «master»lari: bitta joyda o'zgartirilsa — hamma nusxasi yangilanadi.

### 6. Integratsiyalar va to'lov
- Click / Payme / Telegram Stars to'lovlari.
- Webhook va tashqi API chaqiruvlari (kodsiz so'rov quruvchi).
- Bot bilan chuqur bog'lanish: ilovadan botga xabar, bot ssenariylari.
- Fayllarni saqlash (MinIO yoki S3).

### 7. AI bilan yaratish
- Suhbat orqali: «go'zallik saloni uchun yozilish ilovasi kerak» → AI kutubxonadagi komponentlar va
  sxema asosida to'liq ilova (sahifalar, to'plamlar, mantiq) yig'adi.
- Tanlangan bo'limni AI bilan qayta dizayn qilish: «buni zamonaviyroq qil», «tun rejimiga moslash».
- Matnlarni yozish/tarjima, rasmlar tavsiyasi.
- AI natijasi oddiy hujjat — foydalanuvchi uni qo'lda tahrirlashda davom etadi.

### 8. Ekotizim
- Shablonlar va komponentlar bozori (foydalanuvchilar o'zaro ulashadi).
- Jamoa bilan birga tahrirlash, izohlar.
- Statistika: ko'rishlar, bosishlar, konversiya.
- O'z domeni va Telegramdan tashqarida ochilish.

## Ochiq qarorlar
1. Foydalanuvchilarga o'z HTML/JS kodini qo'shishga ruxsat (xavfsizlik vs erkinlik).
2. Ilovalar Telegramdan tashqarida ham ochilsinmi.
3. To'lov tizimlari: Click, Payme yoki ikkalasi.
4. Fayllar: serverdagi MinIO yoki tashqi S3.
