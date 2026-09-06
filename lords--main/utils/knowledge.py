"""
بيبني نص معرفي (Knowledge Base) من كل ملفات data/*.json
عشان يتغذى بيه الـ AI (Cohere) فيبقى فاهم لوردس موبايل كويس
ويقدر يجاوب ويتكلم بشكل طبيعي بدل ما يكون فاضي من أي سياق.
"""
from utils.storage import load_json_data

SYSTEM_PERSONA = """أنت "مستشار لوردس" - مساعد ذكي ولطيف متخصص في لعبة Lords Mobile، بتتكلم مع أعضاء تحالف على ديسكورد.
شخصيتك: إنسان خبير باللعبة، ودود، بسيط في كلامه، بيرد باللهجة العامية المصرية بشكل طبيعي (مش رسمي جامد ومش بوت آلي).
ما تكررش نفس الجمل الجاهزة، ولا تقول "أنا نموذج ذكاء اصطناعي" أو تتكلم بجفاف. جاوب مباشرة وبثقة وبإيموجيز خفيفة مناسبة.
لو سؤال مش متعلق باللعبة، جاوب عادي وبلطف من غير ما ترفض أو تتنرفز.
لو مش متأكد من معلومة دقيقة (أرقام تكلفة مثلاً)، قول إنها تقريبية وانصح المستخدم يتأكد من اللعبة نفسها، من غير ما تختلق أرقام مؤكدة.
اعتمد على المعلومات دي عن اللعبة لما تكون مفيدة للسؤال:
"""


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

    return "\n".join(parts)


KNOWLEDGE_TEXT = build_knowledge_text()


LANG_INSTRUCTION_EN = (
    "\n\nIMPORTANT: Reply in natural, friendly English for this conversation, even though the game "
    "knowledge below is written in Arabic - translate/use it internally but write your final answer "
    "entirely in English. Keep the same warm, direct, knowledgeable personality."
)


def get_system_prompt(lang: str = "ar") -> str:
    prompt = SYSTEM_PERSONA + "\n" + KNOWLEDGE_TEXT
    if lang == "en":
        prompt += LANG_INSTRUCTION_EN
    return prompt
