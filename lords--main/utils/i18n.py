"""
طبقة ترجمة خفيفة (ar/en) لتفضيل اللغة على مستوى السيرفر أو المستخدم.
مسؤولة عن: تخزين/قراءة تفضيل اللغة، وقاموس ترجمات لعناصر الواجهة
(أزرار، عناوين، رسائل نظام) للأوامر اللي بتدعم اللغتين.

⚠️ حدود مهمة (قيود منصة ديسكورد نفسها، مش قيد في الكود):
أسماء ووصف الأوامر اللي بتظهر لما تكتب "/" جوه ديسكورد (زي "🏯 أفضل أبطال وتشكيلة
لإسقاط الحصن المظلم") دي "Metadata" مسجّلة مع ديسكورد وقت تشغيل البوت، وبتتحدد حسب
لغة تطبيق ديسكورد بتاع كل شخص - مش ممكن تتغيّر ديناميكياً حسب إعداد `/language` بتاعنا
لكل سيرفر. اللي فعلاً بيتغيّر مع `/language` هو *رد البوت الفعلي* لما تنفّذ الأمر:
العنوان، القوائم المنسدلة، الأزرار، النوافذ (Modals)، والرسائل. وده اللي المستخدم بيشوفه
ويتفاعل معاه فعلياً في 99% من الوقت.

نطاق التغطية الحالي (بيتحترم فيه إعداد اللغة بالكامل في ردود البوت):
/ai، /play، /rally، /troop، /language، /language me، /languageme، /help.
باقي الأوامر (market/intel/hunt/shield/guild/rally-remaining/events/wiki/monster/
dict/info/heroes/geartiers/scout/counter/report/colo/analyze) لسه بواجهة عربية ثابتة
حالياً - ترجمتها خطوة تالية.
"""
from utils.storage import load, save

SETTINGS_FILE = "settings"
USER_SETTINGS_FILE = "user_settings"
DEFAULT_LANG = "ar"
SUPPORTED_LANGS = ("ar", "en")


def get_lang(guild_id: int | None, user_id: int | None = None) -> str:
    """يرجع لغة المستخدم، ثم لغة السيرفر كخيار احتياطي، ثم العربية."""
    if user_id is not None:
        user_data = load(USER_SETTINGS_FILE)
        user_lang = user_data.get(str(user_id), {}).get("lang")
        if user_lang in SUPPORTED_LANGS:
            return user_lang

    if guild_id is not None:
        guild_data = load(SETTINGS_FILE)
        guild_lang = guild_data.get(str(guild_id), {}).get("lang")
        if guild_lang in SUPPORTED_LANGS:
            return guild_lang

    return DEFAULT_LANG


def set_lang(guild_id: int, lang: str) -> None:
    data = load(SETTINGS_FILE)
    gid = str(guild_id)
    data.setdefault(gid, {})
    data[gid]["lang"] = lang
    save(SETTINGS_FILE, data)


def set_user_lang(user_id: int, lang: str) -> None:
    """يحفظ اختيار اللغة الخاص بعضو واحد، بدون تغيير إعداد السيرفر."""
    data = load(USER_SETTINGS_FILE)
    uid = str(user_id)
    data.setdefault(uid, {})
    data[uid]["lang"] = lang
    save(USER_SETTINGS_FILE, data)


TRANSLATIONS = {
    "lang_set_ar": {
        "ar": "✅ تم تغيير لغة البوت في السيرفر ده إلى **العربية**.",
        "en": "✅ تم تغيير لغة البوت في السيرفر ده إلى **العربية**.",
    },
    "lang_set_en": {
        "ar": "✅ Bot language for this server switched to **English**.",
        "en": "✅ Bot language for this server switched to **English**.",
    },
    "lang_admin_only": {
        "ar": "❌ الأمر ده يحتاج صلاحية Manage Server عشان محدش يغيّر لغة السيرفر عبطًا.",
        "en": "❌ This command requires the Manage Server permission.",
    },
    # /bot_channel
    "bot_channel_success": {
        "ar": "✅ تم تحديد {channel} كقناة/ثريد تواصل البوت في السيرفر ده.",
        "en": "✅ {channel} is now set as the bot's communication channel/thread in this server.",
    },
    "bot_channel_admin_only": {
        "ar": "❌ الأمر ده يحتاج صلاحية Manage Server.",
        "en": "❌ This command requires the Manage Server permission.",
    },
    "bot_channel_error": {
        "ar": "⚠️ حصل خطأ أثناء حفظ القناة. حاول تاني.",
        "en": "⚠️ Something went wrong while saving the channel. Please try again.",
    },
    "bot_channel_current_none": {
        "ar": "ℹ️ مفيش قناة/ثريد تواصل محددة للبوت في السيرفر ده لسه.",
        "en": "ℹ️ No bot communication channel/thread is set for this server yet.",
    },
    "bot_channel_current": {
        "ar": "ℹ️ قناة/ثريد تواصل البوت الحالية: {channel}",
        "en": "ℹ️ Current bot communication channel/thread: {channel}",
    },
    # /ai
    "ai_need_input": {
        "ar": "❓ اكتب سؤال أو ارفق صورة عتاد/تقرير عشان أقدر أساعدك.",
        "en": "❓ Type a question or attach a gear/report image so I can help.",
    },
    "ai_disabled": {
        "ar": "⚠️ خاصية الـ AI مش مفعّلة لسه. لازم صاحب البوت يحط `COHERE_API_KEY` في ملف `.env` الأول.",
        "en": "⚠️ The AI feature isn't enabled yet. The bot owner needs to set `COHERE_API_KEY` in `.env` first.",
    },
    "ai_bad_image": {
        "ar": "❌ الملف اللي رفعته مش صورة. ارفق صورة (png/jpg) عشان أقدر أحللها.",
        "en": "❌ That file isn't an image. Attach a png/jpg so I can analyze it.",
    },
    "ai_header": {
        "ar": "🤖 **مستشار لوردس**",
        "en": "🤖 **Lords Advisor**",
    },
    "ai_footer": {
        "ar": "🗣️ سؤال {user}",
        "en": "🗣️ Asked by {user}",
    },
    "ai_error": {
        "ar": "⚠️ حصل خطأ أثناء التواصل مع خدمة الـ AI. حاول تاني بعد شوية.\n(تفاصيل تقنية: {err})",
        "en": "⚠️ Something went wrong talking to the AI service. Try again shortly.\n(technical: {err})",
    },
    "ai_mention_error": {
        "ar": "⚠️ حصل خطأ أثناء معالجة السؤال. جرّب تاني بعد شوية.",
        "en": "⚠️ Something went wrong while processing your question. Please try again shortly.",
    },
    "ai_cooldown": {
        "ar": "⏳ استنى شوية ({s} ثانية) قبل ما تسأل تاني.",
        "en": "⏳ Wait a bit ({s}s) before asking again.",
    },
    "ai_might_line": {
        "ar": "قوة الحساب (Might) اللي ذكرها اللاعب: {might}",
        "en": "Player-reported account Might: {might}",
    },
    # زرار "اسأل المستشار الذكي" - بيتضاف تحت نتيجة أي حاسبة (حدث/تسريعات/كاونتر...)
    "calc_ai_advice_button": {"ar": "🤖 اسأل المستشار الذكي", "en": "🤖 Ask the AI advisor"},
    "calc_ai_advice_default_question": {
        "ar": "بناءً على الأرقام والنتيجة دي، إيه أفضل نصيحة أو استراتيجية تقترحها عليّ؟",
        "en": "Based on these numbers and this result, what's your best advice or strategy?",
    },
    "calc_ai_advice_footer": {
        "ar": "💡 نصيحة الذكاء الاصطناعي مكمّلة للحاسبة، مش بديل لقرارك",
        "en": "💡 AI advice complements the calculator - it's not a substitute for your own call",
    },
    # /play
    "play_wrong_channel": {
        "ar": "🎮 اللعبة دي مخصصة لقناة الألعاب بس: <#{channel}>",
        "en": "🎮 This game is restricted to the games channel: <#{channel}>",
    },
    "play_title": {"ar": "🎮 خمّن الاسم!", "en": "🎮 Guess the name!"},
    "play_category": {"ar": "الفئة", "en": "Category"},
    "play_hint": {"ar": "💡 تلميح", "en": "💡 Hint"},
    "play_footer": {
        "ar": "اضغط الزرار وابعت تخمينك - عندك 30 ثانية!",
        "en": "Press the button and send your guess - you have 30 seconds!",
    },
    "play_guess_button": {"ar": "🎯 خمّن الاسم", "en": "🎯 Guess the name"},
    "play_modal_title": {"ar": "🎯 خمّن الاسم", "en": "🎯 Guess the name"},
    "play_modal_label": {"ar": "اكتب اسم العنصر", "en": "Type the item's name"},
    "play_already_solved": {
        "ar": "⏳ الجولة خلصت بالفعل، استنى الجولة الجاية!",
        "en": "⏳ This round is already over, wait for the next one!",
    },
    "play_wrong": {"ar": "❌ غلط، جرب تاني!", "en": "❌ Wrong, try again!"},
    "play_correct_msg": {"ar": "🎉 إجابة صحيحة!", "en": "🎉 Correct answer!"},
    "play_win_title": {"ar": "✅ {user} خمّن صح!", "en": "✅ {user} guessed it!"},
    "play_answer_was": {"ar": "الإجابة كانت", "en": "The answer was"},
    "play_score_footer": {
        "ar": "رصيده دلوقتي: {points} نقطة | رتبته: {rank}",
        "en": "Current score: {points} pts | Rank: {rank}",
    },
    "play_timeout_title": {"ar": "⏰ خلص الوقت!", "en": "⏰ Time's up!"},
    "play_timeout_desc": {
        "ar": "محدش خمّن صح. الإجابة كانت: {answer}",
        "en": "Nobody guessed correctly. The answer was: {answer}",
    },
    "play_cooldown": {
        "ar": "⏳ استنى شوية قبل ما تلعب تاني ({s} ثانية).",
        "en": "⏳ Wait a bit before playing again ({s}s).",
    },
    # /troop, /rally
    "troop_set_success": {
        "ar": "✅ تم تسجيل نوع قواتك الأساسي: {troop}",
        "en": "✅ Your main troop type is set to: {troop}",
    },
    "rally_no_troop_note": {
        "ar": "\n(ℹ️ الأعضاء اللي لسه ما سجّلوش نوع قواتهم بـ `/troop set` مش هيوصلهم تنبيه مباشر.)",
        "en": "\n(ℹ️ Members who haven't registered their troop type with `/troop set` won't get a direct ping.)",
    },
    "rally_title": {"ar": "🚨📯 نداء حشد!", "en": "🚨📯 Rally call!"},
    "rally_desc": {
        "ar": "{leader} فاتح حشد وعايز **{troop}** بالتحديد!\n⏰ هيتقفل تقريباً: {countdown}",
        "en": "{leader} opened a rally and needs **{troop}** specifically!\n⏰ Closing around: {countdown}",
    },
    "rally_note_field": {"ar": "📝 ملاحظة", "en": "📝 Note"},
    "rally_no_matches": {
        "ar": "محدش مسجّل بنوع القوات ده لسه - سجّل نوعك بـ `/troop set` عشان توصلك التنبيهات دي.",
        "en": "Nobody is registered with this troop type yet - use `/troop set` so you get pinged for these.",
    },
    "rally_open_app": {"ar": "📲 افتح التطبيق", "en": "📲 Open the app"},
    "rally_pinged": {"ar": "🔔 تم استدعاء", "en": "🔔 Pinged"},

    # rally_cog.py - /rally set (نسخة @everyone: هدف الحشد + صورة)
    "rally_desc_v2": {
        "ar": "⚠️ {leader} فاتح حشد وعايز **{troop}**!\n⏰ هيتقفل تقريباً: {countdown}",
        "en": "⚠️ {leader} opened a rally and needs **{troop}**!\n⏰ Closing around: {countdown}",
    },
    "rally_target_field": {"ar": "🎯 هدف الحشد (تحالف/شخص)", "en": "🎯 Rally target (alliance/player)"},
    "rally_footer_v2": {"ar": "فتحه: {leader}", "en": "Opened by: {leader}"},
    "rally_everyone_ping": {
        "ar": "🚨🔔 حشد جديد اتفتح - يلا انضموا بسرعة! ⚠️",
        "en": "🚨🔔 A new rally is open - join quickly! ⚠️",
    },

    # ------------------------------------------------------------------
    # rally_cog.py - /rally_log + RallyLogView (جزء تصليح - كان ناقص بالكامل)
    # ------------------------------------------------------------------
    "rally_log_prompt": {
        "ar": "اختر الأعضاء المشاركين في الحشد من القائمة تحت، وبعدين دوس **تأكيد التسجيل**:",
        "en": "Choose the members who took part in the rally from the list below, then press "
              "**Confirm log**:",
    },
    "rally_log_admin_only": {
        "ar": "❌ الأمر ده مخصص للإدارة فقط (صلاحية Manage Server).",
        "en": "❌ This command is for admins only (requires Manage Server permission).",
    },
    "rally_select_placeholder": {
        "ar": "اختر الأعضاء المشاركين في الحشد...",
        "en": "Choose the members who took part in the rally...",
    },
    "rally_select_confirm_hint": {
        "ar": "✅ اخترت **{count}** عضو. دوس زرار \"تأكيد التسجيل\" تحت عشان تحفظ.",
        "en": "✅ You selected **{count}** members. Press \"Confirm log\" below to save.",
    },
    "rally_confirm_button": {"ar": "✅ تأكيد التسجيل", "en": "✅ Confirm log"},
    "rally_log_need_member": {
        "ar": "❌ لازم تختار عضو واحد على الأقل قبل التأكيد.",
        "en": "❌ You must select at least one member before confirming.",
    },
    "rally_log_success_title": {"ar": "✅ تم تسجيل حضور الحشد", "en": "✅ Rally attendance logged"},
    "rally_log_type_field": {"ar": "🧭 النوع", "en": "🧭 Type"},
    "rally_log_result_field": {"ar": "🏆 النتيجة", "en": "🏆 Result"},
    "rally_log_members_field": {"ar": "👥 الأعضاء المشاركون", "en": "👥 Participating members"},
    "rally_log_footer": {"ar": "سجّله: {by}", "en": "Logged by: {by}"},

    # ------------------------------------------------------------------
    # war_cog.py - /report add (رسالة الـ cooldown كانت ثنائية اللغة inline)
    # ------------------------------------------------------------------
    "report_cooldown": {
        "ar": "⏳ استنى شوية قبل ما تسجّل تقرير تاني ({seconds:.0f} ثانية).",
        "en": "⏳ Please wait {seconds:.0f}s before logging another report.",
    },

    # ------------------------------------------------------------------
    # events_cog.py - fmt_minutes() helper
    # ------------------------------------------------------------------
    "fmt_unit_day": {"ar": "يوم", "en": "day"},
    "fmt_unit_hour": {"ar": "ساعة", "en": "hour"},
    "fmt_unit_minute": {"ar": "دقيقة", "en": "minute"},
    "fmt_joiner": {"ar": " و ", "en": ", "},
    "rally_log_mentions_joiner": {"ar": "، ", "en": ", "},

    # ------------------------------------------------------------------
    # events_cog.py - /event
    # ------------------------------------------------------------------
    "event_category_prompt": {
        "ar": "اختر نوع الحدث الأول 👇",
        "en": "First, choose the event type 👇",
    },
    "event_category_select_placeholder": {"ar": "اختر الحدث...", "en": "Choose the event..."},
    "event_prompt": {
        "ar": "📌 {category}\nدلوقتي اختر نوع النشاط اللي عايز تحسبه من القائمة تحت 👇",
        "en": "📌 {category}\nNow choose the activity type you want to calculate from the list below 👇",
    },
    "event_select_placeholder": {"ar": "اختر نوع النشاط داخل الحدث...", "en": "Choose the activity within the event..."},
    "event_modal_title": {"ar": "🧮 حاسبة الحدث", "en": "🧮 Event calculator"},
    "event_field_required_points": {"ar": "🎯 النقاط المطلوبة للمرحلة", "en": "🎯 Points required for the stage"},
    "event_field_points_per_action": {"ar": "✨ النقاط لكل مرّة/فعل", "en": "✨ Points per action"},
    "event_field_time_per_action": {
        "ar": "⏱️ الوقت اللازم لكل مرة (بالدقائق)",
        "en": "⏱️ Time needed per action (in minutes)",
    },
    "event_field_speedups": {
        "ar": "🚀 إجمالي التسريعات المتاحة (بالدقائق)",
        "en": "🚀 Total speedups available (in minutes)",
    },
    "event_placeholder_required_points": {"ar": "مثال: 500000", "en": "e.g.: 500000"},
    "event_placeholder_points_per_action": {"ar": "مثال: 1000", "en": "e.g.: 1000"},
    "event_placeholder_time_per_action": {"ar": "مثال: 30", "en": "e.g.: 30"},
    "event_placeholder_speedups": {"ar": "مثال: 4320", "en": "e.g.: 4320"},
    "event_invalid_numbers": {
        "ar": "❌ من فضلك أدخل أرقام صحيحة وأكبر من صفر.",
        "en": "❌ Please enter valid numbers greater than zero.",
    },
    "event_result_title": {"ar": "🧮 نتيجة حاسبة: {label}", "en": "🧮 Calculator result: {label}"},
    "event_required_points_field": {"ar": "🎯 النقاط المطلوبة", "en": "🎯 Points required"},
    "event_points_per_action_field": {"ar": "✨ نقاط/فعل", "en": "✨ Points/action"},
    "event_actions_needed_field": {"ar": "🔁 عدد الأفعال المطلوبة", "en": "🔁 Actions needed"},
    "event_total_time_field": {"ar": "⏱️ الوقت الكلي المطلوب", "en": "⏱️ Total time needed"},
    "event_speedups_available_field": {"ar": "🚀 التسريعات المتاحة", "en": "🚀 Speedups available"},
    "event_can_complete_field": {"ar": "✅ النتيجة", "en": "✅ Result"},
    "event_can_complete_value": {"ar": "تقدر تكمل الحدث بالكامل!", "en": "You can complete the event fully!"},
    "event_remaining_speedups_field": {
        "ar": "🎁 المتبقي من التسريعات بعد الإكمال",
        "en": "🎁 Speedups remaining after completion",
    },
    "event_cannot_complete_field": {"ar": "⚠️ النتيجة", "en": "⚠️ Result"},
    "event_cannot_complete_value": {
        "ar": "لن تكمل المرحلة بالتسريعات الحالية وحدها.",
        "en": "You won't complete the stage with your current speedups alone.",
    },
    "event_percentage_field": {"ar": "📊 نسبة الإنجاز الممكنة حالياً", "en": "📊 Currently achievable progress"},
    "event_achievable_points_field": {"ar": "🏁 النقاط اللي هتوصلها", "en": "🏁 Points you'll reach"},
    "event_missing_points_field": {"ar": "❗ النقاط اللي هتفضل ناقصة", "en": "❗ Points you'll still be missing"},
    "event_extra_time_field": {
        "ar": "⏳ وقت/تسريعات إضافية مطلوبة لإكمالها",
        "en": "⏳ Extra time/speedups needed to finish",
    },
    "event_footer": {"ar": "Lords Mobile Companion Bot", "en": "Lords Mobile Companion Bot"},

    # ------------------------------------------------------------------
    # events_cog.py - /shelter
    # ------------------------------------------------------------------
    "shelter_prompt": {"ar": "اختر مدة حماية المخبأ:", "en": "Choose the shelter duration:"},
    "shelter_4h_button": {"ar": "4 ساعات", "en": "4 hours"},
    "shelter_8h_button": {"ar": "8 ساعات", "en": "8 hours"},
    "shelter_12h_button": {"ar": "12 ساعة", "en": "12 hours"},
    "shelter_started": {
        "ar": "🛡️ تم تفعيل حماية المخبأ لمدة **{hours} ساعات**.\n"
              "⏰ هينتهي تقريباً الساعة `{end_time}`.\n"
              "🔔 هوصلك تنبيه هنا وبرسالة خاصة قبل الانتهاء بـ 15 دقيقة.",
        "en": "🛡️ Shelter protection activated for **{hours} hours**.\n"
              "⏰ It will end around `{end_time}`.\n"
              "🔔 You'll get a reminder here and by DM 15 minutes before it ends.",
    },
    "shelter_reminder_text": {
        "ar": "⏰ تنبيه: حماية المخبأ ({hours} ساعات) هتنتهي خلال **15 دقيقة**! جهّز جيشك 🛡️",
        "en": "⏰ Reminder: shelter protection ({hours} hours) ends in **15 minutes**! Get your troops ready 🛡️",
    },

    # ------------------------------------------------------------------
    # events_cog.py - /cost
    # ------------------------------------------------------------------
    "cost_prompt": {"ar": "اختر نوع التكلفة اللي عايز تحسبها:", "en": "Choose the cost type you want to calculate:"},
    "cost_tier_select_placeholder": {
        "ar": "اختر نوع التكلفة المطلوب حسابها...",
        "en": "Choose the cost type to calculate...",
    },
    "cost_tier_t4": {"ar": "⚔️ تدريب T4", "en": "⚔️ Training T4"},
    "cost_tier_t5": {"ar": "⚔️ تدريب T5", "en": "⚔️ Training T5"},
    "cost_tier_research": {"ar": "🎓 أبحاث الأكاديمية", "en": "🎓 Academy research"},
    "cost_modal_title": {"ar": "💰 حاسبة تكلفة التدريب", "en": "💰 Training cost calculator"},
    "cost_field_quantity": {"ar": "🔢 عدد الوحدات المطلوب تدريبها", "en": "🔢 Number of units to train"},
    "cost_field_food": {"ar": "🍖 تكلفة الطعام لكل وحدة", "en": "🍖 Food cost per unit"},
    "cost_field_wood_stone": {"ar": "🪵 تكلفة الخشب/الحجر لكل وحدة", "en": "🪵 Wood/stone cost per unit"},
    "cost_field_ore_gold": {"ar": "⛏️ تكلفة الخام/الذهب لكل وحدة", "en": "⛏️ Ore/gold cost per unit"},
    "cost_field_time_per_unit": {
        "ar": "⏱️ زمن الوحدة (ثانية) وعدد الطوابير",
        "en": "⏱️ Time per unit (seconds) and number of queues",
    },
    "cost_invalid_numbers": {
        "ar": "❌ تأكد من إدخال أرقام صحيحة، وخانة الزمن بصيغة: الزمن,عدد الطوابير (مثال: 12,2)",
        "en": "❌ Make sure you enter valid numbers, and the time field as: time,queues (example: 12,2)",
    },
    "cost_result_title": {"ar": "💰 تكلفة تدريب: {tier}", "en": "💰 Training cost: {tier}"},
    "cost_quantity_field": {"ar": "🔢 عدد الوحدات", "en": "🔢 Number of units"},
    "cost_total_food_field": {"ar": "🍖 إجمالي الطعام", "en": "🍖 Total food"},
    "cost_total_wood_stone_field": {"ar": "🪵 إجمالي الخشب/الحجر", "en": "🪵 Total wood/stone"},
    "cost_total_ore_gold_field": {"ar": "⛏️ إجمالي الخام/الذهب", "en": "⛏️ Total ore/gold"},
    "cost_total_time_field": {"ar": "⏱️ الزمن الكلي التقريبي", "en": "⏱️ Approximate total time"},
    "cost_footer": {
        "ar": "القيم المدخلة تقريبية حسب بيانات المستخدم - راجع الأكاديمية للأرقام الدقيقة",
        "en": "Entered values are approximate based on user input - check the Academy for exact numbers",
    },

    # ------------------------------------------------------------------
    # events_cog.py - /speedup
    # ------------------------------------------------------------------
    "speedup_modal_title": {"ar": "🚀 حاسبة التسريعات", "en": "🚀 Speedup calculator"},
    "speedup_field_entries": {"ar": "🚀 التسريعات (مثال: 4h, 6h, 1d×3)", "en": "🚀 Speedups (e.g. 4h, 6h, 1d×3)"},
    "speedup_field_entries_placeholder": {
        "ar": "اكتب كل تسريعة وافصل بينهم بفاصلة، مثال: 4h, 6h, 1d×3 أو 24×4, 3d×2",
        "en": "Write each speedup separated by commas, e.g. 4h, 6h, 1d×3 or 24×4, 3d×2",
    },
    "speedup_invalid_numbers": {
        "ar": "❌ ما قدرتش أفهم أي رقم صحيح. اكتب بصيغة زي: 4h, 6h, 1d×3",
        "en": "❌ Couldn't understand any valid entry. Use a format like: 4h, 6h, 1d×3",
    },
    "speedup_result_title": {"ar": "🚀 إجمالي التسريعات المتاحة", "en": "🚀 Total speedups available"},
    "speedup_breakdown_field": {"ar": "📋 تفصيل كل بند", "en": "📋 Breakdown"},
    "speedup_errors_field": {"ar": "⚠️ بنود ما اتفهمتش", "en": "⚠️ Entries not understood"},
    "speedup_in_minutes_field": {"ar": "🔢 بالدقائق", "en": "🔢 In minutes"},
    "speedup_in_hours_field": {"ar": "🕐 بالساعات", "en": "🕐 In hours"},
    "speedup_minutes_unit": {"ar": "دقيقة", "en": "minutes"},
    "speedup_hours_unit": {"ar": "ساعة", "en": "hours"},

    # مشترك بين أكتر من أمر
    "err_invalid_numbers": {
        "ar": "❌ أدخل أرقام صحيحة فقط.",
        "en": "❌ Please enter valid numbers only.",
    },

    # /language, /set_game_link, /game_link
    "lang_set_ar_full": {
        "ar": "✅ تم تغيير لغة البوت في السيرفر ده إلى **العربية**.",
        "en": "✅ تم تغيير لغة البوت في السيرفر ده إلى **العربية**.",
    },
    "lang_set_en_full": {
        "ar": "✅ Bot language for this server switched to **English**.\n"
              "ℹ️ ملحوظة: أسماء ووصف الأوامر نفسها (اللي بتظهر لما تكتب / في ديسكورد) بتتحدد من إعدادات "
              "ديسكورد بتاعك مش من الأمر ده - ده تحكّم في ردود ولوحات البوت (الأزرار، القوائم، الرسائل) بس.",
        "en": "✅ Bot language for this server switched to **English**.\n"
              "ℹ️ Note: the command names/descriptions Discord shows you when typing `/` are controlled by "
              "your own Discord client language, not by this setting - this controls the bot's actual replies "
              "and menus (buttons, dropdowns, messages) instead.",
    },
    "lang_me_set": {
        "ar": "✅ تم ضبط ردود البوت لك على **العربية**. أي أمر تستخدمه هيرد عليك بالعربي.",
        "en": "✅ Your bot replies are now set to **English**. Commands you use will reply in English.",
    },
    "gamelink_bad_url": {
        "ar": "❌ الرابط لازم يبدأ بـ http:// أو https://",
        "en": "❌ The link must start with http:// or https://",
    },
    "gamelink_set_confirm": {
        "ar": "✅ تم ضبط رابط فتح اللعبة لهذا السيرفر:\n{link}\n"
              "هيتستخدم دلوقتي في زرار \"📲 افتح اللعبة\" بأوامر التنبيهات (زي /rally set و/shield).",
        "en": "✅ The game link for this server is set to:\n{link}\n"
              "It will now be used by the \"📲 Open the game\" button in alert commands (like /rally set and /shield).",
    },
    "gamelink_admin_only": {
        "ar": "❌ الأمر ده مخصص للإدارة فقط (صلاحية Manage Server).",
        "en": "❌ This command is admin-only (requires Manage Server permission).",
    },
    "gamelink_current": {
        "ar": "📲 رابط فتح اللعبة الحالي:\n{link}",
        "en": "📲 Current game link:\n{link}",
    },
    "unexpected_error": {
        "ar": "❌ حصل خطأ غير متوقع.",
        "en": "❌ Unexpected error.",
    },

    # /jewel_calc
    "jewel_pick_target": {
        "ar": "اختر تاير الجوهر المستهدف اللي عايز تحسب المطلوب للوصول له 👇",
        "en": "Choose the target jewel tier you want to calculate requirements for 👇",
    },
    "jewel_select_placeholder": {
        "ar": "اختر التاير المستهدف (افتراضياً وصولاً للخرافي)...",
        "en": "Choose the target tier (e.g. all the way to Mythic)...",
    },
    "jewel_modal_title": {"ar": "💎 حاسبة دمج الجواهر", "en": "💎 Jewel Merge Calculator"},
    "jewel_field_qty": {
        "ar": "🎯 عدد الجواهر المطلوبة من التاير المستهدف",
        "en": "🎯 Number of jewels needed at the target tier",
    },
    "jewel_field_ratio": {
        "ar": "🔁 كام جوهر من التاير الأقل = 1 من اللي فوقه؟",
        "en": "🔁 How many lower-tier jewels merge into 1 of the next tier?",
    },
    "jewel_field_rate": {
        "ar": "🎲 نسبة نجاح الدمج % (سيبها 100 لو مضمونة)",
        "en": "🎲 Merge success rate % (leave as 100 if guaranteed)",
    },
    "jewel_err": {
        "ar": "❌ تأكد إن العدد ونسبة الدمج أرقام أكبر من صفر، ونسبة النجاح بين 1 و100.",
        "en": "❌ Make sure quantity and merge ratio are numbers greater than zero, and the success rate is between 1 and 100.",
    },
    "jewel_title": {
        "ar": "💎 حاسبة دمج الجواهر - المستهدف: {target}",
        "en": "💎 Jewel Merge Calculator - Target: {target}",
    },
    "jewel_qty_field": {"ar": "🎯 الكمية المطلوبة", "en": "🎯 Quantity needed"},
    "jewel_ratio_field": {"ar": "🔁 نسبة الدمج", "en": "🔁 Merge ratio"},
    "jewel_rate_field": {"ar": "🎲 نسبة النجاح", "en": "🎲 Success rate"},
    "jewel_breakdown_field": {
        "ar": "📊 التفصيل تاير بتاير (من الهدف لغاية Common)",
        "en": "📊 Tier-by-tier breakdown (from target down to Common)",
    },
    "jewel_total_field": {
        "ar": "⚪ إجمالي جواهر Common اللي محتاجها",
        "en": "⚪ Total Common jewels you'll need",
    },
    "jewel_footer": {
        "ar": "القيم تقريبية حسب نسبة الدمج ونسبة النجاح اللي دخّلتها - راجع نافذة الدمج في اللعبة للتأكد.",
        "en": "Values are estimates based on the ratio and success rate you entered - check the merge window in-game to confirm.",
    },

    # /darknest
    "darknest_prompt": {
        "ar": "اختر مستوى الحصن المظلم:",
        "en": "Choose the Dark Nest level:",
    },
    "darknest_select_placeholder": {
        "ar": "اختر مستوى الحصن المظلم...",
        "en": "Choose the Dark Nest level...",
    },
    "darknest_title": {
        "ar": "🏯 الحصن المظلم - المستوى {lvl}",
        "en": "🏯 Dark Nest - Level {lvl}",
    },
    "darknest_heroes_field": {"ar": "🦸 الأبطال المقترحون", "en": "🦸 Suggested heroes"},
    "darknest_formation_field": {"ar": "🧩 التشكيلة", "en": "🧩 Formation"},
    "darknest_notes_field": {"ar": "📝 ملاحظات", "en": "📝 Notes"},
    "darknest_footer": {
        "ar": "بيانات إرشادية عامة - حدّثها حسب آخر meta لديك",
        "en": "General reference info - adjust based on your current meta",
    },

    # /gear
    "gear_choose_troop": {"ar": "اختر نوع القوات:", "en": "Choose your troop type:"},
    "gear_troop_select_placeholder": {"ar": "اختر نوع القوات...", "en": "Choose troop type..."},
    "gear_choose_player_type": {
        "ar": "اخترت {troop} - دلوقتي اختر فئة اللاعب:",
        "en": "You picked {troop} - now choose your player type:",
    },
    "gear_result_title": {
        "ar": "{emoji} أفضل عتاد لـ {troop} ({kind})",
        "en": "{emoji} Best gear for {troop} ({kind})",
    },

    # /counter
    "counter_prompt": {
        "ar": "اضغط الزر تحت وأدخل بيانات تشكيلة العدو 👇",
        "en": "Press the button below and enter the enemy formation details 👇",
    },
    "counter_button": {"ar": "أدخل تشكيلة العدو", "en": "Enter enemy formation"},
    "counter_modal_title": {"ar": "⚔️ حاسبة التشكيلة المضادة", "en": "⚔️ Counter Formation Calculator"},
    "counter_field_infantry": {"ar": "🛡️ نسبة/عدد المشاة عند العدو", "en": "🛡️ Enemy infantry ratio/count"},
    "counter_field_ranged": {"ar": "🏹 نسبة/عدد الرماة عند العدو", "en": "🏹 Enemy ranged ratio/count"},
    "counter_field_cavalry": {"ar": "🐎 نسبة/عدد الفرسان عند العدو", "en": "🐎 Enemy cavalry ratio/count"},
    "counter_field_siege": {"ar": "🏰 نسبة/عدد الحصار عند العدو", "en": "🏰 Enemy siege ratio/count"},
    "counter_title": {"ar": "⚔️ التشكيلة المضادة المقترحة", "en": "⚔️ Suggested counter formation"},
    "counter_input_field": {"ar": "📊 تشكيلة العدو المدخلة", "en": "📊 Entered enemy formation"},
    "counter_dominant_field": {"ar": "🎯 النوع الغالب عند العدو", "en": "🎯 Enemy's dominant troop type"},
    "counter_suggestion_field": {"ar": "✅ الوحدات المقترحة للرد", "en": "✅ Suggested response troops"},
    "counter_formation_field": {"ar": "🧩 التشكيلة التكتيكية المقترحة", "en": "🧩 Suggested tactical formation"},
    "counter_footer": {
        "ar": "قاعدة عامة تقريبية - اضبطها حسب أبطالك وعتادك الفعلي",
        "en": "A rough general rule - adjust it based on your actual heroes and gear",
    },
    "counter_mixed": {"ar": "مزيج متوازن", "en": "A balanced mix"},

    # /report
    "report_group_desc": {"ar": "📝 تسجيل واستدعاء سجل المعارك", "en": "📝 Log and view the battle record"},
    "report_modal_title": {"ar": "📝 تسجيل معركة", "en": "📝 Log a battle"},
    "report_field_opponent": {"ar": "👤 اسم الخصم", "en": "👤 Opponent name"},
    "report_field_result": {"ar": "🏆 النتيجة (فوز/خسارة/تعادل)", "en": "🏆 Result (win/loss/draw)"},
    "report_field_notes": {"ar": "📋 تفاصيل إضافية", "en": "📋 Extra details"},
    "report_saved_title": {"ar": "✅ تم تسجيل المعركة", "en": "✅ Battle logged"},
    "report_opponent_field": {"ar": "👤 الخصم", "en": "👤 Opponent"},
    "report_result_field": {"ar": "🏆 النتيجة", "en": "🏆 Result"},
    "report_notes_field": {"ar": "📋 ملاحظات", "en": "📋 Notes"},
    "report_none_yet": {"ar": "لا يوجد أي معارك مسجلة بعد.", "en": "No battles logged yet."},
    "report_none_for_user": {
        "ar": "لا توجد معارك مسجلة بواسطة {member}.",
        "en": "No battles logged by {member}.",
    },
    "report_list_title": {"ar": "📚 سجل المعارك", "en": "📚 Battle log"},
    "report_user_title": {"ar": "📚 سجل معارك {member}", "en": "📚 {member}'s battle log"},
    "report_vs": {"ar": "{result} ضد {opponent}", "en": "{result} vs {opponent}"},
    "report_by_line": {
        "ar": "✍️ بواسطة: {author} | 📋 {notes}\n🕒 {time}",
        "en": "✍️ Logged by: {author} | 📋 {notes}\n🕒 {time}",
    },
    "report_notes_line": {"ar": "📋 {notes}\n🕒 {time}", "en": "📋 {notes}\n🕒 {time}"},

    # /colo
    "colo_modal_title": {"ar": "🏟️ محاكي الكولوسيوم", "en": "🏟️ Colosseum Simulator"},
    "colo_field_heroes": {
        "ar": "🦸 أبطال الخصم (افصل بفاصلة)",
        "en": "🦸 Opponent heroes (comma-separated)",
    },
    "colo_result_title": {"ar": "🏟️ نتيجة محاكي الكولوسيوم", "en": "🏟️ Colosseum simulator result"},
    "colo_vs_field": {"ar": "🦸 ضد {hero}", "en": "🦸 Against {hero}"},
    "colo_no_data": {
        "ar": "لا توجد بيانات محدّدة لهذا البطل بعد - اتبع القاعدة العامة تحت.",
        "en": "No specific data for this hero yet - follow the general rule below.",
    },
    "colo_general_rule_field": {"ar": "📜 القاعدة العامة", "en": "📜 General rule"},

    # /analyze
    "analyze_bad_image": {"ar": "❌ الملف المرفق لازم يكون صورة.", "en": "❌ The attached file must be an image."},
    "analyze_with_image_note": {
        "ar": "📎 تم إرفاق الصورة: {filename}\n"
              "ملحوظة: البوت لسه مش بيقرأ أرقام من الصور تلقائياً، فأدخل نسب/أعداد قوات الخصم "
              "اللي شايفها في التقرير يدوياً في النافذة الجاية 👇",
        "en": "📎 Image attached: {filename}\n"
              "Note: the bot doesn't automatically read numbers from images yet, so enter the enemy troop "
              "ratios/counts you see in the report manually in the next window 👇",
    },
    "analyze_no_image_note": {
        "ar": "أدخل نسب/أعداد قوات الخصم من تقرير المعركة 👇",
        "en": "Enter the enemy troop ratios/counts from the battle report 👇",
    },

    # /help
    "help_title": {"ar": "📖 دليل بوت Lords Mobile الكامل", "en": "📖 Lords Mobile Bot - Full Guide"},
    "help_intro": {
        "ar": "أهلاً بيك! 👋 البوت ده مجهّز بكل حاجة يحتاجها التحالف: حواسب، أدوات حرب، أدلة، تتبع نشاط، "
              "وأكتر. اختر قسم من القائمة تحت 👇 عشان تشوف كل أوامره بالتفصيل.",
        "en": "Welcome! 👋 This bot is packed with everything the alliance needs: calculators, war tools, "
              "guides, activity tracking, and more. Pick a category from the menu below 👇 to see all its "
              "commands in detail.",
    },
    "help_overview_field": {"ar": "📂 الأقسام المتاحة", "en": "📂 Available categories"},
    "help_select_placeholder": {"ar": "اختر قسم عشان تشوف أوامره...", "en": "Choose a category to see its commands..."},
    "help_footer": {
        "ar": "Lords Mobile Companion Bot | 🌐 غيّر اللغة بأمر /language",
        "en": "Lords Mobile Companion Bot | 🌐 Change language with /language",
    },

    # ------------------------------------------------------------------
    # مشترك بين كذا أمر - نفس رسالة الخطأ العامة المستخدمة في /language و/set_game_link
    # (راجع "unexpected_error" فوق)
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # guild_cog.py - جزء 4: /quiz
    # ------------------------------------------------------------------
    "rank_beginner": {"ar": "🥉 مبتدئ", "en": "🥉 Beginner"},
    "rank_active_contributor": {"ar": "🥈 مساهم نشط", "en": "🥈 Active contributor"},
    "rank_field_leader": {"ar": "🥇 قائد ميداني", "en": "🥇 Field leader"},
    "rank_lords_expert": {"ar": "🧠 خبير لوردس", "en": "🧠 Lords expert"},
    "quiz_embed_title": {
        "ar": "🧠 سؤال مسابقة لوردس موبايل",
        "en": "🧠 Lords Mobile quiz question",
    },
    "quiz_embed_footer": {
        "ar": "عندك 30 ثانية للإجابة!",
        "en": "You have 30 seconds to answer!",
    },
    "quiz_already_answered": {
        "ar": "إنت جاوبت على السؤال ده بالفعل!",
        "en": "You've already answered this question!",
    },
    "quiz_correct": {"ar": "✅ إجابة صحيحة!", "en": "✅ Correct answer!"},
    "quiz_wrong": {"ar": "❌ إجابة غلط.", "en": "❌ Wrong answer."},
    "quiz_result_footer": {
        "ar": "{msg} رصيدك دلوقتي: **{points}** نقطة | رتبتك: {rank}",
        "en": "{msg} Your current score: **{points}** pts | Rank: {rank}",
    },

    # ------------------------------------------------------------------
    # guild_cog.py - جزء 5: /user_admin_check
    # ------------------------------------------------------------------
    "admin_check_prompt": {
        "ar": "اختر العضو اللي عايز تراجع سجله من القائمة تحت:",
        "en": "Choose the member whose record you want to review from the list below:",
    },
    "admin_check_select_placeholder": {
        "ar": "اختر العضو اللي عايز تراجع سجله...",
        "en": "Choose the member to review...",
    },
    "admin_check_permission_denied": {
        "ar": "❌ الأمر ده مخصص للإدارة فقط (صلاحية Manage Server).",
        "en": "❌ This command is for admins only (requires Manage Server permission).",
    },
    "admin_dashboard_title": {
        "ar": "🛡️ لوحة المتابعة الإدارية: {name}",
        "en": "🛡️ Admin follow-up dashboard: {name}",
    },
    "admin_dashboard_events_field": {
        "ar": "📋 سجل الأحداث (/log_activity)",
        "en": "📋 Event log (/log_activity)",
    },
    "admin_dashboard_events_value": {
        "ar": "👥 حشود: {rally}\n🎉 مهرجان التحالف: {guild_fest} ({gf_completed} مهمة مكتملة)\n"
              "🐉 ساحة التنين: {dragon_arena}\n⚔️ KvK: {kvk}",
        "en": "👥 Rallies: {rally}\n🎉 Alliance Festival: {guild_fest} ({gf_completed} completed tasks)\n"
              "🐉 Dragon Arena: {dragon_arena}\n⚔️ KvK: {kvk}",
    },
    "admin_dashboard_rally_field": {
        "ar": "📯 حضور الحشود (/rally_log)",
        "en": "📯 Rally attendance (/rally_log)",
    },
    "admin_dashboard_rally_value": {
        "ar": "الإجمالي: {total}\n🏆 فوز: {wins}",
        "en": "Total: {total}\n🏆 Wins: {wins}",
    },
    "admin_dashboard_reports_field": {
        "ar": "⚔️ معارك مسجّلة (/report)",
        "en": "⚔️ Logged battles (/report)",
    },
    "admin_dashboard_recent_activities_field": {"ar": "🕒 آخر 5 أنشطة", "en": "🕒 Last 5 activities"},
    "admin_dashboard_recent_rallies_field": {"ar": "🕒 آخر 5 حشود", "en": "🕒 Last 5 rallies"},
    "admin_dashboard_no_data": {
        "ar": "⚠️ مفيش أي سجل مشاركة لهذا العضو لسه.",
        "en": "⚠️ No participation record for this member yet.",
    },

    # ------------------------------------------------------------------
    # guild_cog.py - جزء 6: /information
    # ------------------------------------------------------------------
    "info_profile_title": {"ar": "🪪 ملف العضو: {name}", "en": "🪪 Member profile: {name}"},
    "info_rally_field": {"ar": "👥 مشاركات الحشود", "en": "👥 Rally participation"},
    "info_rally_value": {
        "ar": "الإجمالي: **{total}**\n{attack_label}: {attack} | {defense_label}: {defense}\n{win_label}: {wins}",
        "en": "Total: **{total}**\n{attack_label}: {attack} | {defense_label}: {defense}\n{win_label}: {wins}",
    },
    "info_war_field": {"ar": "⚔️ التزام الحروب", "en": "⚔️ War commitment"},
    "info_war_value": {
        "ar": "مشاركات KvK: **{kvk}**\nمعارك مسجّلة: **{reports}**",
        "en": "KvK participations: **{kvk}**\nLogged battles: **{reports}**",
    },
    "info_events_field": {"ar": "🎉 الفعاليات", "en": "🎉 Events"},
    "info_events_value": {
        "ar": "مهرجان التحالف: {fest} نشاط ({gf_completed} مهمة مكتملة)\nساحة التنين: {dragon}",
        "en": "Alliance Festival: {fest} activities ({gf_completed} completed tasks)\nDragon Arena: {dragon}",
    },
    "info_rank_field": {"ar": "🏅 الرتبة العامة", "en": "🏅 Overall rank"},
    "info_rank_value": {
        "ar": "{rank} — {points} نقطة مشاركة إجمالية",
        "en": "{rank} — {points} total participation points",
    },
    "info_footer": {"ar": "طلب بواسطة {user}", "en": "Requested by {user}"},

    # ------------------------------------------------------------------
    # guild_cog.py - جزء 7: /top5 + /event_stats + gf_reminder
    # ------------------------------------------------------------------
    "top5_no_data": {
        "ar": "لا توجد بيانات مشاركة مسجلة بعد.",
        "en": "No participation data recorded yet.",
    },
    "top5_title": {
        "ar": "🏆 أنشط 5 أعضاء - كل الفعاليات والحشود",
        "en": "🏆 Top 5 most active members - all events & rallies",
    },
    "top5_line": {
        "ar": "{medal} **{name}** — {score} مشاركة إجمالية",
        "en": "{medal} **{name}** — {score} total participations",
    },
    "top5_footer": {
        "ar": "الاحتساب: أنشطة /log_activity + حضور /rally_log + معارك /report",
        "en": "Calculated from: /log_activity activities + /rally_log attendance + /report battles",
    },
    "event_stats_title": {
        "ar": "📊 إحصائية مشاركة التحالف: {name}",
        "en": "📊 Alliance participation report: {name}",
    },
    "event_stats_participated_field": {"ar": "✅ شاركوا", "en": "✅ Participated"},
    "event_stats_participated_value": {
        "ar": "{count}/{total} عضو",
        "en": "{count}/{total} members",
    },
    "event_stats_percentage_field": {"ar": "📈 نسبة المشاركة", "en": "📈 Participation rate"},
    "event_stats_non_participants_field": {
        "ar": "😴 لم يشاركوا ({count})",
        "en": "😴 Didn't participate ({count})",
    },
    "event_stats_extra_suffix": {
        "ar": " (+{count} إضافي)",
        "en": " (+{count} more)",
    },
    "gf_reminder_text": {
        "ar": "⏰ تنبيه: مهمة **{task}** الخاصة بـ {member} هتنتهي خلال {minutes} دقيقة! 🎉",
        "en": "⏰ Reminder: task **{task}** for {member} is due in {minutes} minutes! 🎉",
    },

    # ------------------------------------------------------------------
    # guild_cog.py - جزء 8: /reset_stats + ResetConfirmView + setup()
    # ------------------------------------------------------------------
    "reset_confirm_prompt": {
        "ar": "⚠️ متأكد إنك عايز تصفّر كل سجلات النشاط والمسابقة لهذا السيرفر؟ الإجراء ده لا يمكن التراجع عنه.",
        "en": "⚠️ Are you sure you want to reset all activity and quiz records for this server? "
              "This action cannot be undone.",
    },
    "reset_admin_only_full": {
        "ar": "❌ الأمر ده للإدارة فقط (Administrator).",
        "en": "❌ This command is admin-only (Administrator permission).",
    },
    "reset_confirm_admin_only": {
        "ar": "❌ الأمر ده للإدارة فقط.",
        "en": "❌ This command is admin-only.",
    },
    "reset_confirm_yes_button": {"ar": "نعم، صفّر كل شيء", "en": "Yes, reset everything"},
    "reset_confirm_cancel_button": {"ar": "إلغاء", "en": "Cancel"},
    "reset_confirm_success": {
        "ar": "✅ تم تصفير كل السجلات لهذا السيرفر.",
        "en": "✅ All records for this server have been reset.",
    },
    "reset_confirm_cancelled": {"ar": "تم الإلغاء.", "en": "Cancelled."},

    # ------------------------------------------------------------------
    # guild_cog.py - جزء 1: الرتب + /log_activity
    # ------------------------------------------------------------------
    "log_activity_modal_title": {"ar": "📋 تسجيل مشاركة", "en": "📋 Log participation"},
    "log_activity_details_label": {"ar": "📝 التفاصيل", "en": "📝 Details"},
    "log_activity_reason_label": {"ar": "❓ السبب/الملاحظة", "en": "❓ Reason/note"},
    "log_activity_success_title": {"ar": "✅ تم تسجيل المشاركة", "en": "✅ Participation logged"},
    "log_activity_member_field": {"ar": "👤 العضو", "en": "👤 Member"},
    "log_activity_type_field": {"ar": "🏷️ النشاط", "en": "🏷️ Activity"},
    "log_activity_details_field": {"ar": "📝 التفاصيل", "en": "📝 Details"},
    "activity_select_placeholder": {"ar": "اختر نوع النشاط...", "en": "Choose the activity type..."},
    "log_activity_prompt": {
        "ar": "سجّل نشاط للعضو {member} - اختر النوع:",
        "en": "Logging activity for {member} - choose the type:",
    },
    "log_activity_admin_only": {
        "ar": "❌ الأمر ده مخصص لقيادة التحالف فقط (يحتاج صلاحية Manage Server) عشان محدش يسجّل بيانات غلط على غيره.",
        "en": "❌ This command is for alliance leadership only (requires Manage Server permission) so nobody "
              "can log false data about others.",
    },

    # ------------------------------------------------------------------
    # guild_cog.py - جزء 2: /stats_event
    # ------------------------------------------------------------------
    "stats_top_button": {"ar": "🏆 الأوائل", "en": "🏆 Top contributors"},
    "stats_active_button": {"ar": "✅ المشاركون النشطون", "en": "✅ Active members"},
    "stats_inactive_button": {"ar": "😴 غير المشاركين", "en": "😴 Inactive members"},
    "stats_no_data": {"ar": "لا توجد بيانات مسجلة بعد.", "en": "No data recorded yet."},
    "stats_top_title": {
        "ar": "🏆 الأوائل - تكريم أفضل المساهمين",
        "en": "🏆 Top contributors - honoring the best",
    },
    "stats_top_line": {
        "ar": "{rank}. **{name}** — {count} مشاركة 🏅",
        "en": "{rank}. **{name}** — {count} contributions 🏅",
    },
    "stats_no_active": {"ar": "لا يوجد أعضاء نشطون مسجلين بعد.", "en": "No active members recorded yet."},
    "stats_active_title": {"ar": "✅ الأعضاء النشطون", "en": "✅ Active members"},
    "stats_all_participated": {
        "ar": "🎉 كل الأعضاء شاركوا بحاجة على الأقل!",
        "en": "🎉 All members have participated in at least one thing!",
    },
    "stats_inactive_title": {"ar": "😴 غير المشاركين / المتقاعسون", "en": "😴 Inactive members / slackers"},
    "stats_inactive_extra_footer": {
        "ar": "+ {count} عضو إضافي غير معروض",
        "en": "+ {count} additional members not shown",
    },
    "stats_event_prompt": {"ar": "اختر التقرير اللي عايز تشوفه:", "en": "Choose the report you want to see:"},

    # ------------------------------------------------------------------
    # guild_cog.py - جزء 3: مجموعة /gf (مهرجان التحالف)
    # ------------------------------------------------------------------
    "gf_leadership_only": {
        "ar": "❌ الأمر ده مخصص لقيادة التحالف فقط.",
        "en": "❌ This command is for alliance leadership only.",
    },
    "gf_task_modal_title": {"ar": "🎉 مهمة مهرجان التحالف", "en": "🎉 Alliance Festival task"},
    "gf_task_name_label": {"ar": "📌 اسم المهمة", "en": "📌 Task name"},
    "gf_task_name_placeholder": {"ar": "مثال: أنفق 500 جوهرة", "en": "Example: Spend 500 gems"},
    "gf_minutes_label": {
        "ar": "⏱️ المهمة هتنتهي خلال كام دقيقة؟",
        "en": "⏱️ How many minutes until the task is due?",
    },
    "gf_minutes_placeholder": {"ar": "مثال: 60", "en": "Example: 60"},
    "gf_invalid_minutes": {
        "ar": "❌ أدخل عدد دقائق صحيح وأكبر من صفر.",
        "en": "❌ Enter a valid number of minutes greater than zero.",
    },
    "gf_task_added": {
        "ar": "✅ تم تسجيل مهمة **{task}** للعضو {member}، هينتهي وقتها خلال {minutes:.0f} دقيقة. "
              "هيوصله تنبيه قبل 30 و10 دقايق ⏰",
        "en": "✅ Task **{task}** logged for {member}, due in {minutes:.0f} minutes. They'll get a "
              "reminder 30 and 10 minutes before ⏰",
    },
    "gf_no_pending_task": {
        "ar": "لا توجد مهام معلّقة لهذا العضو.",
        "en": "There are no pending tasks for this member.",
    },
    "gf_task_done": {"ar": "✅ تم تسجيل إكمال مهمة {member}!", "en": "✅ Task completion logged for {member}!"},
    "gf_no_completed_tasks": {
        "ar": "لا توجد مهام مكتملة مسجلة بعد.",
        "en": "No completed tasks recorded yet.",
    },
    "gf_board_line": {
        "ar": "{rank}. <@{uid}> — {count} مهمة مكتملة ✅",
        "en": "{rank}. <@{uid}> — {count} completed tasks ✅",
    },
    "gf_board_title": {"ar": "🏅 لوحة صدارة مهرجان التحالف", "en": "🏅 Alliance Festival leaderboard"},

    # ------------------------------------------------------------------
    # hunt_cog.py - /hunt_log
    # ------------------------------------------------------------------
    "hunt_need_one_mode": {
        "ar": "❌ لازم تستخدم طريقة واحدة على الأقل: `hunted` (يدوي)، أو `image` (صورة)، "
              "أو `bulk_list` (قائمة مجمّعة).",
        "en": "❌ You need to use at least one method: `hunted` (manual), `image` (image), "
              "or `bulk_list` (bulk list).",
    },
    "hunt_only_one_mode": {
        "ar": "❌ استخدم طريقة واحدة بس في المرة الواحدة (يدوي/صورة/قائمة) عشان منلخبطش الأرقام.",
        "en": "❌ Use only one method at a time (manual/image/list) so the numbers don't get mixed up.",
    },
    "hunt_manual_invalid_amount": {"ar": "❌ العدد لازم يكون أكبر من صفر.", "en": "❌ The amount must be greater than zero."},
    "hunt_manual_status_done": {"ar": "✅ خلّص التارجت اليومي! 🎉", "en": "✅ Finished the daily target! 🎉"},
    "hunt_manual_status_remaining": {
        "ar": "باقيله **{remaining}** للتارجت.",
        "en": "**{remaining}** left to reach the target.",
    },
    "hunt_manual_log_title": {"ar": "🐾 تم تسجيل الصيد", "en": "🐾 Hunt logged"},
    "hunt_manual_log_desc": {
        "ar": "{member} صاد **{hunted}** دلوقتي.\n📊 إجمالي اليوم: **{total}/{target}**\n{status}",
        "en": "{member} just hunted **{hunted}**.\n📊 Today's total: **{total}/{target}**\n{status}",
    },
    "hunt_bulk_parse_failed": {
        "ar": "❌ مقدرتش أفهم أي سطر من القائمة. الصيغة المتوقعة: `الاسم رقم` في كل سطر (مثال: `Ahmed 250`).",
        "en": "❌ I couldn't understand any line in the list. Expected format: `name number` per line "
              "(example: `Ahmed 250`).",
    },
    "hunt_image_not_image": {"ar": "❌ المرفق ده مش صورة.", "en": "❌ That attachment isn't an image."},
    "hunt_image_extract_failed": {
        "ar": "❌ مقدرتش أقرأ الجدول من الصورة (أو COHERE_API_KEY مش مضبوط). "
              "جرّب صورة أوضح، أو استخدم `bulk_list`/`hunted` بدل كده.",
        "en": "❌ I couldn't read the table from the image (or COHERE_API_KEY isn't set). "
              "Try a clearer image, or use `bulk_list`/`hunted` instead.",
    },
    "hunt_report_title": {"ar": "🐾 تقرير صيد", "en": "🐾 Hunt report"},
    "hunt_report_title_image_suffix": {"ar": " (من صورة)", "en": " (from image)"},
    "hunt_report_title_bulk_suffix": {"ar": " (قائمة مجمّعة)", "en": " (bulk list)"},
    "hunt_report_matched_field": {"ar": "📋 تم تسجيل {count} عضو", "en": "📋 {count} members logged"},
    "hunt_report_unmatched_field": {"ar": "⚠️ {count} اسم مش متعرف عليه", "en": "⚠️ {count} unrecognized names"},
    "hunt_report_unmatched_hint": {
        "ar": "(اتأكد إن الاسم مطابق لليوزرنيم/اسم الشهرة في الديسكورد)",
        "en": "(make sure the name matches the Discord username/display name)",
    },
    "hunt_report_footer": {"ar": "🎯 التارجت اليومي الحالي: {target}", "en": "🎯 Current daily target: {target}"},
    "hunt_channel_invalid_target": {
        "ar": "❌ التارجت اليومي لازم يكون رقم أكبر من صفر.",
        "en": "❌ The daily target must be a number greater than zero.",
    },
    "hunt_channel_success": {
        "ar": "✅ تم تحديد {channel} كقناة تقارير وقوائم الصيد.",
        "en": "✅ {channel} has been set as the hunt reports and lists channel.",
    },
    "hunt_channel_target_set": {
        "ar": "\n🎯 التارجت اليومي اتضبط على **{target}**.",
        "en": "\n🎯 The daily target has been set to **{target}**.",
    },
    "hunt_channel_admin_only": {
        "ar": "❌ الأمر ده مخصص للإدارة فقط (صلاحية Manage Server).",
        "en": "❌ This command is for admins only (requires Manage Server permission).",
    },
    "hunt_channel_error": {"ar": "❌ حصل خطأ غير متوقع.", "en": "❌ An unexpected error occurred."},
    "hunt_list_empty": {
        "ar": "مفيش بيانات صيد مسجلة لسه. استخدم `/hunt_log` عشان تبدأ التسجيل.",
        "en": "No hunt data logged yet. Use `/hunt_log` to start logging.",
    },
    "hunt_list_title": {"ar": "📊 القائمة الشاملة للصيد اليومي", "en": "📊 Daily hunt overview"},
    "hunt_list_pending_field": {"ar": "🕗 لسه ماوصلوش ({count})", "en": "🕗 Not there yet ({count})"},
    "hunt_list_done_field": {"ar": "✅ خلّصوا التارجت ({count})", "en": "✅ Reached the target ({count})"},
    "hunt_list_footer": {
        "ar": "🎯 التارجت اليومي: {target} | إجمالي الأعضاء المتابَعين: {count}",
        "en": "🎯 Daily target: {target} | Total tracked members: {count}",
    },
    "hunt_pending_line": {
        "ar": "🕗 **{name}** — {bar} ({hunted}/{target}, باقي {remaining})",
        "en": "🕗 **{name}** — {bar} ({hunted}/{target}, {remaining} remaining)",
    },
    "hunt_done_line": {
        "ar": "✅ **{name}** — {bar} ({hunted}/{target})",
        "en": "✅ **{name}** — {bar} ({hunted}/{target})",
    },

    # ------------------------------------------------------------------
    # intel_cog.py - /scout
    # ------------------------------------------------------------------
    "scout_button_prompt": {
        "ar": "اضغط الزر وصف عتاد الخصم اللي شايفه 👇",
        "en": "Press the button and describe the enemy gear you see 👇",
    },
    "scout_button_label": {"ar": "صف عتاد الخصم", "en": "Describe enemy gear"},
    "scout_modal_title": {"ar": "🔍 كشف عتاد الخصم", "en": "🔍 Enemy Gear Scan"},
    "scout_modal_label": {"ar": "👀 العتاد اللي شايفه على الخصم", "en": "👀 Gear you see on the enemy"},
    "scout_modal_placeholder": {
        "ar": "مثال: خوذة نوسيروس، درع رماة فيه جواهر مشاة...",
        "en": "Example: Noceros helmet, ranged armor with infantry gems...",
    },
    "scout_result_title": {"ar": "🔍 نتيجة تحليل عتاد الخصم", "en": "🔍 Enemy gear analysis result"},
    "scout_input_field": {"ar": "📋 الوصف المدخل", "en": "📋 Entered description"},
    "scout_footer": {
        "ar": "تحليل تقريبي مبني على كلمات مفتاحية - استخدمه كمؤشر مش كيقين 100%",
        "en": "Rough analysis based on keywords - use it as an indicator, not 100% certainty",
    },
    "scout_alert_economy": {
        "ar": "🚨 **الخصم لابس عتاد تطوير/بحث (اقتصادي)!** دفاعه شبه معدوم - احشده حالاً قبل ما يغيّر عتاده!",
        "en": "🚨 **The enemy is wearing development/research (economy) gear!** Their defense is nearly "
              "nonexistent - rally them now before they switch gear!",
    },
    "scout_alert_mixed": {
        "ar": "⚠️ **لخبطة واضحة في نوع العتاد/الجواهر** (تشكيلة مختلطة غير متجانسة) - "
              "على الأغلب حساب مش ممتلك خبرة أو بيلعب بشكل عشوائي، فرصة جيدة للهجوم.",
        "en": "⚠️ **Clear mismatch in gear/gem types** (an inconsistent mixed build) - likely an "
              "inexperienced or randomly-played account, a good attack opportunity.",
    },
    "scout_alert_normal": {
        "ar": "✅ العتاد الموصوف يبدو حرب عادي متجانس - قيّم قوة الجيش الظاهرة قبل ما تقرر تهاجم.",
        "en": "✅ The described gear looks like a normal, consistent war build - assess the visible army "
              "strength before deciding to attack.",
    },

    # ------------------------------------------------------------------
    # intel_cog.py - /heroes و /geartiers
    # ------------------------------------------------------------------
    "heroes_prompt": {"ar": "اختر التصنيف اللي عايز تشوفه:", "en": "Choose the category you want to see:"},
    "heroes_btn_economy": {"ar": "🧪 أبطال التطوير", "en": "🧪 Development heroes"},
    "heroes_btn_free_war": {"ar": "🆓 أبطال حرب مجانيين", "en": "🆓 Free war heroes"},
    "heroes_btn_paid_war": {"ar": "💎 أبطال حرب للشحن", "en": "💎 Paid war heroes"},
    "heroes_title_economy": {
        "ar": "🧪 أبطال التطوير (بناء/بحث/طاقة)",
        "en": "🧪 Development heroes (building/research/energy)",
    },
    "heroes_title_free_war": {"ar": "🆓 أفضل أبطال حرب مجانيين", "en": "🆓 Best free war heroes"},
    "heroes_title_paid_war": {"ar": "💎 أفضل أبطال حرب مدفوعين", "en": "💎 Best paid war heroes"},
    "geartiers_prompt": {"ar": "اختر تصنيف العتاد:", "en": "Choose the gear category:"},
    "gear_type_war": {"ar": "⚔️ عتاد الحرب", "en": "⚔️ War gear"},
    "gear_type_hunting": {"ar": "🏹 عتاد الصيد", "en": "🏹 Hunting gear"},
    "gear_type_economy": {"ar": "🏗️ عتاد الاقتصاد", "en": "🏗️ Economy gear"},
    "geartiers_war_title": {"ar": "{emoji} تصنيف عتاد الحرب", "en": "{emoji} War gear tiers"},
    "geartiers_hunting_title": {"ar": "{emoji} تصنيف عتاد الصيد", "en": "{emoji} Hunting gear tiers"},
    "geartiers_economy_title": {"ar": "{emoji} عتاد الاقتصاد", "en": "{emoji} Economy gear"},
    "gear_weak_field": {"ar": "⚠️ عتاد ضعيف", "en": "⚠️ Weak gear"},
    "gear_pieces_field": {"ar": "🧩 القطع", "en": "🧩 Pieces"},
    "gear_warning_field": {"ar": "⚠️ تحذير", "en": "⚠️ Warning"},

    # ------------------------------------------------------------------
    # market_cog.py - /market offer/list/cancel
    # ------------------------------------------------------------------
    "market_same_resource": {
        "ar": "❌ ماينفعش نفس نوع المورد في العرض والطلب.",
        "en": "❌ You can't offer and request the same resource type.",
    },
    "market_offer_added_title": {
        "ar": "💱 تم إضافة عرضك في البورصة",
        "en": "💱 Your offer was added to the market",
    },
    "market_have_field": {"ar": "لديّ", "en": "I have"},
    "market_want_field": {"ar": "أريد", "en": "I want"},
    "market_match_notify": {
        "ar": (
            "🔔 لقينا تطابق محتمل في بورصة الموارد!\n"
            "👤 <@{user1}> عنده {amount1} {res1} ويبي {want1} {res2}\n"
            "👤 <@{user2}> عنده {amount2} {res3} ويبي {want2} {res4}\n"
            "تواصلوا وأتموا التبادل داخل اللعبة يدوياً 🤝"
        ),
        "en": (
            "🔔 Found a possible match in the resource market!\n"
            "👤 <@{user1}> has {amount1} {res1} and wants {want1} {res2}\n"
            "👤 <@{user2}> has {amount2} {res3} and wants {want2} {res4}\n"
            "Get in touch and complete the trade manually in-game 🤝"
        ),
    },
    "market_list_empty": {"ar": "لا توجد عروض تبادل نشطة حالياً.", "en": "No active trade offers right now."},
    "market_list_title": {"ar": "💱 عروض بورصة الموارد النشطة", "en": "💱 Active resource market offers"},
    "market_list_field_value": {
        "ar": "يعطي: {give_amount} {give_res} ◀ مقابل ▶ يريد: {want_amount} {want_res}",
        "en": "Gives: {give_amount} {give_res} ◀ for ▶ Wants: {want_amount} {want_res}",
    },
    "market_cancel_none": {"ar": "مفيش عروض نشطة ليك عشان تلغيها.", "en": "You have no active offers to cancel."},
    "market_cancel_success": {"ar": "✅ تم إلغاء آخر عرض ليك.", "en": "✅ Your last offer was cancelled."},

    # ------------------------------------------------------------------
    # shield_cog.py - /shield، /voice_rescue، /shelter_done
    # ------------------------------------------------------------------
    "shield_ack_owner_only": {
        "ar": "❌ الزرار ده مخصص لصاحب الدرع بس.",
        "en": "❌ This button is for the shield owner only.",
    },
    "shield_no_active_alarm": {"ar": "ℹ️ مفيش منبه شغال دلوقتي.", "en": "ℹ️ There's no active alarm right now."},
    "shield_ack_stopped": {"ar": "✅ تمام، تم إيقاف المنبه.", "en": "✅ Done, the alarm has been stopped."},
    "shield_no_active_to_renew": {
        "ar": "ℹ️ مفيش منبه شغال دلوقتي عشان أجدده.",
        "en": "ℹ️ There's no active alarm to renew right now.",
    },
    "shield_ack_button": {"ar": "✅ استلمت / Done", "en": "✅ Done"},
    "shield_renew_button": {"ar": "🛡️ تجديد الدرع", "en": "🛡️ Renew shield"},
    "shield_duration_invalid": {
        "ar": "❌ المدة لازم تكون رقم أكبر من صفر.",
        "en": "❌ Duration must be a number greater than zero.",
    },
    "shield_repeat_invalid": {
        "ar": "❌ مدة التكرار لازم تكون رقم أكبر من صفر.",
        "en": "❌ Repeat interval must be a number greater than zero.",
    },
    "shield_already_active": {
        "ar": "⚠️ عندك منبه درع شغال بالفعل. استخدم `/shelter_done` الأول لو عايز توقفه أو تبدأ واحد جديد.",
        "en": "⚠️ You already have an active shield alarm. Use `/shelter_done` first if you want to "
              "stop it or start a new one.",
    },
    "shield_open_game_button": {"ar": "📲 افتح اللعبة", "en": "📲 Open the game"},
    "shield_started_title": {"ar": "🛡️ منبه الدرع الذكي اتفعّل", "en": "🛡️ Smart shield alarm activated"},
    "shield_duration_desc": {"ar": "مدة الدرع: **{amount} {unit}**", "en": "Shield duration: **{amount} {unit}**"},
    "shield_end_time_field": {"ar": "⏰ هينتهي تقريباً", "en": "⏰ Ends approximately"},
    "shield_first_alert_field": {"ar": "🔔 التنبيه الأول", "en": "🔔 First alert"},
    "shield_first_alert_value": {
        "ar": "قبل الانتهاء بـ 15 دقيقة (رسالة + DM)",
        "en": "15 minutes before it ends (message + DM)",
    },
    "shield_escalation_field": {"ar": "🚨 لو محدش رد", "en": "🚨 If nobody responds"},
    "shield_escalation_value": {
        "ar": "😈 هدخل الروم الصوتية اللي انت فيها وأرن بصوت إنذار لو محدش رد.",
        "en": "😈 I'll join the voice channel you're in and ring a siren if nobody responds.",
    },
    "shield_escalation_role_note": {
        "ar": "\n📣 هتم منشنة {role} كمان لو محدش استلم.",
        "en": "\n📣 {role} will also get pinged if nobody acknowledges.",
    },
    "shield_repeat_field": {"ar": "🔁 تكرار تلقائي", "en": "🔁 Automatic repeat"},
    "shield_repeat_value": {
        "ar": "كل **{hours} ساعة** لحد `/shelter_done stop_repeat:True`",
        "en": "Every **{hours} hour(s)** until `/shelter_done stop_repeat:True`",
    },
    "shield_renewed_title": {"ar": "🛡️ تم تجديد الدرع", "en": "🛡️ Shield renewed"},
    "shield_renewed_desc": {
        "ar": "منبه جديد بمدة **{duration}** ابتدى من دلوقتي.",
        "en": "A new alarm for **{duration}** has started now.",
    },
    "shield_done_no_active": {
        "ar": "ℹ️ مفيش عندك منبه درع شغال دلوقتي.",
        "en": "ℹ️ You don't have an active shield alarm right now.",
    },
    "shield_done_stopped_plain": {"ar": "✅ تم إيقاف المنبه.", "en": "✅ The alarm has been stopped."},
    "shield_done_stopped_and_repeat": {
        "ar": "✅ تم إيقاف المنبه وإلغاء التكرار.",
        "en": "✅ The alarm has been stopped and the repeat has been cancelled.",
    },
    "shield_repeat_auto_notice": {
        "ar": "🔁 هيتعاد منبه الدرع لـ{user} تلقائياً بعد **{time}**.",
        "en": "🔁 The shield alarm for {user} will automatically repeat after **{time}**.",
    },
    "shield_pre_alert_title": {
        "ar": "⏰ تنبيه: الدرع هينتهي خلال 15 دقيقة!",
        "en": "⏰ Alert: the shield ends in 15 minutes!",
    },
    "shield_pre_alert_desc": {
        "ar": "جهّز جيشك 🛡️ لو أنت فاكر خلاص، دوس زرار **✅ استلمت** تحت أو اكتب `/shelter_done`.",
        "en": "Get your army ready 🛡️ If you've already got it, press **✅ Done** below or type "
              "`/shelter_done`.",
    },
    "shield_progress_field": {"ar": "📊 نسبة انقضاء الدرع", "en": "📊 Shield elapsed progress"},
    "shield_escalated_room_line": {
        "ar": "دخلت روم **{channel}** هرن لحد ما ترد 😈\n",
        "en": "I joined **{channel}** and I'll keep ringing until you respond 😈\n",
    },
    "shield_escalated_instructions": {
        "ar": "اكتب `/shelter_done` أو دوس زرار \"✅ استلمت\" فوق عشان أسكت.",
        "en": "Type `/shelter_done` or press the \"✅ Done\" button above to make me stop.",
    },
    "shield_escalated_title": {"ar": "🚨 الدرع خلص ومردتش!", "en": "🚨 The shield ended and you didn't respond!"},
    "shield_escalation_ping": {
        "ar": "🔊 {user} لسه مستني رد! `/shelter_done` وهسكت فوراً 🙏",
        "en": "🔊 {user} still waiting for a response! `/shelter_done` and I'll stop right away 🙏",
    },
    "shield_ack_done_title": {"ar": "✅ تم الاستلام", "en": "✅ Acknowledged"},
    "shield_ack_done_desc": {
        "ar": "تمام يا {user}! استلمت، خرجت من الروم. 🫡",
        "en": "Alright {user}! Acknowledged, I've left the room. 🫡",
    },
    "shield_renew_same_duration_button": {
        "ar": "🛡️ تجديد الدرع بنفس المدة",
        "en": "🛡️ Renew shield with the same duration",
    },
    "shield_gave_up_title": {"ar": "⌛ خرجت من الروم", "en": "⌛ Left the room"},
    "shield_gave_up_desc": {
        "ar": "بعد محاولات كتير من غير رد من {user}.",
        "en": "After many attempts with no response from {user}.",
    },

    # ------------------------------------------------------------------
    # guides_cog.py - /monster (بقى ديناميكي) و /add_monster
    # ------------------------------------------------------------------
    "monster_prompt": {"ar": "اختر الوحش:", "en": "Choose the monster:"},
    "monster_select_placeholder": {"ar": "اختر اسم الوحش...", "en": "Choose the monster name..."},
    "monster_damage_field": {"ar": "⚡ نوع الضرر المطلوب", "en": "⚡ Required damage type"},
    "monster_defense_field": {"ar": "🛡️ ملاحظة الدفاع", "en": "🛡️ Defense note"},
    "monster_heroes_field": {"ar": "🦸 الأبطال المقترحون", "en": "🦸 Suggested heroes"},
    "monster_footer": {
        "ar": "بيانات إرشادية عامة - قد تختلف حسب مستوى الوحش",
        "en": "General reference info - may vary by monster level",
    },
    "monster_empty": {
        "ar": "📭 لسه مفيش وحوش مضافة. اطلب من الإدارة تستخدم `/add_monster` عشان تضيف أول وحش.",
        "en": "📭 No monsters added yet. Ask an admin to use `/add_monster` to add the first one.",
    },
    "add_monster_admin_only": {
        "ar": "❌ الأمر ده مخصص للإدارة فقط (صلاحية Manage Server).",
        "en": "❌ This command is for admins only (requires Manage Server permission).",
    },
    "add_monster_success": {
        "ar": "✅ تم إضافة وحش **{name}** بنجاح. جرّب `/monster` عشان تشوفه.",
        "en": "✅ Monster **{name}** was added successfully. Try `/monster` to see it.",
    },
    "add_monster_bad_image": {
        "ar": "❌ المرفق اللي حطيته مش صورة.",
        "en": "❌ The attachment you added isn't an image.",
    },
    "dict_not_found_suggest": {
        "ar": "❓ ما لقيتش '{term}' بالظبط. قصدك: {suggestions}؟",
        "en": "❓ Couldn't find '{term}' exactly. Did you mean: {suggestions}?",
    },
    "dict_not_found": {
        "ar": "❌ المصطلح '{term}' مش موجود في القاموس.",
        "en": "❌ The term '{term}' isn't in the dictionary.",
    },

    # ------------------------------------------------------------------
    # guides_cog.py - /info (بقى يدعم صور) و /add_info
    # ------------------------------------------------------------------
    "info_prompt": {"ar": "اختر الحدث:", "en": "Choose the event:"},
    "info_select_placeholder": {
        "ar": "اختر الحدث اللي عايز تعرف عنه...",
        "en": "Choose the event you want to know about...",
    },
    "info_empty": {
        "ar": "📭 لسه مفيش معلومات مضافة. اطلب من الإدارة تستخدم `/add_info` عشان تضيف أول شرح.",
        "en": "📭 No info entries added yet. Ask an admin to use `/add_info` to add the first one.",
    },
    "add_info_admin_only": {
        "ar": "❌ الأمر ده مخصص للإدارة فقط (صلاحية Manage Server).",
        "en": "❌ This command is for admins only (requires Manage Server permission).",
    },
    "add_info_success": {
        "ar": "✅ تم إضافة شرح **{title}** بنجاح. جرّب `/info` عشان تشوفه.",
        "en": "✅ Info entry **{title}** was added successfully. Try `/info` to see it.",
    },
    "add_info_bad_image": {
        "ar": "❌ أحد المرفقات اللي حطيتها مش صورة.",
        "en": "❌ One of the attachments you added isn't an image.",
    },

    # ------------------------------------------------------------------
    # guild_cog.py - /gf calc
    # ------------------------------------------------------------------
    "gf_calc_prompt": {
        "ar": "🧮 اكتب سؤالك أو حساب التسريعات (مثال: '4h, 6h, 1d×3' أو 'معايا 500 حجر وعايز أستبدلهم بخشب، ينفع؟')",
        "en": "🧮 Type your question or speedup calculation (e.g. '4h, 6h, 1d×3' or "
              "'I have 500 stone and want to swap it for wood, is that possible?')",
    },
    "gf_calc_field_query": {"ar": "🧮 سؤالك أو حساب التسريعات", "en": "🧮 Your question or speedup calc"},
    "gf_calc_modal_title": {"ar": "🧮 حاسبة مهرجان التحالف", "en": "🧮 Alliance Festival calculator"},
    "gf_calc_speedup_result_title": {"ar": "🚀 إجمالي التسريعات", "en": "🚀 Total speedups"},
    "gf_calc_ai_result_title": {"ar": "🧮 إجابة الحاسبة", "en": "🧮 Calculator answer"},
    "gf_calc_ai_footer": {
        "ar": "إجابة تقريبية بالذكاء الاصطناعي - تأكد من التفاصيل داخل اللعبة",
        "en": "Approximate AI-generated answer - verify the details in-game",
    },

    # ------------------------------------------------------------------
    # setup_cog.py - /setup, /setup_check
    # ------------------------------------------------------------------
    "setup_hunt_channel_select_placeholder": {
        "ar": "🏹 قناة تقارير الصيد اليومي (اختياري)",
        "en": "🏹 Daily hunt reports channel (optional)",
    },
    "setup_leadership_role_select_placeholder": {
        "ar": "📣 رتبة قادة التحالف (R4/R5) لتنبيهات الدرع (اختياري)",
        "en": "📣 Alliance leadership role (R4/R5) for shield alerts (optional)",
    },
    "setup_hunt_channel_set_confirm": {
        "ar": "✅ قناة الصيد اتضبطت: {channel}",
        "en": "✅ Hunt channel set: {channel}",
    },
    "setup_leadership_role_set_confirm": {
        "ar": "✅ رتبة القيادة اتضبطت: {role} — هتتمنشن تلقائياً لو حد اتأخر يرد على تنبيه درعه.",
        "en": "✅ Leadership role set: {role} — it will be mentioned automatically if someone is late to respond to their shield alert.",
    },
    "setup_diagnostics_button_label": {
        "ar": "🩺 فحص الإعدادات الحالية",
        "en": "🩺 Check current settings",
    },
    "setup_diag_lang_line": {
        "ar": "✅ اللغة مضبوطة: **{lang_label}**",
        "en": "✅ Language set: **{lang_label}**",
    },
    "setup_diag_hunt_channel_not_set": {
        "ar": "⚠️ قناة تقارير الصيد لسه ماتحددتش (اختياري - `/hunt_log` هيرد في نفس القناة اللي بتنفّذ فيها الأمر)",
        "en": "⚠️ Hunt reports channel isn't set yet (optional - `/hunt_log` will reply in whichever channel it's run from)",
    },
    "setup_diag_hunt_channel_deleted": {
        "ar": "❌ قناة الصيد المحددة اتمسحت أو البوت طرد منها - اضبطها تاني من `/setup`",
        "en": "❌ The configured hunt channel was deleted or the bot was removed from it - set it again from `/setup`",
    },
    "setup_diag_hunt_channel_ok": {
        "ar": "✅ قناة الصيد شغالة: {channel}",
        "en": "✅ Hunt channel is working: {channel}",
    },
    "setup_diag_hunt_channel_perms_missing": {
        "ar": "❌ البوت ناقصه صلاحية Send Messages/Embed Links في {channel}",
        "en": "❌ The bot is missing the Send Messages/Embed Links permission in {channel}",
    },
    "setup_diag_role_not_set": {
        "ar": "⚠️ رتبة القيادة لسه ماتحددتش (اختياري - تنبيه `/shield` مش هيمنشن حد لو الدرع خلص من غير رد)",
        "en": "⚠️ Leadership role isn't set yet (optional - `/shield` alerts won't mention anyone if a shield expires with no response)",
    },
    "setup_diag_role_deleted": {
        "ar": "❌ رتبة القيادة المحددة اتمسحت - اضبط رتبة تانية من `/setup`",
        "en": "❌ The configured leadership role was deleted - set another role from `/setup`",
    },
    "setup_diag_role_ok": {
        "ar": "✅ رتبة القيادة هتتمنشن فعلياً: {role}",
        "en": "✅ Leadership role will actually be mentioned: {role}",
    },
    "setup_diag_role_warn": {
        "ar": "⚠️ رتبة القيادة {role} مضبوطة، بس الرتبة مش Mentionable والبوت مالوش صلاحية "
              "Mention Everyone - يعني المنشنة ممكن متوصلش تنبيه فعلي. فعّل \"Allow anyone to mention\" "
              "في إعدادات الرتبة، أو ادّي البوت صلاحية Mention Everyone.",
        "en": "⚠️ Leadership role {role} is set, but the role isn't mentionable and the bot lacks the "
              "Mention Everyone permission - so the mention might not actually notify anyone. Enable "
              "\"Allow anyone to mention\" in the role's settings, or grant the bot the Mention Everyone permission.",
    },
    "setup_diag_link_default": {
        "ar": "⚠️ رابط اللعبة لسه بالقيمة الافتراضية (تقدر تخصصه لاحقاً لو حبيت)",
        "en": "⚠️ Game link is still the default value (you can customize it later if you'd like)",
    },
    "setup_diag_link_custom": {
        "ar": "✅ رابط اللعبة مخصص: {link}",
        "en": "✅ Game link is customized: {link}",
    },
    "setup_diag_cohere_ok": {
        "ar": "✅ مفتاح Cohere موجود - `/ai` وتحليل صور الصيد شغالين",
        "en": "✅ Cohere key is present - `/ai` and hunt image analysis are working",
    },
    "setup_diag_cohere_missing": {
        "ar": "❌ مفيش COHERE_API_KEY في `.env` - `/ai` وتحليل الصور بالكامل معطّلين حالياً",
        "en": "❌ No COHERE_API_KEY in `.env` - `/ai` and image analysis are fully disabled right now",
    },
    "setup_diag_nacl_ok": {
        "ar": "✅ PyNaCl متثبتة - تصعيد `/shield` الصوتي هيشتغل",
        "en": "✅ PyNaCl is installed - `/shield` voice escalation will work",
    },
    "setup_diag_nacl_missing": {
        "ar": "❌ PyNaCl مش متثبتة - تصعيد `/shield` الصوتي مش هيشتغل (`pip install PyNaCl`)",
        "en": "❌ PyNaCl isn't installed - `/shield` voice escalation won't work (`pip install PyNaCl`)",
    },
    "setup_diag_intent_ok": {
        "ar": "✅ Server Members Intent مفعّل",
        "en": "✅ Server Members Intent is enabled",
    },
    "setup_diag_intent_missing": {
        "ar": "❌ Server Members Intent مقفول من Discord Developer Portal - أوامر زي `/stats_event` "
              "و`/log_activity` ممكن ما تشتغلش صح",
        "en": "❌ Server Members Intent is disabled from the Discord Developer Portal - commands like "
              "`/stats_event` and `/log_activity` might not work correctly",
    },
    "setup_diag_base_perms_ok": {
        "ar": "صلاحيات الرسائل الأساسية (Send Messages/Embed Links) سليمة",
        "en": "Basic message permissions (Send Messages/Embed Links) are fine",
    },
    "setup_diag_base_perms_bad": {
        "ar": "ناقص صلاحية Send Messages أو Embed Links في السيرفر",
        "en": "Missing the Send Messages or Embed Links permission in the server",
    },
    "setup_diag_voice_perms_ok": {
        "ar": "صلاحيات الصوت (Connect/Speak) سليمة لتصعيد الدرع",
        "en": "Voice permissions (Connect/Speak) are fine for shield escalation",
    },
    "setup_diag_voice_perms_bad": {
        "ar": "ناقص صلاحية Connect أو Speak - تصعيد `/shield` الصوتي مش هيقدر يدخل الروم",
        "en": "Missing the Connect or Speak permission - `/shield` voice escalation won't be able to join the room",
    },
    "setup_diag_title": {"ar": "🩺 فحص حالة إعدادات البوت", "en": "🩺 Bot settings health check"},
    "setup_diag_summary_field": {"ar": "📋 الخلاصة", "en": "📋 Summary"},
    "setup_diag_summary_value": {
        "ar": "✅ سليم: {healthy}  •  ⚠️ تنبيه: {warnings}  •  ❌ معطّل: {broken}",
        "en": "✅ Healthy: {healthy}  •  ⚠️ Warning: {warnings}  •  ❌ Broken: {broken}",
    },
    "setup_embed_title": {"ar": "⚙️ دليل التثبيت السريع", "en": "⚙️ Quick setup guide"},
    "setup_embed_description": {
        "ar": "اختر من القوائم تحت لضبط البوت لسيرفرك في ثواني - كل اختيار بيتحفظ فوراً "
              "من غير ما تحتاج تكتب أي أمر إضافي.\n\n"
              "🌐 **اللغة** — تتحكم في كل ردود البوت الفعلية.\n"
              "🏹 **قناة الصيد** — فين تتبعت تقارير وملخصات `/hunt_log` تلقائياً.\n"
              "📣 **رتبة القيادة** — مين يتمنشن تلقائياً لو عضو اتأخر يرد على تنبيه `/shield`.\n"
              "🩺 **فحص الإعدادات** — تأكد إن كل حاجة فعلاً شغالة (صلاحيات، Cohere، الصوت...) مش بس متسجلة.",
        "en": "Choose from the menus below to configure the bot for your server in seconds - each choice "
              "is saved instantly, no extra commands needed.\n\n"
              "🌐 **Language** — controls all of the bot's actual replies.\n"
              "🏹 **Hunt channel** — where `/hunt_log` reports and summaries are sent automatically.\n"
              "📣 **Leadership role** — who gets mentioned automatically if a member is late to respond to a `/shield` alert.\n"
              "🩺 **Settings check** — confirm everything is actually working (permissions, Cohere, voice...) not just saved.",
    },
    "setup_current_role_field": {"ar": "📣 رتبة القيادة الحالية", "en": "📣 Current leadership role"},
}


ACTIVITY_TYPE_LABELS_I18N = {
    "rally": {"ar": "👥 حشود (Rally)", "en": "👥 Rallies"},
    "guild_fest": {"ar": "🎉 مهرجان التحالف", "en": "🎉 Alliance Festival"},
    "dragon_arena": {"ar": "🐉 ساحة التنين", "en": "🐉 Dragon Arena"},
    "kvk": {"ar": "⚔️ KvK", "en": "⚔️ KvK"},
}

RALLY_TYPE_LABELS_I18N = {
    "attack": {"ar": "⚔️ هجوم", "en": "⚔️ Attack"},
    "defense": {"ar": "🛡️ دفاع", "en": "🛡️ Defense"},
}

RALLY_RESULT_LABELS_I18N = {
    "win": {"ar": "🏆 فوز", "en": "🏆 Win"},
    "loss": {"ar": "❌ خسارة", "en": "❌ Loss"},
    "draw": {"ar": "🤝 تعادل", "en": "🤝 Draw"},
}

EVENT_CATEGORY_LABELS_I18N = {
    "hell": {"ar": "🔥 حدث الجحيم", "en": "🔥 Hell Event"},
    "solo": {"ar": "🧍 الحدث الفردي", "en": "🧍 Individual Event"},
}

EVENT_TYPE_LABELS_I18N = {
    "research": {"ar": "🔬 أبحاث", "en": "🔬 Research"},
    "building": {"ar": "🏗️ بناء", "en": "🏗️ Building"},
    "t1": {"ar": "⚔️ تدريب T1", "en": "⚔️ Training T1"},
    "t2": {"ar": "⚔️ تدريب T2", "en": "⚔️ Training T2"},
    "t3": {"ar": "⚔️ تدريب T3", "en": "⚔️ Training T3"},
    "t4": {"ar": "⚔️ تدريب T4", "en": "⚔️ Training T4"},
    "t5": {"ar": "⚔️ تدريب T5", "en": "⚔️ Training T5"},
    "artifacts": {"ar": "🏺 آثار", "en": "🏺 Artifacts"},
    "hunting": {"ar": "🐾 صيد وحوش", "en": "🐾 Monster hunting"},
    "tycoon": {"ar": "🎩 تايكون", "en": "🎩 Tycoon"},
    "ghosts": {"ar": "👻 أشباح", "en": "👻 Ghosts"},
    "spending": {"ar": "💎 إنفاق جواهر/تسريعات", "en": "💎 Gem/speedup spending"},
}

TROOP_LABELS_I18N = {
    "infantry": {"ar": "🛡️ مشاة", "en": "🛡️ Infantry"},
    "ranged": {"ar": "🏹 رماة", "en": "🏹 Ranged"},
    "cavalry": {"ar": "🐎 فرسان", "en": "🐎 Cavalry"},
    "siege": {"ar": "🏰 حصار", "en": "🏰 Siege"},
    "hybrid": {"ar": "🔀 هجين", "en": "🔀 Hybrid"},
}

# أسماء الموارد لاستخدامها جوه رسائل/Embeds بتتغيّر مع /language (مختلف عن
# RESOURCE_CHOICES بتاع market_cog.py اللي Metadata ثابتة عند ديسكورد نفسه ومش
# بتتغيّر ديناميكياً - نفس القيد الموجود على أسماء الأوامر نفسها).
RESOURCE_LABELS_I18N = {
    "food": {"ar": "🍖 طعام", "en": "🍖 Food"},
    "wood": {"ar": "🪵 خشب", "en": "🪵 Wood"},
    "stone": {"ar": "🪨 حجر", "en": "🪨 Stone"},
    "ore": {"ar": "⛏️ خام/فولاذ", "en": "⛏️ Ore/Steel"},
    "gold": {"ar": "💰 ذهب", "en": "💰 Gold"},
}


def t(key: str, lang: str, **kwargs) -> str:
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    text = entry.get(lang, entry.get(DEFAULT_LANG, key))
    return text.format(**kwargs) if kwargs else text
