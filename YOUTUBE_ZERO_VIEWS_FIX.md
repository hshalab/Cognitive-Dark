# 🔧 YouTube Zero-Views / Shorts-Feed Diagnosis & Repair

## Sab se bara masla (code se confirmed)

`src/platforms/youtube.py` har video ko **`privacyStatus: "private"`** ke sath
upload karta hai aur usay sirf tab public karta hai jab `publishAt` ka
scheduled time aaye. YouTube ka scheduler private video ko khud public karta hai
— **lekin agar yeh schedule "fire" na ho (API/quota issue, galat future time,
ya video 24 ghante se zyada door schedule ho), to video HAMESHA private reh
jati hai. Private videos ko koi impressions nahi milte → 0 views.**

Yahi aapki zero-views videos ki sab se mumkin waja hai.

---

## 1. Abhi check karein (diagnostic script)

Repo mein naya script add kiya hai:

```bash
python scripts/youtube_shorts_repair.py
```

Yeh aapki channel ki **saari videos** (public, private, scheduled, unlisted)
nikal ke har ek ke liye batayega:

| Cheez | Matlab |
|---|---|
| `privacyStatus` | private hai ya public — private = 0 impressions |
| `publishAt` | future mein to abhi tak public nahi hui |
| `views` | kitne views aaye |
| `dur` | duration (Shorts ke liye ≤ 180s hona chahiye) |
| Shorts issues | vertical/portrait hai ya nahi, resolution, ratio |
| **Past-due PRIVATE** | scheduled time guzar gaya magar abhi bhi private |

Agar koi video "past-due private" list mein aaye, woh atki hui hai.

### 2. Ek click repair

```bash
python scripts/youtube_shorts_repair.py --fix-public
```

Yeh un tamam videos ko **public** kar dega jin ka scheduled time guzar chuka hai
magar woh abhi tak private hain. Is ke baad YouTube unhein Shorts feed mein
process karega.

> Credentials wohi hain jo upload ke liye: `.env` mein
> `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `REFRESH_TOKEN` (ya
> `YOUTUBE_CREDENTIALS`).

---

## 3. Zero views ki deegar wajuhat (jab video public ho)

Agar video **public** hai phir bhi 0/2 views hain, to yeh technical nahi
**algorithm** ka issue hai. Naye channel ke liye yeh normal hai:

### Cold-start kaise kaam karta hai
1. YouTube pehle **chhote test impressions** deta hai (24–72h).
2. Us batch mein yeh dekhta hai:
   - **CTR** (thumbnail/title click rate) — 5%+ achha
   - **3-second retention** — pehly 3 sec mein kitne ruke
   - **Average view %** — 60%+ Shorts ke liye bohat achha
3. Agar yeh signals weak hue, video aur push nahi hoti → views ruk jate hain.

### Shorts feed mein na aane ki technical sharait (code check karta hai)
- ✅ **Vertical 1080×1920** (aapka code yahi banata hai)
- ✅ **≤ 60s** (aapki pipeline 57s cap karti hai — bilkul sahi)
- ✅ Square pixels, libx264, AAC audio, faststart (code mein set hai)
- ✅ `selfDeclaredMadeForKids: False` (adult educational content)
- ⚠️ Video ka **PUBLIC** hona zaroori hai (upar wali fix)

### Content-side improvement (sab se zaroori)
- Pehla **2 second ka hook** stop-scroll hona chahiye (dekhiye
  `USA_GROWTH_PLAN.md` ke 30 hooks).
- Thumbnail mein 3 se kam lafz, high-contrast red/yellow.
- Pehla frame clear ho — band chalte hue phone mein bhi samajh aaye.
- Captions on (code already banata hai) — 85% USA log bina awaz dekhte hain.
- Pehle 60 minute mein khud ek pinned comment daalein.

---

## 4. Naye channel ke liye 30-din ki haqeeqat

- 4 videos par 0–2 views **bilkul normal** hai.
- YouTube ko 20–30 videos ke baad aapki channel "samajh" aati hai (kis niche,
  kaun audience).
- Sab se bara lever: **consistency + behtar hooks**, na ke settings.
- Rozana 1 Short 30 din tak = algorithm ko train karne ka minimum dataset.

---

## 5. Verify kaise karein repair ke baad

`--fix-public` chalane ke 24–48 ghante baad:

```bash
python scripts/channel_inventory.py
python scripts/fetch_metrics.py
```

YouTube Studio mein bhi check karein:
- **Content → Shorts** tab — video wahan dikhni chahiye
- **Analytics → Reach → Impressions** — impressions aane chahiye
- Agar 72h baad bhi 0 impressions hain to:
  - video ko delete karke **same content naye thumbnail/title** ke sath
    dobara upload karein (purani video ka weak signal chala jata hai)

---

## 6. CI se chalaein (browser ke bina)

`.github/workflows/video_manager.yml` mein "Run manager" step already mojood
hai. Agar chaho to is script ko us workflow ke through bhi chala sakte hain
(workflow_dispatch se) — main us mein `"shorts_repair"` action add kar sakta
hun. Bata dein.
