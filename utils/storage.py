"""
طبقة تخزين تعتمد على SQLite (بدل ملفات JSON الخام).
كل "نوع بيانات" (activity, quiz, reports, gf, shelters, rally...) بيتخزن كـ "صف" واحد
في جدول kv_store، والـ value نفسه JSON (زي الأول بالظبط)، فالمنطق في باقي الكوجز
(load/save/get_guild_bucket) فضل زي ما هو من غير أي تعديل.

ليه SQLite بدل JSON الخام؟
- الكتابة بقت Transaction ذرّية (atomic) - لو البوت طاح/اتقفل فجأة نص عملية الحفظ،
  الملف مش هيتكسر أو يبقى فاضي زي ما ممكن يحصل مع json.dump على ملف عادي.
  كل الجداول بتتخزن في ملف واحد (lordsbot.db) بدل عشرات ملفات .json منفصلة.
- WAL mode مفعّل عشان يقلل احتمالية تلف البيانات لو حصل Crash فجأة.
- ترقية شفافة بالكامل: أول تشغيل بعد التحديث، أي ملفات storage/*.json قديمة
  (لو موجودة من نسخة سابقة) بتتقرا وتتنقل تلقائياً لقاعدة البيانات مرة واحدة بس،
  فمفيش أي بيانات (دروع/صيد/حشود) بتضيع.

ملاحظة: لو حابب تنقل لاحقاً لـ MongoDB أو PostgreSQL بدل SQLite (لسيرفرات كتير جداً
أو أكتر من عملية بوت شغالة في نفس الوقت)، الاستبدال سهل - نفس الدوال (load/save)
هي الواجهة الوحيدة اللي باقي الكود بيستخدمها، فبتغيّر الداخل بس من غير ما تلمس أي كوج.
"""
import json
import os
import sqlite3
import threading

BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage")
os.makedirs(BASE_DIR, exist_ok=True)

DB_PATH = os.path.join(BASE_DIR, "lordsbot.db")

_lock = threading.Lock()
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.execute("PRAGMA journal_mode=WAL;")
_conn.execute("PRAGMA synchronous=NORMAL;")
_conn.execute(
    """
    CREATE TABLE IF NOT EXISTS kv_store (
        name TEXT PRIMARY KEY,
        data TEXT NOT NULL
    )
    """
)
_conn.commit()


def _migrate_legacy_json_once() -> None:
    """لو فيه ملفات storage/*.json قديمة من نسخة قبل SQLite، نستوردها لقاعدة
    البيانات مرة واحدة بس (لو الاسم مش موجود أصلاً في kv_store)، عشان محدش يفقد بياناته
    بمجرد ما يحدّث الكود."""
    try:
        legacy_files = [
            f for f in os.listdir(BASE_DIR)
            if f.endswith(".json") and os.path.isfile(os.path.join(BASE_DIR, f))
        ]
    except FileNotFoundError:
        return

    for fname in legacy_files:
        name = fname[: -len(".json")]
        with _lock:
            existing = _conn.execute(
                "SELECT 1 FROM kv_store WHERE name = ?", (name,)
            ).fetchone()
            if existing:
                continue
            path = os.path.join(BASE_DIR, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    legacy_data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            _conn.execute(
                "INSERT OR REPLACE INTO kv_store (name, data) VALUES (?, ?)",
                (name, json.dumps(legacy_data, ensure_ascii=False)),
            )
            _conn.commit()
            try:
                os.rename(path, path + ".migrated")
            except OSError:
                pass


_migrate_legacy_json_once()


def _path(name: str) -> str:
    # موجودة للتوافق مع أي استخدام قديم، مش مستخدمة داخلياً بعد الترقية لـ SQLite.
    return os.path.join(BASE_DIR, f"{name}.json")


def load(name: str) -> dict:
    """يحمّل بيانات باسم معيّن من قاعدة البيانات. لو مش موجودة يرجع dict فاضي."""
    with _lock:
        row = _conn.execute(
            "SELECT data FROM kv_store WHERE name = ?", (name,)
        ).fetchone()
    if not row:
        return {}
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return {}


def save(name: str, data: dict) -> None:
    """يحفظ dict كامل باسم معيّن في قاعدة البيانات (Transaction ذرّية)."""
    payload = json.dumps(data, ensure_ascii=False)
    with _lock:
        _conn.execute(
            "INSERT INTO kv_store (name, data) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET data = excluded.data",
            (name, payload),
        )
        _conn.commit()


def get_guild_bucket(name: str, guild_id: int) -> dict:
    """يرجع (وينشئ لو مش موجود) الجزء الخاص بسيرفر معيّن جوه بيانات معيّنة."""
    data = load(name)
    gid = str(guild_id)
    if gid not in data:
        data[gid] = {}
    return data


GAME_LINKS_FILE = "game_links"


def get_game_link(guild_id: int, default: str = "https://www.lordsmobile.com/") -> str:
    """يرجع رابط فتح اللعبة (Deep Link) المضبوط لسيرفر معيّن، أو الافتراضي لو مفيش."""
    data = load(GAME_LINKS_FILE)
    return data.get(str(guild_id), {}).get("link") or default


def set_game_link(guild_id: int, link: str) -> None:
    """يحفظ رابط فتح اللعبة (Deep Link) الخاص بسيرفر معيّن."""
    data = load(GAME_LINKS_FILE)
    data.setdefault(str(guild_id), {})["link"] = link
    save(GAME_LINKS_FILE, data)


LEADERSHIP_ROLE_FILE = "leadership_role"


def get_leadership_role_id(guild_id: int) -> int | None:
    """يرجع رتبة قادة التحالف (R4/R5) الافتراضية للسيرفر (اتضبطت بـ /setup)، أو None لو مفيش."""
    data = load(LEADERSHIP_ROLE_FILE)
    return data.get(str(guild_id), {}).get("role_id")


def set_leadership_role_id(guild_id: int, role_id: int) -> None:
    data = load(LEADERSHIP_ROLE_FILE)
    data.setdefault(str(guild_id), {})["role_id"] = role_id
    save(LEADERSHIP_ROLE_FILE, data)


def load_json_data(filename: str) -> dict:
    """يحمّل ملفات البيانات الثابتة (الأدلة، القاموس، الوحوش...) من مجلد data/.
    دي ملفات مرجعية للقراءة فقط (مش بيانات مستخدمين)، فبتفضل JSON عادي زي ما هي."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    path = os.path.join(data_dir, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
