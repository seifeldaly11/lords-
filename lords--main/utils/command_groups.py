from discord import app_commands


admin_group = app_commands.Group(
    name="admin",
    description="⚙️ أدوات إدارة السيرفر والتتبع | Server administration tools"
)
admin_monster_group = app_commands.Group(
    name="monster",
    description="🐲 إدارة دليل الوحوش | Manage monster guides",
    parent=admin_group,
)
admin_guide_group = app_commands.Group(
    name="guide",
    description="📖 إدارة الشروحات | Manage guides",
    parent=admin_group,
)
admin_reply_group = app_commands.Group(
    name="reply",
    description="💬 إدارة الردود الجاهزة | Manage canned replies",
    parent=admin_group,
)
admin_welcome_group = app_commands.Group(
    name="welcome",
    description="👋 إدارة رسائل الترحيب | Manage welcome messages",
    parent=admin_group,
)
admin_track_group = app_commands.Group(
    name="track",
    description="📊 تتبع نشاط التحالف | Track alliance activity",
    parent=admin_group,
)
admin_channel_group = app_commands.Group(
    name="channel",
    description="📍 ضبط قنوات البوت | Configure bot channels",
    parent=admin_group,
)

shop_group = app_commands.Group(
    name="shop",
    description="🛍️ متجر الحسابات | Accounts shop"
)
