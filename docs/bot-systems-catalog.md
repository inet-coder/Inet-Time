# Telegram botlarning asosiy turlari va ularga kerak funksiyalar

Maqsad: konstruktor **bitta loyihaga emas**, Telegram'da eng ko'p quriladigan **barcha** bot turlariga mos bo'lsin.
Buning uchun avval bot turlarini sanab, ularning umumiy «g'ishtlari»ni (modullarini) ajratamiz. Har bir tur —
shu g'ishtlarning turli kombinatsiyasi. G'isht bir marta quriladi, istalgan botga qo'shiladi.

## 1. Eng ko'p quriladigan bot turlari

| # | Tur | Kimlar quradi | Asosiy g'ishtlar |
|---|---|---|---|
| 1 | **Do'kon / restoran / yetkazib berish** | savdo, kafe, gul, kiyim | katalog, savat, buyurtma, to'lov, promokod, buyurtma holatlari |
| 2 | **Yozilish (booking)** | salon, klinika, avtoservis, repetitor, sport zal | xizmatlar, mutaxassislar, jadval, bo'sh vaqt, eslatma, bekor qilish |
| 3 | **Kanal yordamchisi** | kanal egalari, bloggerlar | majburiy obuna, avto-post, tugmali post, reaksiya/ovoz berish, statistika |
| 4 | **Qayta aloqa / yordam xizmati** | har qanday biznes | murojaat → egasi, javob berish, tiket holati, operatorlar, FAQ |
| 5 | **Ta'lim / kurs** | o'quv markazi, mentor | darslar, vazifalar, test, sertifikat, to'lov, guruhga qo'shish |
| 6 | **Viktorina / o'yin / konkurs** | marketing, kanallar | savol-javob, ball, reyting, kunlik bonus, tasodifiy g'olib, kapcha |
| 7 | **Referal / bonus tizimi** | tarmoq, MLM, aksiyalar | taklif havolasi, ball, mukofot bosqichlari, reyting, yechib olish |
| 8 | **Ariza / so'rovnoma / ro'yxatga olish** | tadbir, vakansiya, tanlov | ko'p bosqichli forma, fayl yuklash, tasdiqlash, jadvalga yozish |
| 9 | **Obuna / pullik klub** | kontent mualliflari | to'lov, muddat, avtomatik chiqarish, eslatma, kanalga taklif |
| 10 | **Ma'lumotnoma / katalog** | ko'chmas mulk, vakansiya, turizm | filtrli ro'yxat, qidiruv, kartalar, aloqa tugmasi |
| 11 | **Tarqatish / e'lonlar** | media, tashkilot | segmentlar, rejalashtirilgan xabar, statistika |
| 12 | **Anonim savol / fikr-mulohaza** | jamoa, o'qituvchi | anonim xabar, javob, moderatsiya |
| 13 | **Kalkulyator / generator** | xizmat narxlash | bosqichli savol → hisob → natija |
| 14 | **Ichki bot (jamoa uchun)** | kompaniya | rollar, vazifalar, hisobotlar, bildirishnomalar |

## 2. Umumiy g'ishtlar (modullar) va hozirgi holat

✅ tayyor · 🟡 qisman · ❌ yo'q

### Kontent va navigatsiya
- ✅ Bo'limlar, postlar (matn, rasm, video, fayl, ovoz...), formatlash
- ✅ Tugmalar: klaviatura / inline / aralash; surish, ko'chirish, kesish-qo'yish
- ✅ Kalit so'zlar, buyruqlar, tasodifiy post
- ✅ Shartli tugmalar (o'zgaruvchi qiymatiga qarab ko'rinadi)
- ❌ **Ko'p til** (foydalanuvchi tilni tanlaydi, matnlar tarjimasi)
- ❌ **Rejalashtirilgan post** (belgilangan vaqtda yuborish)

### Ma'lumot va foydalanuvchi
- ✅ O'zgaruvchilar (har foydalanuvchi uchun ID bo'yicha), tizim o'zgaruvchilari
- ✅ Savollar, ko'p bosqichli formalar, javoblar egasiga + CSV
- ✅ Foydalanuvchilar ro'yxati, bloklash, o'zgaruvchilarni tahrirlash
- ❌ **Segmentlar** (shart bo'yicha guruhlash: «ball > 10», «buyurtma bergan»)
- ❌ **Teglar / yorliqlar** (egasi foydalanuvchiga yorliq qo'yadi)
- ❌ **Jadval ko'rinishida ma'lumot** (egasi ro'yxatni botning o'zida yuritadi: yozuvlar, qo'shish, tahrirlash)

### Savdo
- ✅ Katalog, savat, buyurtma, holatlar, yetkazish, minimal summa
- ❌ Promokod / chegirma
- ❌ Ombor (qoldiq) va «tugadi» belgisi
- ❌ **To'lov** (Click, Payme, Telegram Payments)
- ❌ Variantlar (o'lcham, rang), qo'shimchalar (sous, qo'shimcha pishloq)

### Vaqt bilan ishlash
- ❌ **Yozilish**: xizmat × mutaxassis × jadval → bo'sh vaqt → band qilish → tasdiq → eslatma
- ❌ **Avtomatik xabarlar** (start'dan N soat keyin, tashlab ketilgan savat, tug'ilgan kun)
- ❌ **Takrorlanuvchi vazifalar** (har kuni 9:00 da «kun gapi»)

### Jalb qilish va o'yin
- ✅ Referal (ball, mukofot), majburiy obuna
- ❌ **Viktorina / test** (savollar, to'g'ri javob, ball, natija sahifasi)
- ❌ **Reyting** (TOP-10 o'zgaruvchi bo'yicha)
- ❌ **Kunlik bonus**, konkurs (tasodifiy g'olib), kapcha

### Aloqa
- ✅ Qayta aloqa (egasiga, «Reply» bilan javob), xabar tarqatish
- 🟡 Tiketlar: raqam, holat, tarix (hozir faqat oddiy yo'naltirish)
- ❌ **Operatorlar** (bir nechta admin ichida murojaatlarni bo'lib olish, «meniki» deb olish)
- ❌ Shablon javoblar

### Boshqaruv
- ✅ /admin: sozlamalar, foydalanuvchilar, tarqatish, CSV
- ✅ Adminlar ro'yxati
- ❌ **Rollar** (egasi / menejer / operator — kimga nima mumkin)
- ❌ **Statistika**: bo'limlar bosilishi, voronka, kunlar kesimida o'sish
- ❌ **Bildirishnoma sozlamalari** (qaysi hodisa kimga boradi)
- ❌ Zaxira nusxa / boshqa botga ko'chirish (eksport/import hujjat)

### Integratsiya
- ✅ Web App (Mini App) tugmasi, havolalar
- ❌ **Webhook** (tashqi tizimga so'rov yuborish: buyurtma → Google Sheets / CRM)
- ❌ Google Sheets'ga yozish
- ❌ Guruh/kanalga post yuborish (kanalga avto-post)

## 3. «Admin panel» har botda — talab

Har bir bot (AI yoki qo'lda yaratilgan) **o'z boshqaruv panelini** bot turiga qarab oladi. Panel statik emas:
botda qaysi modul bo'lsa, panelda shu modul bo'limi **o'zi paydo bo'ladi**.

```
⚙️ Boshqaruv paneli
 📊 Statistika            ← har doim
 👤 Foydalanuvchilar      ← har doim
 📨 Xabar tarqatish       ← har doim (segment bo'yicha)
 🛒 Do'kon                ← katalog moduli bo'lsa
 📅 Yozilishlar           ← booking moduli bo'lsa
 🎫 Murojaatlar           ← tiket moduli bo'lsa
 🏆 Viktorina             ← test moduli bo'lsa
 📝 Arizalar              ← formalar bo'lsa
 ⚙️ Sozlamalar            ← har doim
```

Texnik qoida: har modul `module_registry` da o'zini e'lon qiladi — `{id, nomi, panel_bo'limi, bot_hujjatidagi_kaliti,
hodisalar}`. Panel va statistika shu ro'yxatdan chiziladi, shuning uchun yangi modul qo'shilganda panelga
qo'lda tegish kerak emas.

## 4. Interfeys qoidalari (AI'siz ham oson)

Hozirgi og'riq: imkoniyat ko'p, lekin yangi odam «qayerdan boshlash»ni bilmaydi. Yechim — **uch daraja**:

1. **Tayyor tizim tanlash (30 soniya).** «Bot yaratish» → 14 ta **tizim** kartasi (do'kon, yozilish, kanal yordamchisi,
   viktorina, qayta aloqa…) → har biri uchun 3–5 ta savol (nom, telefon, manzil, ish vaqti, mahsulotlar) → bot tayyor,
   o'zi ishlaydi. AI kerak emas. Savollarga javoblar shablonga qo'yiladi.
2. **AI bilan (60 soniya).** Xuddi shu tizimlar, lekin erkin matn: «Toshkentda gul do'koni…» → AI tizimni tanlaydi,
   savollarni o'zi to'ldiradi, qolganini so'raydi. AI **tizimlar kutubxonasidan** yig'adi — noldan kod yozmaydi,
   shuning uchun sifat doim bir xil yuqori.
3. **Qo'lda sozlash.** Yaratilgandan keyin hamma narsa tahrirlanadi: muharrir (tugmalar/postlar), modul
   sozlamalari, panel.

Har bir ekranda: bitta asosiy harakat, 3 tadan ko'p bo'lmagan tugma qatori, har bir bo'limda «ℹ️ bu nima?» qisqa
izoh, xato bo'lsa — nima qilish kerakligi (sabab emas, yechim).

**Yangi foydalanuvchi uchun «Birinchi 5 daqiqa» yo'riqnomasi**: bot yaratilgach panel tepasida
`1) matnlarni tekshiring ✓  2) mahsulot/xizmat qo'shing ✓  3) o'zingiz sinab ko'ring ✓  4) kanalga e'lon qiling`
ro'yxati — bajarilgan bandlar belgilanadi.

## 5. AI qanday ishlaydi (tizim kutubxonasi asosida)

```
Egasi yozadi → AI niyatni aniqlaydi (qaysi tizim(lar)?) → kerakli modullar tanlanadi
→ modul sozlamalari to'ldiriladi (mahsulotlar, xizmatlar, jadval...) → matnlar yoziladi
→ linter tekshiradi → 🧪 sinov → ✅ qo'llash
```

- AI **modul konfiguratsiyasini** to'ldiradi (aniq sxema bo'yicha, validatsiya bilan) — bu erkin JSON'dan ancha ishonchli.
- Aralash botlar: «salon + do'kon + referal» — bir nechta modul bir botga.
- Bot yaratilgandan keyin ham AI modul qo'sha oladi: «yozilish qo'sh», «promokod qo'sh», «har kuni 9:00 da maslahat yubor».
- Egasi so'rovni muhokama qiladi, AI aniqlashtiruvchi savol beradi (faqat zarur bo'lsa).

## 6. Bajarish tartibi (ta'sir kuchiga qarab)

| Bosqich | Nima | Nima uchun avval |
|---|---|---|
| **A** | **Modul reyestri + panel modullarga qarab chiziladi** + statistika (voronka) | Hamma narsaning poydevori; admin panel talabi |
| **B** | **Tizimlar galereyasi** (14 tizim kartasi + savollar) — AI'siz yaratish | Yangi foydalanuvchi uchun asosiy qulaylik |
| **C** | **Yozilish moduli** (booking) | 2-o'rinda eng ko'p so'raladigan tur |
| **D** | **Avtomatik xabarlar** + rejalashtirilgan post + segmentlar | Savdo va kanal botlari uchun marketing |
| **E** | **Viktorina / reyting / kunlik bonus / konkurs / kapcha** | Kanal va jalb qilish botlari |
| **F** | **Tiketlar + operatorlar + rollar** | Yordam xizmati botlari |
| **G** | **To'lovlar** (Telegram Payments) + promokod + ombor | Savdo va pullik obuna |
| **H** | **Webhook + Google Sheets + kanalga avto-post** | Integratsiya |
| **I** | **Ko'p til** + eksport/import | Kengayish |
| **J** | **40 brifli sifat to'plami** | Har bosqichdan keyin regressiya |

Birinchi navbatdagi ish — **A + B**: ular qolgan hamma modulni «bir xil usulda» qo'shish imkonini beradi.
