"""
/help - دليل الأوامر الكامل، منظّم في أقسام مع شرح متوسط الطول لكل أمر (مش كلمة واحدة، ومش فقرة طويلة).
بيحترم /language بالكامل: العنوان، الأقسام، وشرح كل أمر بيتغيّر عربي/إنجليزي حسب تفضيل السيرفر.

ملحوظة: أسماء ووصف الأوامر اللي ديسكورد نفسه بيعرضها لما تكتب "/" (Metadata مسجّلة عند
ديسكورد) بتتبع لغة تطبيق ديسكورد بتاع كل شخص، مش تفضيل /language بتاعنا - وده قيد من ديسكورد
نفسه مش حاجة نقدر نتحكم فيها. الأمر ده (/help) هو المرجع الكامل والمضمون يطلع باللغة الصح
دايماً لأي حد يفتحه.
"""
import discord
from discord import app_commands
from discord.ext import commands

from utils.i18n import get_lang, t

# ---------------------------------------------------------------------------
# محتوى الأقسام - كل قسم: مفتاح، إيموجي، لون، اسم ثنائي اللغة، وقائمة أوامر
# (كل أمر: الاسم كامل زي ما بيتكتب، وشرح ثنائي اللغة متوسط الطول)
# ---------------------------------------------------------------------------

HELP_CATEGORIES = [
    {
        "key": "calc",
        "emoji": "🧮",
        "color": discord.Color.gold(),
        "label": {"ar": "حواسب الحدث وتطوير الحساب", "en": "Event & Account Calculators"},
        "commands": [
            {
                "cmd": "/event",
                "desc": {
                    "ar": "حاسبة أحداث الجحيم/المنفرد. تختار نوع النشاط (أبحاث، تدريب، صيد...) وتدخّل "
                          "النقاط المطلوبة والتسريحات المتاحة، والبوت يقولك هتكمل المرحلة ولا لأ، ولو مش هتكمل "
                          "يوريك هتوصل كام % وناقصك كام وقت بالظبط.",
                    "en": "Hell Event / Solo Event calculator. Pick the activity type (research, training, "
                          "hunting...), enter the points needed and your available speedups, and the bot tells "
                          "you whether you'll finish the stage - and if not, exactly what % you'll reach and how "
                          "much extra time you need.",
                },
            },
            {
                "cmd": "/shelter",
                "desc": {
                    "ar": "مؤقت حماية المخبأ (4/8/12 ساعة). بيبعتلك تنبيه هنا في القناة ورسالة خاصة قبل "
                          "ما الحماية تخلص بـ15 دقيقة، عشان متتفاجئش وجيشك مكشوف.",
                    "en": "A shelter-protection timer (4/8/12 hours). You'll get a ping in the channel plus a "
                          "DM 15 minutes before it expires, so you're never caught with your army exposed.",
                },
            },
            {
                "cmd": "/cost",
                "desc": {
                    "ar": "حاسبة تكلفة التدريب (T4/T5/الأبحاث). تدخّل عدد الوحدات وتكلفة الموارد لكل وحدة وزمن "
                          "التدريب، وترجعلك الإجمالي المطلوب من كل مورد والوقت الكلي التقريبي.",
                    "en": "Training cost calculator (T4/T5/research). Enter the unit count, per-unit resource "
                          "cost, and training time, and you'll get the total resources needed plus the "
                          "estimated total time.",
                },
            },
            {
                "cmd": "/speedup",
                "desc": {
                    "ar": "حساب سريع لإجمالي أيام/ساعات/دقايق التسريحات اللي معاك في الحقيبة، مفيد قبل ما "
                          "تستخدمها في حدث أو تدريب عشان تعرف رصيدك بالظبط.",
                    "en": "A quick calculation of your total speedup time (days/hours/minutes) in your bag - "
                          "handy before spending them on an event or training so you know exactly what you have.",
                },
            },
            {
                "cmd": "/jewel_calc",
                "desc": {
                    "ar": "حاسبة دمج الجواهر. تختار التاير المستهدف (لغاية 🔴 الخرافي/Mythic)، تدخّل الكمية "
                          "المطلوبة ونسبة الدمج، وترجعلك تفصيل تاير بتاير لغاية إجمالي جواهر Common اللي محتاجها.",
                    "en": "Jewel merge calculator. Pick the target tier (all the way to 🔴 Mythic), enter the "
                          "quantity and merge ratio you need, and get a full tier-by-tier breakdown down to the "
                          "total Common jewels required.",
                },
            },
        ],
    },
    {
        "key": "war",
        "emoji": "⚔️",
        "color": discord.Color.red(),
        "label": {"ar": "غرفة الحرب والتكتيك", "en": "War Room & Tactics"},
        "commands": [
            {
                "cmd": "/counter",
                "desc": {
                    "ar": "تدخّل تشكيلة العدو (مشاة/رماة/فرسان/حصار) والبوت يرجعلك أنسب رد ونوع التشكيلة "
                          "التكتيكية (Wedge/Phalanx) اللي تناسب الموقف.",
                    "en": "Enter the enemy's formation (infantry/ranged/cavalry/siege) and get the best "
                          "counter troops plus the tactical formation (Wedge/Phalanx) that fits the situation.",
                },
            },
            {
                "cmd": "/report add | list | user",
                "desc": {
                    "ar": "سجل معارك التحالف: `add` يسجّل نتيجة معركة جديدة، `list` يعرض آخر المعارك المسجلة "
                          "في السيرفر كله، و`user` يعرض سجل عضو معيّن بس.",
                    "en": "The alliance battle log: `add` records a new battle result, `list` shows the latest "
                          "logged battles for the whole server, and `user` shows one member's log only.",
                },
            },
            {
                "cmd": "/darknest",
                "desc": {
                    "ar": "تختار مستوى الحصن المظلم (1-6) وياخدك على أفضل أبطال وتشكيلة مقترحة لإسقاطه بنجاح.",
                    "en": "Pick a Dark Nest level (1-6) and get the best suggested heroes and formation to "
                          "take it down successfully.",
                },
            },
            {
                "cmd": "/colo",
                "desc": {
                    "ar": "محاكي الكولوسيوم: تدخّل أبطال الخصم (مفصولين بفاصلة) وترجعلك التشكيلة المضادة "
                          "المناسبة لكل بطل، بالإضافة لقاعدة عامة للحالات اللي مفيهاش بيانات محدّدة.",
                    "en": "Colosseum simulator: enter the opponent's heroes (comma-separated) and get the "
                          "right counter for each one, plus a general rule for cases without specific data.",
                },
            },
            {
                "cmd": "/analyze",
                "desc": {
                    "ar": "محلل تقارير المعارك. ممكن ترفق صورة التقرير للتوثيق، وتدخّل نسب/أعداد قوات الخصم "
                          "يدوياً عشان البوت يحللها ويطلعلك الرد التكتيكي المناسب.",
                    "en": "Battle report analyzer. You can attach a screenshot for documentation, then enter "
                          "the enemy troop ratios/counts manually so the bot can analyze them and suggest a "
                          "tactical response.",
                },
            },
        ],
    },
    {
        "key": "guides",
        "emoji": "📖",
        "color": discord.Color.dark_teal(),
        "label": {"ar": "الأدلة والأبطال والمصطلحات", "en": "Guides, Heroes & Terms"},
        "commands": [
            {
                "cmd": "/wiki (أو /guide)",
                "desc": {
                    "ar": "الدليل الشامل للعبة في قائمة منسدلة واحدة: 🐾 الوحوش (نوع الضرر والأبطال والعتاد "
                          "المطلوب)، 🛡️ المعدات (أفضل تشكيلات F2P/P2P)، 🦸 الأبطال، و🐉 المرافقين.",
                    "en": "The full game guide in one dropdown menu: 🐾 Monsters (damage type, heroes, gear "
                          "needed), 🛡️ Gear (best F2P/P2P setups), 🦸 Heroes, and 🐉 Companions.",
                },
            },
            {
                "cmd": "/gear",
                "desc": {
                    "ar": "تختار نوع القوات (مشاة/رماة/فرسان/حصار/هجين) بعدها فئتك (F2P أو P2P) وترجعلك "
                          "أفضل عتاد مناسب لنمط لعبك.",
                    "en": "Choose your troop type (infantry/ranged/cavalry/siege/hybrid), then your player "
                          "type (F2P or P2P), and get the best gear suited to your playstyle.",
                },
            },
            {
                "cmd": "/monster",
                "desc": {
                    "ar": "تختار اسم الوحش وترجعلك أفضل الأبطال لصيده حسب نوع الضرر المناسب (سحري/فيزيائي)، "
                          "شامل حالات خاصة زي Frostwing وNoceros اللي دفاعهم غير متوازن.",
                    "en": "Pick a monster's name and get the best heroes to hunt it based on the right damage "
                          "type (magic/physical), including special cases like Frostwing and Noceros with "
                          "lopsided defenses.",
                },
            },
            {
                "cmd": "/dict",
                "desc": {
                    "ar": "قاموس مصطلحات سريع مع اقتراحات تلقائية أثناء الكتابة (T4, Rally, RSS, Wedge...) "
                          "لأي مصطلح جديد شفته وحابب تفهمه بسرعة.",
                    "en": "A quick terminology dictionary with live autocomplete suggestions (T4, Rally, RSS, "
                          "Wedge...) for any new term you come across and want explained fast.",
                },
            },
            {
                "cmd": "/info",
                "desc": {
                    "ar": "شرح مبسط للأحداث الرئيسية في اللعبة زي ساحة التنين، حدث المنفرد، KvK، مهرجان "
                          "التحالف، ونظام الجيش.",
                    "en": "A simplified explanation of the game's major events - Dragon Arena, the Solo "
                          "Event, KvK, Alliance Festival, and the army system.",
                },
            },
            {
                "cmd": "/heroes",
                "desc": {
                    "ar": "خلاصة الأبطال المهمين: أبطال التطوير، أبطال حرب مجانيين، وأبطال حرب للشحن، "
                          "عشان تعرف تخطط لأولوياتك من غير ما تضيع وقتك على أبطال ضعيفة.",
                    "en": "A summary of the important heroes: growth heroes, free war heroes, and premium war "
                          "heroes, so you can plan your priorities without wasting time on weak picks.",
                },
            },
            {
                "cmd": "/geartiers",
                "desc": {
                    "ar": "تصنيف كامل للعتاد حسب الغرض: عتاد الحرب، عتاد الصيد، وعتاد الاقتصاد - مع تحذير "
                          "واضح إن لبس عتاد الاقتصاد وقت الحرب بيخلي دفاعك ضعيف جداً.",
                    "en": "A full gear classification by purpose: war gear, hunting gear, and economy gear - "
                          "with a clear warning that wearing economy gear during war leaves your defense very weak.",
                },
            },
            {
                "cmd": "/scout",
                "desc": {
                    "ar": "🔍 كاشف الخصم الضعيف: تصف عتاد الخصم اللي شايفه، والبوت يكتشفلك تلقائياً لو لابس "
                          "عتاد اقتصادي (يعني دفاعه شبه ميت) أو فيه لخبطة في نوع عتاده/جواهره.",
                    "en": "🔍 Weak-opponent detector: describe the gear you see on an enemy, and the bot "
                          "automatically flags whether they're wearing economy gear (meaning near-zero defense) "
                          "or have a mismatched gear/jewel setup.",
                },
            },
        ],
    },
    {
        "key": "games",
        "emoji": "🎮",
        "color": discord.Color.blurple(),
        "label": {"ar": "الألعاب التفاعلية", "en": "Interactive Games"},
        "commands": [
            {
                "cmd": "/play",
                "desc": {
                    "ar": "لعبة تحدي ومعرفة: البوت يختار عنصر عشوائي (عتاد/بطل/وحش/مرافق) ويديك تلميح، "
                          "وتخمّن الاسم خلال 30 ثانية عن طريق زرار. النقاط بتتراكم مع رتب زي الكويز.",
                    "en": "A guess-and-learn game: the bot picks a random item (gear/hero/monster/companion) "
                          "and gives you a hint, you guess the name within 30 seconds via a button. Points build "
                          "up into ranks just like the quiz.",
                },
            },
            {
                "cmd": "/quiz",
                "desc": {
                    "ar": "مسابقة تفاعلية بأزرار مع نقاط ورتب (🧠 خبير لوردس) - وسيلة حلوة تحفّز الأعضاء "
                          "يتفاعلوا ويتعلموا معلومات عن اللعبة وهما بيلعبوا.",
                    "en": "An interactive button-based quiz with points and ranks (🧠 Lords Expert) - a fun "
                          "way to get members engaged and picking up game knowledge while they play.",
                },
            },
        ],
    },
    {
        "key": "alliance",
        "emoji": "🏯",
        "color": discord.Color.dark_gold(),
        "label": {"ar": "إدارة التحالف والتتبع", "en": "Alliance Management & Tracking"},
        "commands": [
            {
                "cmd": "/log_activity (إدارة)",
                "desc": {
                    "ar": "يسجّل مشاركة عضو في نشاط معيّن (حشود، مهرجان، ساحة تنين، KvK) - أساس كل تقارير "
                          "النشاط اللي بعد كده زي /information و/top5.",
                    "en": "Logs a member's participation in an activity (rallies, festival, Dragon Arena, "
                          "KvK) - the foundation for all the activity reports that follow, like /information "
                          "and /top5.",
                },
            },
            {
                "cmd": "/rally_log (إدارة)",
                "desc": {
                    "ar": "يسجّل حضور حشد فعلي: تختار الأعضاء المشاركين (لحد 25 دفعة واحدة)، نوعه (هجوم/دفاع)، "
                          "ونتيجته (فوز/خسارة/تعادل) مع ملاحظة اختيارية.",
                    "en": "Logs actual rally attendance: pick the participating members (up to 25 at once), "
                          "the type (attack/defense), and the result (win/loss/draw) with an optional note.",
                },
            },
            {
                "cmd": "/information [member]",
                "desc": {
                    "ar": "ملف شامل لأي عضو (نفسك افتراضياً): مشاركاته في الحشود، التزامه بالحروب وKvK، "
                          "والفعاليات اللي شارك فيها، بالإضافة لرتبته العامة بين باقي الأعضاء.",
                    "en": "A full member profile (yourself by default): their rally participation, war/KvK "
                          "commitment, and event history, plus their overall rank among other members.",
                },
            },
            {
                "cmd": "/user_admin_check (إدارة)",
                "desc": {
                    "ar": "لوحة متابعة إدارية: تختار عضو من قائمة منسدلة عشان تشوف سجله الكامل في كل الأحداث "
                          "(حروب/حشود/KvK/ساحة تنين/مهرجان) شامل آخر 5 أنشطة وآخر 5 حشود بتاريخها.",
                    "en": "An admin tracking dashboard: pick a member from a dropdown to see their full record "
                          "across every event type (wars/rallies/KvK/Dragon Arena/festival), including their "
                          "last 5 activities and last 5 rallies with dates.",
                },
            },
            {
                "cmd": "/top5",
                "desc": {
                    "ar": "أنشط 5 أعضاء في كل الفعاليات والحشود مجتمعة، بناءً على مجموع نقاط الأنشطة والحشود "
                          "والمعارك المسجلة - وسيلة سريعة لتكريم الأعضاء الأكتر مجهود.",
                    "en": "The top 5 most active members across all events and rallies combined, based on "
                          "total logged activity/rally/battle points - a quick way to spotlight the hardest "
                          "workers.",
                },
            },
            {
                "cmd": "/event_stats event_type",
                "desc": {
                    "ar": "تقرير نسبة مشاركة التحالف في فعالية معينة (حشود/مهرجان/ساحة تنين/KvK/الكل)، بيوريك "
                          "عدد ونسبة المشاركين وقائمة اللي لسه ماشاركوش.",
                    "en": "A participation-rate report for a specific event (rallies/festival/Dragon Arena/"
                          "KvK/all), showing the count and % of participants plus a list of who hasn't joined yet.",
                },
            },
            {
                "cmd": "/stats_event",
                "desc": {
                    "ar": "لوحة تفاعلية سريعة تلخص الأوائل، الأعضاء النشطين، وغير المشاركين - في مكان واحد.",
                    "en": "A quick interactive dashboard summarizing the top members, active participants, "
                          "and non-participants - all in one place.",
                },
            },
            {
                "cmd": "/gf task | done | board | optimize",
                "desc": {
                    "ar": "إدارة مهام مهرجان التحالف بالكامل: `task` لإضافة مهمة، `done` لتعليمها منجزة، "
                          "`board` للوحة الصدارة، و`optimize` عشان الـAI يقترحلك أفضل طريقة تنفيذ.",
                    "en": "Full Alliance Festival task management: `task` adds a task, `done` marks it "
                          "complete, `board` shows the leaderboard, and `optimize` gets AI suggestions for the "
                          "best way to complete it.",
                },
            },
            {
                "cmd": "/reset_stats (إدارة فقط)",
                "desc": {
                    "ar": "يصفّر كل السجلات عشان تبدأ أسبوع جديد من الصفر. محتاج صلاحية Administrator "
                          "ورسالة تأكيد بزرار قبل التنفيذ الفعلي - مفيش تصفير بضغطة واحدة بالغلط.",
                    "en": "Resets all records to start a fresh week. Requires Administrator permission plus a "
                          "confirmation button before it actually runs - no accidental one-tap resets.",
                },
            },
        ],
    },
    {
        "key": "market",
        "emoji": "💱",
        "color": discord.Color.green(),
        "label": {"ar": "بورصة الموارد", "en": "Resource Market"},
        "commands": [
            {
                "cmd": "/market offer",
                "desc": {
                    "ar": "تعرض \"عندي X مقابل Y\"، والبوت يدوّر تلقائياً على تطابق مع عرض عضو تاني ويبعت "
                          "تنبيه للطرفين لو لقى واحد مناسب.",
                    "en": "Post \"I have X for Y\" and the bot automatically looks for a matching offer from "
                          "another member, pinging both sides if it finds one.",
                },
            },
            {
                "cmd": "/market list | cancel",
                "desc": {
                    "ar": "`list` يعرض كل العروض المفتوحة حالياً في السيرفر، و`cancel` يلغي عرضك الحالي "
                          "لو غيّرت رأيك.",
                    "en": "`list` shows every open offer currently posted on the server, and `cancel` "
                          "withdraws your own offer if you change your mind.",
                },
            },
        ],
    },
    {
        "key": "ai",
        "emoji": "🤖",
        "color": discord.Color.purple(),
        "label": {"ar": "مستشار لوردس المطوّر (AI)", "en": "The Advanced Lords Advisor (AI)"},
        "commands": [
            {
                "cmd": "/ai [question] [image] [might]",
                "desc": {
                    "ar": "خبير اللعبة بالذكاء الاصطناعي. اكتب سؤالك وهيردّ عليك مباشرة بمعلومات دقيقة من "
                          "قاعدة معرفة اللعبة، أو ارفق صورة عتاد/تقرير معركة وهيحللها فعلياً لك. محتاج "
                          "`COHERE_API_KEY` مضبوط عند صاحب البوت عشان يشتغل.",
                    "en": "The game's AI expert. Type a question and get an answer straight from the game's "
                          "knowledge base, or attach a gear/battle report screenshot and it will actually "
                          "analyze it for you. Requires the bot owner to have `COHERE_API_KEY` configured.",
                },
            },
        ],
    },
    {
        "key": "rally",
        "emoji": "📯",
        "color": discord.Color.orange(),
        "label": {"ar": "نداء الحشود الذكي", "en": "Smart Rally System"},
        "commands": [
            {
                "cmd": "/troop set",
                "desc": {
                    "ar": "كل عضو يسجّل نوع قواته الأساسي (مشاة/رماة/فرسان/حصار/هجين) مرة واحدة - ده اللي "
                          "بيحدد مين هيتوصله تنبيه لما حد يفتح حشد.",
                    "en": "Every member registers their main troop type (infantry/ranged/cavalry/siege/"
                          "hybrid) once - this decides who gets pinged when someone opens a rally.",
                },
            },
            {
                "cmd": "/rally set troop:<نوع>",
                "desc": {
                    "ar": "يفتح نداء حشد وينبّه بس الأعضاء المسجلين بنفس نوع القوات المطلوب (+ الأعضاء "
                          "الهجين)، مع عد تنازلي حي وزرار \"📲 افتح التطبيق\".",
                    "en": "Opens a rally call and pings only the members registered with the matching troop "
                          "type (plus hybrid members), with a live countdown and a \"📲 Open the app\" button.",
                },
            },
        ],
    },
    {
        "key": "hunt",
        "emoji": "🐾",
        "color": discord.Color.dark_green(),
        "label": {"ar": "متتبع الصيد اليومي", "en": "Daily Hunt Tracker"},
        "commands": [
            {
                "cmd": "/hunt_log",
                "desc": {
                    "ar": "يسجّل صيد عضو بثلاث طرق (وحدة واحدة كل مرة): يدوي (اسم العضو والرقم)، صورة "
                          "لجدول الصيد يتحلل تلقائياً، أو قائمة مجمّعة (سطر لكل عضو).",
                    "en": "Logs a member's hunting count three ways (one at a time): manually (member + "
                          "number), from an auto-analyzed hunt screenshot, or as a bulk list (one line per member).",
                },
            },
            {
                "cmd": "/hunt_channel (إدارة)",
                "desc": {
                    "ar": "يحدد قناة تقارير الصيد اليومية، ويقدر كمان يضبط التارجت المطلوب من كل عضو "
                          "(افتراضياً 100 لو محدش ضبطه).",
                    "en": "Sets the channel for daily hunt reports, and can also set the daily target "
                          "required from each member (defaults to 100 if unset).",
                },
            },
            {
                "cmd": "/hunt_list",
                "desc": {
                    "ar": "عرض شامل لكل الأعضاء المتابَعين: مين خلّص التارجت اليومي بتاعه ومين لسه باقيله كام.",
                    "en": "A full overview of every tracked member: who has hit their daily target and who "
                          "still has some way to go.",
                },
            },
        ],
    },
    {
        "key": "shield",
        "emoji": "🔔",
        "color": discord.Color.dark_orange(),
        "label": {"ar": "منبه الدرع الذكي", "en": "Smart Shield Alarm"},
        "commands": [
            {
                "cmd": "/shield (أو /voice_rescue)",
                "desc": {
                    "ar": "يضبط مؤقت درع/مخبأ بمدة حرة، ويبعت تنبيه (رسالة + DM) قبل الانتهاء بـ15 دقيقة مع "
                          "زرار \"✅ استلمت\". لو محدش رد، البوت يدخل الروم الصوتية بتاعتك ويرن بنغمة إنذار "
                          "لحد ما حد يرد.",
                    "en": "Sets a shield/shelter timer of any length, and sends an alert (message + DM) 15 "
                          "minutes before it ends with an \"✅ Acknowledged\" button. If nobody responds, the "
                          "bot joins your voice channel and plays an alarm tone until someone does.",
                },
            },
            {
                "cmd": "/shelter_done [stop_repeat]",
                "desc": {
                    "ar": "يوقف المنبه الحالي فوراً (وبيفصل البوت من الروم لو كان داخل يرن). ضبط "
                          "`stop_repeat:True` بيلغي كمان أي تكرار مجدول.",
                    "en": "Stops the current alarm right away (and disconnects the bot from the voice channel "
                          "if it's ringing). Setting `stop_repeat:True` also cancels any scheduled repeats.",
                },
            },
        ],
    },
    {
        "key": "settings",
        "emoji": "🌐",
        "color": discord.Color.light_grey(),
        "label": {"ar": "اللغة وإعدادات السيرفر", "en": "Language & Server Settings"},
        "commands": [
            {
                "cmd": "/setup (إدارة)",
                "desc": {
                    "ar": "دليل التثبيت السريع بضغطة زر: يضبط اللغة، قناة تقارير الصيد، ورتبة قادة "
                          "التحالف (R4/R5) اللي هتتمنشن تلقائياً وقت تنبيهات الدرع - وفيه زرار 🩺 فحص "
                          "يتأكد إن كل حاجة شغالة فعلاً مش بس متسجلة.",
                    "en": "One-click quick-setup wizard: sets the language, hunt report channel, and the "
                          "leadership (R4/R5) role that gets auto-mentioned on shield alerts - includes a "
                          "🩺 diagnostics button that verifies everything actually works, not just that it's saved.",
                },
            },
            {
                "cmd": "/setup_check (إدارة)",
                "desc": {
                    "ar": "فحص سريع بدون فتح /setup كامل: هل قناة الصيد عندها صلاحيات صح؟ هل رتبة القيادة "
                          "فعلاً هتتمنشن؟ هل مفتاح Cohere موجود؟ هل PyNaCl والصوت شغالين؟ هل Server Members "
                          "Intent مفعّل؟",
                    "en": "A quick check without opening the full /setup: does the hunt channel have the "
                          "right permissions? Will the leadership role actually get mentioned? Is the Cohere "
                          "key present? Is voice (PyNaCl) working? Is the Server Members Intent enabled?",
                },
            },
            {
                "cmd": "/language (إدارة)",
                "desc": {
                    "ar": "يضبط لغة ردود البوت لهذا السيرفر (عربي 🇪🇬 / إنجليزي 🇬🇧) - كل رسالة، قائمة، "
                          "زرار، ونافذة يتغير معاها فوراً.",
                    "en": "Sets the bot's reply language for this server (Arabic 🇪🇬 / English 🇬🇧) - every "
                          "message, dropdown, button, and modal switches immediately.",
                },
            },
            {
                "cmd": "/set_game_link (إدارة)",
                "desc": {
                    "ar": "يضبط رابط فتح اللعبة (Deep Link) المستخدم في زرار \"📲 افتح اللعبة\" بأوامر "
                          "التنبيهات زي /rally set و/shield.",
                    "en": "Sets the game deep link used by the \"📲 Open the game\" button in alert commands "
                          "like /rally set and /shield.",
                },
            },
            {
                "cmd": "/game_link",
                "desc": {
                    "ar": "يعرض الرابط المضبوط حالياً لهذا السيرفر (متاح للجميع، للمراجعة فقط).",
                    "en": "Shows the link currently configured for this server (visible to everyone, "
                          "read-only).",
                },
            },
            {
                "cmd": "/help",
                "desc": {
                    "ar": "الدليل اللي انت فاتحه دلوقتي 🙂 - قائمة كل الأقسام والأوامر مع شرح لكل واحد فيهم.",
                    "en": "The very guide you're looking at now 🙂 - every category and command, with an "
                          "explanation for each.",
                },
            },
        ],
    },
]


def build_intro_embed(lang: str) -> discord.Embed:
    embed = discord.Embed(
        title=t("help_title", lang),
        description=t("help_intro", lang),
        color=discord.Color.blurple(),
    )
    overview_lines = [
        f"{cat['emoji']} **{cat['label'][lang]}**" for cat in HELP_CATEGORIES
    ]
    embed.add_field(name=t("help_overview_field", lang), value="\n".join(overview_lines), inline=False)
    embed.set_footer(text=t("help_footer", lang))
    return embed


def build_category_embed(cat: dict, lang: str) -> discord.Embed:
    embed = discord.Embed(
        title=f"{cat['emoji']} {cat['label'][lang]}",
        color=cat["color"],
    )
    for c in cat["commands"]:
        embed.add_field(name=f"`{c['cmd']}`", value=c["desc"][lang], inline=False)
    embed.set_footer(text=t("help_footer", lang))
    return embed


class HelpCategorySelect(discord.ui.Select):
    def __init__(self, lang: str):
        self.lang = lang
        options = [
            discord.SelectOption(label=cat["label"][lang], value=cat["key"], emoji=cat["emoji"])
            for cat in HELP_CATEGORIES
        ]
        super().__init__(placeholder=t("help_select_placeholder", lang), options=options)

    async def callback(self, interaction: discord.Interaction):
        cat = next(c for c in HELP_CATEGORIES if c["key"] == self.values[0])
        await interaction.response.send_message(
            embed=build_category_embed(cat, self.lang), ephemeral=True
        )


class HelpView(discord.ui.View):
    def __init__(self, lang: str):
        super().__init__(timeout=180)
        self.add_item(HelpCategorySelect(lang))


class HelpCog(commands.Cog):
    """/help - دليل الأوامر الكامل."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="📖 دليل كل أوامر البوت مع شرح كل أمر - Full command guide")
    async def help_cmd(self, interaction: discord.Interaction):
        lang = get_lang(interaction.guild_id)
        await interaction.response.send_message(
            embed=build_intro_embed(lang), view=HelpView(lang), ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
