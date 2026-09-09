"""
بيبني نص معرفي (Knowledge Base) من كل ملفات data/*.json
عشان يتغذى بيه الـ AI (Cohere) فيبقى فاهم لوردس موبايل كويس
ويقدر يجاوب ويتكلم بشكل طبيعي بدل ما يكون فاضي من أي سياق.
"""
import json
import os

from utils.storage import load_json_data

SYSTEM_PERSONA = """أنت "مستشار لوردس" - بوت ذكي، مرح، وصاحب دعابة حاضرة، متخصص في لعبة Lords Mobile وبيتفاعل مع أعضاء سيرفر ديسكورد.
شخصيتك ودودة وواثقة وسريعة البديهة. استخدم هزاراً خفيفاً وسخرية ذكية و"قصف جبهة" طريفاً عندما يكون الكلام مزاحاً أو تحدياً، بحيث يكون الإحراج للموقف أو للصياغة لا إهانة حقيقية للشخص. لا تكرر نفس النكات الجاهزة ولا تتكلم بجفاف أو تقول إنك نموذج ذكاء اصطناعي.
إذا كان السؤال عن Lords Mobile أو طلب نصيحة لعب، أجب بجدية ووضوح أولاً، مع معلومات دقيقة قدر الإمكان، ويمكن إضافة لمسة فكاهية قصيرة لا تشتت عن الإجابة.
إذا كان الكلام عادياً أو مزاحاً، كن لطيفاً وشارك في المزاح برد مصري قصير وطبيعي (جملة أو جملتين). ممنوع إرسال سلاسل طويلة من «هههههههه» أو تكرار الضحك بدل الرد؛ لو السؤال محتاج إجابة، جاوب أولاً ثم أضف نكتة قصيرة.
ممنوع تماماً الشتائم والألفاظ البذيئة والعبارات الجارحة أو التهديدات أو السخرية من الهوية أو الشكل أو الصحة أو أي نقطة حساسة. لا تستخدم معلومات خاصة لإحراج أحد، ولا تحوّل المزاح إلى تحقير أو تحريض. لو المزحة تتجاوز الحدود، ارفض الجزء المؤذي بلطف ووجّهها لمزاح آمن.
طابق لغة ولهجة أحدث رسالة من العضو فوراً: العربية المصرية بالمصطلحات الشبابية عند الكتابة بالمصري، أو الإنجليزية أو الفرنسية أو أي لغة أخرى عند استخدامها. تفضيل اللغة المحفوظ للعضو هو الاختيار الاحتياطي فقط عندما لا تكون اللغة واضحة.
لا تترجم أسماء عناصر اللعبة بلا داعٍ. لو مش متأكد من معلومة دقيقة، خصوصاً أرقام التكلفة، قل إنها تقريبية وانصح المستخدم بالتأكد من اللعبة نفسها من غير اختلاق أرقام مؤكدة.
لما تهزر، استخدم ضحكة قصيرة واحدة فقط مثل «هههه» أو «هاها» عند الحاجة؛ ممنوع تكرار الضحك أو ملء الرد به.
اعتمد على المعلومات دي عن اللعبة لما تكون مفيدة للسؤال:
"""


COMMAND_REFERENCE = """### أوامر البوت
- /help: دليل الأوامر.
- /language: اختيار لغة الردود.
- /event، /shelter، /cost، /speedup، /jewel_calc: حواسب الأحداث والحماية والتكلفة والتسريعات والجواهر.
- /counter، /report add|list|user، /darknest، /colo، /analyze: أدوات الحرب والتكتيك.
- /wiki أو /guide، /play، /gear، /monster، /dict، /info، /heroes، /geartiers، /scout: أدلة اللعبة والتحديات.
- /log_activity، /rally_log، /information، /user_admin_check، /top5، /event_stats، /stats_event: متابعة نشاط التحالف والأعضاء.
- /gf task|done|board|optimize، /quiz: مهرجان التحالف والمسابقات.
- /reset_stats: تصفير سجلات الإحصاءات (إدارة).
- /market offer|list|cancel: سوق تبادل الموارد.
- /ai: سؤال مستشار لوردس أو تحليل صورة عتاد/تقرير، ومعه might اختياري.
- @LordsMobile [سؤال]: نفس مستشار الـAI بالمنشن.
- /troop set، /rally set: تسجيل نوع القوات وفتح نداء حشد ذكي.
- /hunt_log، /hunt_channel، /hunt_list: تسجيل ومتابعة صيد الوحوش.
- /shield أو /voice_rescue: منبه الدرع الصوتي.
- أوامر الإدارة: /add_monster، /delete_monster، /add_info، /delete_info، /edit_info، /hunt_channel، /reset_stats، /user_admin_check.
استخدم أسماء الأوامر كما هي مع الشرطة المائلة، واشرح للمستخدم المدخلات المطلوبة فقط إذا كانت معروفة من القائمة. إذا سأل عن أمر غير موجود هنا، قل إنك لا تملك تفاصيل مؤكدة عنه بدل اختراعه."""

KNOWN_DATA_FILES = {
    "dict.json", "info.json", "gear.json", "darknest.json", "monsters.json",
    "gear_tiers.json", "heroes.json", "companions.json", "formations.json", "colo_counters.json",
}


def append_all_remaining_game_data(parts: list[str]) -> None:
    """يضيف أي ملفات data JSON جديدة تلقائياً للـAI بدل نسيانها عند إضافة ملف جديد."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    try:
        filenames = sorted(name for name in os.listdir(data_dir) if name.endswith(".json"))
    except OSError:
        return
    for filename in filenames:
        if filename in KNOWN_DATA_FILES:
            continue
        try:
            payload = json.dumps(load_json_data(filename), ensure_ascii=False)
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        parts.append(f"\n### بيانات اللعبة الإضافية ({filename}):\n{payload}")


def build_knowledge_text() -> str:
    parts = []

    dict_data = load_json_data("dict.json")
    parts.append("### قاموس المصطلحات:")
    for term, desc in dict_data.items():
        parts.append(f"- {term}: {desc}")

    info_data = load_json_data("info.json")
    parts.append("\n### الأحداث الرئيسية:")
    for key, val in info_data.items():
        parts.append(f"- {val['title']}: {val['desc']}")

    gear_data = load_json_data("gear.json")
    parts.append("\n### العتاد حسب نوع القوات:")
    for troop, val in gear_data.items():
        parts.append(f"- {troop}: F2P -> {val['f2p']} | P2P -> {val['p2p']}")

    darknest_data = load_json_data("darknest.json")
    parts.append("\n### الحصن المظلم (Dark Nest) حسب المستوى:")
    for lvl, val in darknest_data.items():
        if lvl == "_note":
            continue
        parts.append(f"- مستوى {lvl}: أبطال: {val['heroes']} | تشكيلة: {val['formation']} | ملاحظات: {val['notes']}")

    monster_data = load_json_data("monsters.json")
    parts.append("\n### أبطال صيد الوحوش:")
    for name, val in monster_data.items():
        if name == "_note":
            continue
        note = f" | ملاحظة: {val['defense_note']}" if val.get("defense_note") else ""
        parts.append(f"- {name}: نوع الضرر المطلوب {val['damage_type']}{note} | أبطال مقترحين: {', '.join(val['heroes'])}")

    gear_tiers = load_json_data("gear_tiers.json")
    parts.append("\n### تصنيف العتاد حسب الغرض:")
    parts.append(f"- عتاد الحرب: P2P -> {gear_tiers['war']['p2p']} | F2P -> {gear_tiers['war']['f2p']} | ضعيف -> {gear_tiers['war']['weak']}")
    parts.append(f"- عتاد الصيد: P2P -> {gear_tiers['hunting']['p2p']} | F2P -> {gear_tiers['hunting']['f2p']}")
    parts.append(f"- عتاد الاقتصاد: {gear_tiers['economy']['pieces']} | تحذير: {gear_tiers['economy']['warning']}")

    heroes_data = load_json_data("heroes.json")
    parts.append("\n### خلاصة الأبطال:")
    for category, label in [("economy", "أبطال التطوير"), ("free_war", "أبطال حرب مجانيين"), ("paid_war", "أبطال حرب للشحن")]:
        heroes_list = ", ".join(f"{h['name']} ({h['role']})" for h in heroes_data[category])
        parts.append(f"- {label}: {heroes_list}")

    companions_data = load_json_data("companions.json")
    parts.append("\n### المرافقين (Familiars):")
    for key, val in companions_data.items():
        if key == "_note":
            continue
        parts.append(
            f"- {val['name']} {val.get('emoji', '')}: مهارة -> {val['skills']} | بوف -> {val['buffs']} "
            f"| طريقة التجميع -> {val['gathering']}"
        )

    formations_data = load_json_data("formations.json")
    parts.append("\n### تشكيلات الأبطال (كولوسيوم/حرب/دفاع):")
    for key, val in formations_data.items():
        if key == "_note":
            continue
        parts.append(f"- {val['title']}: {val['desc']}")

    colo_data = load_json_data("colo_counters.json")
    parts.append("\n### مقابلات الكولوسيوم (Colosseum Counters):")
    if colo_data.get("general_rule"):
        parts.append(f"- {colo_data['general_rule']['ar']}")
    for hero in colo_data.get("heroes", []):
        parts.append(f"- {hero['names']['ar']} ({hero['names']['en']}): {hero['counter']['ar']}")

    parts.append(
        "\n### كشف الخصم الضعيف:\n"
        "- لو الخصم لابس عتاد اقتصادي (نوسيروس/جريفون/لونار فلوت) وقت الحرب، دفاعه شبه معدوم وده وقت مثالي لحشده.\n"
        "- لو لاقيت تضارب بين نوع قطعة العتاد ونوع الجواهر جواها (زي درع رماة فيه جواهر مشاة)، ده مؤشر إن الحساب مش خبير أو بيلعب عشوائي."
    )

    append_all_remaining_game_data(parts)
    parts.append(COMMAND_REFERENCE)
    return "\n".join(parts)


KNOWLEDGE_TEXT = build_knowledge_text()


LANG_INSTRUCTION_EN = (
    "\n\nIMPORTANT: The saved preference is English, but always follow the language of the user's latest "
    "message when it is clear. Reply in natural, friendly English for English messages; use Egyptian Arabic "
    "for Egyptian Arabic messages and the user's language for French or other clear languages. Keep the "
    "playful, witty personality without profanity, insults, or hurtful comments. For game questions, be "
    "serious and useful first."
)


LANG_INSTRUCTION_AR = (
    "\n\nمهم: التفضيل المحفوظ عربي، لكن اتبع لغة أحدث رسالة من المستخدم فوراً لو كانت واضحة. "
    "استخدم المصرية الطبيعية للمصري، والإنجليزية أو الفرنسية أو لغة المستخدم لو كتب بها. حافظ على "
    "الهزار الذكي من غير شتائم أو إهانة أو إحراج مؤذٍ، واجعل إجابة أسئلة اللعبة جادة ومفيدة أولاً."
)


def get_system_prompt(lang: str = "ar") -> str:
    prompt = SYSTEM_PERSONA + "\n" + KNOWLEDGE_TEXT
    return prompt + (LANG_INSTRUCTION_EN if lang == "en" else LANG_INSTRUCTION_AR)
