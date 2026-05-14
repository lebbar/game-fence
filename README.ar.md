# Game Fence

🌍 **اللغات**

- 🇸🇦 **العربية** _(هذا الملف)_
- 🇬🇧 [English](README.md)
- 🇫🇷 [Français](README.fr.md)

---

تطبيق **Windows** يتيح **تقييد أو حظر تشغيل البرامج** وفق **جدول أسبوعي** (لكل ملف تنفيذي). مفيد لتنظيم وقت الشاشة أو الألعاب؛ يعمل التطبيق في الخلفية ويمكنه إغلاق العمليات المستهدفة تلقائيًا خارج الفترات المسموح بها.

## الميزات

- قواعد لكل **ملف تنفيذي** (مثل `steam.exe`) مع أوضاع مختلفة حسب اليوم: حظر كامل طوال اليوم، السماح فقط بين ساعات محددة، وغير ذلك.
- واجهة **Tkinter**: العربية، الإنجليزية، الفرنسية (مع دعم RTL للعربية).
- مصدر الوقت: **NTP** عند توفر الشبكة، وإلا يتم الاعتماد على ساعة النظام؛ مع إمكانية ضبط المنطقة الزمنية **UTC±N**.
- **اختصار عام** `Ctrl+Shift+G` لإظهار النافذة (يتطلب مكتبة `keyboard`).
- ملف إعدادات JSON دائم.

## المتطلبات

- **Windows 10/11** (64-bit).
- **Python 3.10+** (لتشغيل المشروع من المصدر).

## التنزيل (ملف جاهز)

**للمستخدمين** (بدون Python):

- **رابط تنزيل مباشر (آخر إصدار من `GameFence.exe`):**  
  [https://github.com/lebbar/game-fence/releases/latest/download/GameFence.exe](https://github.com/lebbar/game-fence/releases/latest/download/GameFence.exe)

- **صفحة الإصدارات:** [https://github.com/lebbar/game-fence/releases](https://github.com/lebbar/game-fence/releases)

### نشر إصدار (للمشرفين)

**الخيار أ — CI (مُفضّل)**  
ادفع وسيم إصدار؛ تشغّل GitHub Actions (`.github/workflows/release.yml`) البناء على Windows وترفع **`GameFence.exe`** كأصل مع الإصدار:

```powershell
git tag v1.0.0
git push origin v1.0.0
```

**الخيار ب — يدوي**  
`.\build.ps1` → `dist\GameFence.exe`، ثم على GitHub: **Releases** → **Draft a new release** → وسم (مثل `v1.0.0`) → أرفق **`GameFence.exe`** → **Publish release**.

## التثبيت (للتطوير)

```powershell
git clone <your-git-url>
cd game-fence
python -m pip install -r requirements.txt
```

لتفعيل اختصار لوحة المفاتيح العام:

```text
pip install keyboard
```

(المكتبة موجودة بالفعل في `requirements.txt`.)

## التشغيل

```powershell
python main.py
```

عند التشغيل لأول مرة، قد يبقى التطبيق مخفيًا: استخدم **`Ctrl+Shift+G`** لإظهار النافذة.

## الإعدادات

الملف: `%LOCALAPPDATA%\GameFence\config.json`

- القواعد، فترة المراقبة، لغة الواجهة، فرق التوقيت (UTC±N)، وغير ذلك.

## البناء — ملف تنفيذي مستقل

باستخدام **PyInstaller** (راجع `requirements-build.txt`) :

```powershell
.\build.ps1
```

الناتج: `dist\GameFence.exe` (بدون نافذة console).

### مُثبّت Windows (اختياري)

1. قم ببناء ملف EXE عبر `build.ps1`.
2. افتح `installer.iss` باستخدام **[Inno Setup](https://jrsoftware.org/isinfo.php)** ثم اضغط **Compile**.

الناتج: المجلد `installer_output\`.

## بنية المشروع

| العنصر | الدور |
|--------|--------|
| `main.py` | الواجهة الرسومية |
| `core.py` | الجدولة، الإعدادات، وإغلاق العمليات |
| `clock_sync.py` | مزامنة NTP / الوقت المرجعي |
| `i18n.py` | النصوص والخطوط حسب اللغة |
| `locales/` | الترجمات `fr.json`, `en.json`, `ar.json` |
| `GameFence.spec` | إعدادات PyInstaller |
| `build.ps1` | تثبيت الاعتماديات وبناء ملف EXE |

## الاعتماديات الرئيسية

- `keyboard` — اعتراض لوحة المفاتيح للاختصار العام.
- `ntplib` — طلبات NTP.

## الأمان والقيود

- يعتمد التحكم على الجهاز الذي تعمل عليه الأداة؛ يمكن لمستخدم يملك صلاحيات المسؤول تعطيل الأداة.
- يُفضّل الجمع مع حسابات مناسبة لاستخدام جاد يشبه «الرقابة الأبوية».
- لا يُعد هذا التطبيق بديلاً عن الإشراف المادي أو وجود بالغ مع المستخدم.
- غالبًا ما يمكن لشخص لديه معرفة تقنية أن يجد ثغرة أو طريقًا للتجاوز؛ لا تعتبر الحماية مطلقة.

---

*مشروع شخصي — المساهمات وفتح المشاكل مرحب بها.*
