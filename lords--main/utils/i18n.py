"""
طبقة ترجمة خفيفة (ar/en) لتفضيل اللغة على مستوى السيرفر.
مسؤولة عن: تخزين/قراءة تفضيل اللغة، وقاموس ترجمات لعناصر الواجهة
(أزرار، عناوين، رسائل نظام) للأوامر اللي بتدعم اللغتين.

⚠️ حدود مهمة (قيود منصة ديسكورد نفسها، مش قيد في الكود):
أسماء ووصف الأوامر اللي بتظهر لما تكتب "/" جوه ديسكورد (زي "🏯 أفضل أبطال وتشكيلة
لإسقاط الحصن المظلم") دي "Metadata" مسجّلة مع ديسكورد وقت تشغيل البوت، وبتتحدد حسب
لغة تطبيق ديسكورد بتاع كل شخص - مش ممكن تتغيّر ديناميكياً حسب إعداد `/language` بتاعنا
لكل سيرفر. اللي فعلاً بيتغيّر مع `/language` هو *رد البوت الفعلي* لما تنفّذ الأمر:
العنوان، القوائم المنسدلة، الأزرار، النوافذ (Modals)، والرسائل. وده اللي المستخدم بيشوفه
ويتفاعل معاه فعلياً في 99% من الوقت.

نطاق التغطية الحالي (بيتحترم فيه `/language` بالكامل في ردود البوت):
/ai، /play، /rally، /troop، /language، /set_game_link، /game_link، /jewel_calc،
/darknest، /gear، /help.
باقي الأوامر (market/games/intel/hunt/shield/guild/rally-remaining/events/wiki/monster/
dict/info/heroes/geartiers/scout/counter/report/colo/analyze) لسه بواجهة عربية ثابتة
حالياً - ترجمتها خطوة تالية.
"""
from utils.storage import load, save

SETTINGS_FILE = "settings"
DEFAULT_LANG = "ar"
SUPPORTED_LANGS = ("ar", "en")


def get_lang(guild_id: int | None) -> str:
    if guild_id is None:
        return DEFAULT_LANG
    data = load(SETTINGS_FILE)
    return data.get(str(guild_id), {}).get("lang", DEFAULT_LANG)


def set_lang(guild_id: int, lang: str) -> None:
    data = load(SETTINGS_FILE)
    gid = str(guild_id)
    data.setdefault(gid, {})
    data[gid]["lang"] = lang
    save(SETTINGS_FILE, data)


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
    "ai_cooldown": {
        "ar": "⏳ استنى شوية ({s} ثانية) قبل ما تسأل تاني.",
        "en": "⏳ Wait a bit ({s}s) before asking again.",
    },
    "ai_might_line": {
        "ar": "قوة الحساب (Might) اللي ذكرها اللاعب: {might}",
        "en": "Player-reported account Might: {might}",
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
    "rally_title": {"ar": "📯 نداء حشد!", "en": "📯 Rally call!"},
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
    # مشترك بين كذا أمر - رسالة خطأ عامة غير متوقعة
    # ------------------------------------------------------------------
    "err_unexpected": {"ar": "❌ حصل خطأ غير متوقع.", "en": "❌ An unexpected error occurred."},

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
}

ACTIVITY_TYPE_LABELS_I18N = {
    "rally": {"ar": "👥 حشود (Rally)", "en": "👥 Rallies"},
    "guild_fest": {"ar": "🎉 مهرجان التحالف", "en": "🎉 Alliance Festival"},
    "dragon_arena": {"ar": "🐉 ساحة التنين", "en": "🐉 Dragon Arena"},
    "kvk": {"ar": "⚔️ KvK", "en": "⚔️ KvK"},
}

TROOP_LABELS_I18N = {
    "infantry": {"ar": "🛡️ مشاة", "en": "🛡️ Infantry"},
    "ranged": {"ar": "🏹 رماة", "en": "🏹 Ranged"},
    "cavalry": {"ar": "🐎 فرسان", "en": "🐎 Cavalry"},
    "siege": {"ar": "🏰 حصار", "en": "🏰 Siege"},
    "hybrid": {"ar": "🔀 هجين", "en": "🔀 Hybrid"},
}


def t(key: str, lang: str, **kwargs) -> str:
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    text = entry.get(lang, entry.get(DEFAULT_LANG, key))
    return text.format(**kwargs) if kwargs else text
