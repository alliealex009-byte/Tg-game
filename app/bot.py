"""Telegram bot (aiogram 3): attractive DM hub, group commands, owner panel with broadcast,
join-request verification, referrals. Game rules live in app/games, pure helpers in verify.py / broadcast.py."""
from __future__ import annotations

import asyncio
import html
import logging
import os

from aiogram import Bot, BaseMiddleware, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    ChatJoinRequest,
    ChatMemberUpdated,
    FSInputFile,
    InlineKeyboardButton as Btn,
    InlineKeyboardMarkup as Kb,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)

from . import broadcast
from .games import GAME_INFO
from .games.base import GameError
from .verify import Verifier

log = logging.getLogger("bot")

PLAY_CMDS = {info["cmd"]: key for key, info in GAME_INFO.items()}  # e.g. {"playludo": "ludo", ...}
CATS = ["Board", "Cards", "Party", "Casino", "Brain", "Action", "Classic"]
CAT_EMOJI = {"Action": "💥", "Board": "♟", "Cards": "🃏", "Party": "🎭", "Casino": "🎰", "Brain": "🧠", "Classic": "🎲"}
BANNER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "banner.png")


def cat_of(info) -> str:
    return info.get("cat", "Classic")


def players_txt(i) -> str:
    return str(i["min"]) if i["min"] == i["max"] else f"{i['min']}-{i['max']}"


COMMANDS = (
    [BotCommand(command="start", description="Open the game hub"), BotCommand(command="games", description="List all games")]
    + [BotCommand(command=i["cmd"], description=f"{i['emoji']} {i['title']} [bet]"[:100]) for i in GAME_INFO.values()]
    + [
        BotCommand(command="profile", description="Your stats"),
        BotCommand(command="balance", description="Your coin balance"),
        BotCommand(command="daily", description="Claim your daily bonus"),
        BotCommand(command="invite", description="Invite friends, earn up to 700 coins each"),
        BotCommand(command="id", description="Show your Telegram id"),
        BotCommand(command="panel", description="Owner panel (owner only)"),
        BotCommand(command="top", description="Leaderboard"),
        BotCommand(command="help", description="How to play"),
    ]
)[:100]


def games_list(cat: str | None = None) -> str:
    out = []
    for c in CATS:
        if cat and c != cat:
            continue
        items = [i for i in GAME_INFO.values() if cat_of(i) == c]
        if not items:
            continue
        out.append(f"{CAT_EMOJI[c]} <b>{c}</b>")
        out += [f"  {i['emoji']} {i['title']} · {players_txt(i)}p · /{i['cmd']}" for i in items]
        out.append("")
    return "\n".join(out).strip()


def fmt_wait(sec: int) -> str:
    h, m = sec // 3600, (sec % 3600) // 60
    return f"{h}h {m}m" if h else f"{m}m"


class Gate(BaseMiddleware):
    """Registers the sender, blocks banned users, remembers groups the bot talks in."""

    def __init__(self, db, ensure):
        self.db, self.ensure = db, ensure

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user is not None and not user.is_bot:
            row = self.ensure(user)
            if row.get("banned"):
                if isinstance(event, CallbackQuery):
                    await event.answer("🚫 You are banned from this bot.", show_alert=True)
                return None
            chat = event.chat if isinstance(event, Message) else (event.message.chat if isinstance(event, CallbackQuery) and event.message else None)
            if chat is not None and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
                self.db.upsert_chat(chat.id, chat.title or "", chat.type.value)
        return await handler(event, data)


def build(settings, db, rooms):
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    r = Router()
    dp.include_router(r)
    ctx = {"username": "", "banner_id": None}
    verifier = Verifier()
    pending_bc: dict = {}   # admin id -> {"target": str, "src": (chat_id, msg_id) | None}
    owner_tag = f"@{settings.owner_username}"
    sister_tag = f"@{settings.sister_bot}"
    esc = html.escape

    def ensure_user(tg_user):
        name = " ".join(x for x in (tg_user.first_name, tg_user.last_name) if x) or tg_user.username or str(tg_user.id)
        return db.upsert_user(tg_user.id, name[:40], tg_user.username or f"user_{tg_user.id}", None)

    gate = Gate(db, ensure_user)
    r.message.outer_middleware(gate)
    r.callback_query.outer_middleware(gate)

    def is_admin(uid: int) -> bool:
        return uid in settings.admin_ids

    def app_link(code=None):
        if settings.app_short_name and ctx["username"]:
            base = f"https://t.me/{ctx['username']}/{settings.app_short_name}"
            return f"{base}?startapp={code}" if code else base
        return None

    def join_btn(code: str, private: bool, label: str):
        link = app_link(code)
        if link:
            return Btn(text=label, url=link)
        if private:
            return Btn(text=label, web_app=WebAppInfo(url=f"{settings.webapp_url}?room={code}"))
        return Btn(text=label, url=f"https://t.me/{ctx['username']}?start=join_{code}")  # groups can't use web_app buttons

    def hub_btn(label="🎮 Play Now"):
        link = app_link()
        return Btn(text=label, url=link) if link else Btn(text=label, web_app=WebAppInfo(url=settings.webapp_url))

    def credit_line() -> str:
        return f"👑 Owner: <b>{esc(settings.owner_name)}</b> ({owner_tag})"

    def sister_line() -> str:
        return f"🤖 Sister bot: {sister_tag} — manage groups &amp; channels"

    def main_menu(uid: int = 0) -> Kb:
        owner_row = [[Btn(text="👑 Owner Panel", callback_data="ow:home")]] if is_admin(uid) else []
        return Kb(inline_keyboard=owner_row + [
            [hub_btn("🎮 PLAY NOW")],
            [Btn(text="🕹 All Games", callback_data="m:games"), Btn(text="👤 Profile", callback_data="m:profile")],
            [Btn(text="🏆 Leaderboard", callback_data="m:top"), Btn(text="🎁 Daily Bonus", callback_data="m:daily")],
            [Btn(text="👥 Invite & Earn", callback_data="m:invite"), Btn(text="❓ How to play", callback_data="m:help")],
            [Btn(text=f"🤖 {settings.sister_bot}", url=f"https://t.me/{settings.sister_bot}"),
             Btn(text=f"👑 {settings.owner_name}", url=f"https://t.me/{settings.owner_username}")],
        ])

    def back_menu(*rows) -> Kb:
        return Kb(inline_keyboard=[*rows, [Btn(text="⬅️ Menu", callback_data="m:home")]])

    def welcome_text(u) -> str:
        return (
            f"✨ <b>Welcome, {esc(u['name'])}!</b> ✨\n\n"
            f"🎮 <b>{len(GAME_INFO)} multiplayer games</b> — Ludo, Chess, UNO, Teen Patti, Mafia, Carrom and more, "
            "played live with friends right inside Telegram.\n\n"
            f"💰 Balance: <b>{u['coins']}</b> coins   🏆 Wins: <b>{u['wins']}</b>\n\n"
            "👇 Tap <b>PLAY NOW</b>, or add me to a group and send /games\n\n"
            f"{sister_line()}\n{credit_line()}"
        )

    async def send_banner(chat_id: int, caption: str, kb: Kb):
        """Photo + caption. Telegram caches the upload, so later sends reuse the file_id."""
        try:
            photo = ctx["banner_id"] or FSInputFile(BANNER)
            m = await bot.send_photo(chat_id, photo, caption=caption, reply_markup=kb)
            if m.photo:
                ctx["banner_id"] = m.photo[-1].file_id
            return m
        except TelegramForbiddenError:
            raise
        except Exception:
            log.exception("banner send failed, falling back to text")
            return await bot.send_message(chat_id, caption, reply_markup=kb)

    async def show(cb: CallbackQuery, text: str, kb: Kb):
        msg = cb.message
        try:
            if msg.photo:
                await msg.edit_caption(caption=text[:1024], reply_markup=kb)
            else:
                await msg.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except TelegramBadRequest:
            pass  # "message is not modified"
        await cb.answer()

    # ------------------------------------------------------------------ start / menu
    @r.message(CommandStart())
    async def start(m: Message, command: CommandObject):
        u = ensure_user(m.from_user)
        arg = command.args or ""
        if arg.startswith("join_"):
            code = arg[5:].upper()
            room = rooms.get(code)
            if room is None:
                return await m.answer("😕 That game room has expired. Ask for a new one.")
            info = GAME_INFO[room.game_type]
            return await m.answer(
                f"{info['emoji']} <b>{info['title']}</b> room <code>{code}</code>\nTap below to join!",
                reply_markup=Kb(inline_keyboard=[[Btn(text="🎮 Join game", web_app=WebAppInfo(url=f"{settings.webapp_url}?room={code}"))]]),
            )
        if arg.startswith("ref_") and arg[4:].isdigit():
            ref = int(arg[4:])
            if db.set_referrer(m.from_user.id, ref, settings.referral_bonus):
                u = db.get_user(m.from_user.id)
                try:
                    await bot.send_message(ref, f"🎉 <b>{esc(u['name'])}</b> joined with your link! You earned <b>+{db.last_referral}</b> coins.")
                except Exception:
                    pass
        if m.chat.type != ChatType.PRIVATE:
            return await m.answer(f"👋 Hi! Send /games to see every game, or tap below.", reply_markup=Kb(inline_keyboard=[[hub_btn()]]))
        await send_banner(m.chat.id, welcome_text(u), main_menu(m.from_user.id))

    @r.callback_query(F.data == "m:home")
    async def cb_home(cb: CallbackQuery):
        await show(cb, welcome_text(db.get_user(cb.from_user.id)), main_menu(cb.from_user.id))

    @r.callback_query(F.data == "m:games")
    async def cb_games(cb: CallbackQuery):
        rows, row = [], []
        for c in CATS:
            if any(cat_of(i) == c for i in GAME_INFO.values()):
                row.append(Btn(text=f"{CAT_EMOJI[c]} {c}", callback_data=f"m:cat:{c}"))
                if len(row) == 2:
                    rows.append(row); row = []
        if row:
            rows.append(row)
        await show(cb, f"🕹 <b>{len(GAME_INFO)} games</b>\nPick a category:", back_menu(*rows))

    @r.callback_query(F.data.startswith("m:cat:"))
    async def cb_cat(cb: CallbackQuery):
        c = cb.data[6:]
        items = [(k, i) for k, i in GAME_INFO.items() if cat_of(i) == c]
        rows = []
        for k, i in items:
            rows.append([Btn(text=f"{i['emoji']} {i['title']} ({players_txt(i)}p)", callback_data=f"m:play:{k}")])
        rows.append([Btn(text="⬅️ Categories", callback_data="m:games")])
        await show(cb, f"{CAT_EMOJI.get(c, '🎲')} <b>{esc(c)}</b>\nTap a game to create a room, then share it with friends:", Kb(inline_keyboard=rows))

    @r.callback_query(F.data.startswith("m:play:"))
    async def cb_play(cb: CallbackQuery):
        key = cb.data[7:]
        if key not in GAME_INFO:
            return await cb.answer()
        try:
            room = rooms.create(cb.from_user.id, key, 0)
        except GameError as e:
            return await cb.answer(str(e), show_alert=True)
        i = GAME_INFO[key]
        await cb.answer()
        await bot.send_message(
            cb.message.chat.id,
            f"{i['emoji']} <b>{i['title']}</b> — room <code>{room.code}</code>\n"
            f"Players: {players_txt(i)} · Free game\n\nTap <b>Join</b> to open it. Share the room code with friends, or add computer players inside.",
            reply_markup=Kb(inline_keyboard=[[join_btn(room.code, True, f"🎮 Join {i['title']}")]]),
        )

    def profile_text(uid: int) -> str:
        u = db.get_user(uid)
        rate = f"{u['wins'] * 100 // u['games']}%" if u["games"] else "—"
        return (
            f"👤 <b>{esc(u['name'])}</b>\n\n"
            f"💰 Coins: <b>{u['coins']}</b>\n🎮 Games: <b>{u['games']}</b>\n🏆 Wins: <b>{u['wins']}</b>  ({rate})\n"
            f"🔥 Daily streak: <b>{u['streak']}</b>\n👥 Friends invited: <b>{u['refs']}</b>"
        )

    @r.callback_query(F.data == "m:profile")
    async def cb_profile(cb: CallbackQuery):
        await show(cb, profile_text(cb.from_user.id), back_menu())

    @r.message(Command("profile"))
    async def profile(m: Message):
        await m.reply(profile_text(m.from_user.id))

    def top_text() -> str:
        rows = db.leaderboard(10)
        if not rows:
            return "🏆 <b>Leaderboard</b>\n\nNo games played yet. Be the first!"
        medals = ["🥇", "🥈", "🥉"]
        lines = [f"{medals[i] if i < 3 else str(i + 1) + '.'} {esc(x['name'])} — {x['wins']} wins" for i, x in enumerate(rows)]
        return "🏆 <b>Leaderboard</b>\n\n" + "\n".join(lines)

    @r.callback_query(F.data == "m:top")
    async def cb_top(cb: CallbackQuery):
        await show(cb, top_text(), back_menu())

    @r.message(Command("top"))
    async def top(m: Message):
        await m.reply(top_text())

    def daily_text(uid: int) -> str:
        ok, coins, wait = db.claim_daily(uid)
        if ok:
            u = db.get_user(uid)
            return f"🎁 <b>+{db.last_bonus} coins!</b>\n🔥 Streak: {u['streak']} day(s) — come back daily for up to +300 extra.\n💰 Balance: <b>{coins}</b>"
        return f"⏳ Next bonus in <b>{fmt_wait(wait)}</b>.\n💰 Balance: <b>{coins}</b>"

    @r.callback_query(F.data == "m:daily")
    async def cb_daily(cb: CallbackQuery):
        await show(cb, daily_text(cb.from_user.id), back_menu())

    @r.message(Command("daily"))
    async def daily(m: Message):
        await m.reply(daily_text(m.from_user.id))

    @r.message(Command("balance"))
    async def balance(m: Message):
        u = db.get_user(m.from_user.id)
        await m.reply(f"💰 Balance: <b>{u['coins']}</b> coins\n🏆 Wins: {u['wins']} / {u['games']} games")

    def invite_text(uid: int) -> str:
        link = f"https://t.me/{ctx['username']}?start=ref_{uid}"
        u = db.get_user(uid)
        return (
            f"👥 <b>Invite &amp; Earn</b>\n\nYou get <b>{settings.referral_bonus}</b> coins for your first friend, rising by 50 with every friend up to <b>700</b> per friend "
            f"(your friend gets +{settings.referral_bonus // 2}).\n\n🔗 Your link:\n<code>{link}</code>\n\nFriends invited: <b>{u['refs']}</b>"
        )

    @r.callback_query(F.data == "m:invite")
    async def cb_invite(cb: CallbackQuery):
        link = f"https://t.me/{ctx['username']}?start=ref_{cb.from_user.id}"
        share = f"https://t.me/share/url?url={link}&text=Play%20Ludo%2C%20Chess%2C%20UNO%20and%20more%20with%20me!"
        await show(cb, invite_text(cb.from_user.id), back_menu([Btn(text="📤 Share link", url=share)]))

    @r.message(Command("invite"))
    async def invite(m: Message):
        await m.reply(invite_text(m.from_user.id))

    def help_text() -> str:
        return (
            "❓ <b>How to play</b>\n\n"
            "1️⃣ Send a game command in a group (e.g. <code>/playludo</code>) or pick a game in my DM\n"
            "2️⃣ Friends tap <b>Join</b>, the host taps <b>START</b>\n"
            "3️⃣ Add <code>100</code> after the command for a coin bet: <code>/playludo 100</code>\n\n"
            "/games · /daily · /profile · /invite · /top\n\n"
            "Coins are virtual and have no cash value.\n\n" + credit_line() + "\n" + sister_line()
        )

    @r.callback_query(F.data == "m:help")
    async def cb_help(cb: CallbackQuery):
        await show(cb, help_text(), back_menu())

    @r.message(Command("help"))
    async def help_(m: Message):
        await m.reply(help_text(), disable_web_page_preview=True)

    @r.message(Command("games"))
    async def games(m: Message):
        await m.reply(
            f"🎮 <b>{len(GAME_INFO)} games</b>\n\n" + games_list() + "\n\nAdd a number for a coin bet, e.g. <code>/playludo 100</code>"
        )

    # ------------------------------------------------------------------ creating rooms from chat commands
    async def create_game(m: Message, command: CommandObject, game_type: str):
        u = ensure_user(m.from_user)
        bet = 0
        if command.args:
            try:
                bet = int(command.args.split()[0])
            except ValueError:
                return await m.reply(f"Usage: /{GAME_INFO[game_type]['cmd']} [bet]")
        try:
            room = rooms.create(u["id"], game_type, bet)
        except GameError as e:
            return await m.reply(esc(str(e)))
        info = GAME_INFO[game_type]
        private = m.chat.type == ChatType.PRIVATE
        text = (
            f"{info['emoji']} <b>{info['title']} - New Game</b>\n\n"
            f"🔗 Room : <code>{room.code}</code>\n"
            f"👤 Host : {esc(u['name'])}\n"
            f"👥 Players : 0/{info['max']}\n"
            f"💰 Bet : {bet if bet else 'Free'}\n\n"
            "Tap the button below to join!"
        )
        await m.reply(text, reply_markup=Kb(inline_keyboard=[[join_btn(room.code, private, f"🎮 Join {info['title']}")]]))

    @r.message(Command(*PLAY_CMDS))
    async def play(m: Message, command: CommandObject):
        await create_game(m, command, PLAY_CMDS[command.command])

    # ------------------------------------------------------------------ groups: bot added / removed, welcome
    @r.my_chat_member()
    async def my_member(ev: ChatMemberUpdated):
        chat, st = ev.chat, ev.new_chat_member.status
        if chat.type == ChatType.PRIVATE:
            db.mark_dm(ev.from_user.id, st not in ("kicked", "left"))
            return
        if st in ("member", "administrator"):
            db.upsert_chat(chat.id, chat.title or "", chat.type.value)
            if chat.type == ChatType.CHANNEL:
                return
            who = esc(ev.from_user.full_name) if ev.from_user else "everyone"
            try:
                await bot.send_photo(
                    chat.id, ctx["banner_id"] or FSInputFile(BANNER),
                    caption=(
                        f"🎉 <b>Thanks for adding me, {who}!</b>\n\n"
                        f"🎮 I bring <b>{len(GAME_INFO)} multiplayer games</b> to this group — Ludo, Chess, UNO, Teen Patti, Mafia, Carrom &amp; more.\n\n"
                        "▶️ Try <code>/playludo</code> · <code>/playuno</code> · <code>/playchess</code>\n"
                        "📋 /games shows everything\n\n"
                        "🛡 Make me an admin with <i>Invite users</i> and I will verify every join request automatically (/verify on|off).\n\n"
                        f"{sister_line()}\n{credit_line()}"
                    ),
                    reply_markup=Kb(inline_keyboard=[
                        [Btn(text="🕹 All games", url=f"https://t.me/{ctx['username']}?start=go")],
                        [Btn(text=f"🤖 {settings.sister_bot}", url=f"https://t.me/{settings.sister_bot}"),
                         Btn(text=f"👑 {settings.owner_name}", url=f"https://t.me/{settings.owner_username}")],
                    ]),
                )
            except Exception:
                log.info("could not post welcome in %s", chat.id)
        elif st in ("left", "kicked"):
            db.set_chat_active(chat.id, False)

    # ------------------------------------------------------------------ join-request verification
    def verify_on(chat_id: int) -> bool:
        v = db.kv_get(f"vf:{chat_id}")
        return (db.kv_get("verify_default", "1") == "1") if v is None else v == "1"

    def challenge_kb(chat_id: int, ch) -> Kb:
        btns = [Btn(text=o, callback_data=f"vf:{chat_id}:{i}") for i, o in enumerate(ch.options)]
        return Kb(inline_keyboard=[btns[:3], btns[3:]])

    @r.chat_join_request()
    async def join_request(req: ChatJoinRequest):
        if not verify_on(req.chat.id):
            return
        uid = req.from_user.id
        if db.is_banned(uid):
            try:
                await bot.decline_chat_join_request(req.chat.id, uid)
            except Exception:
                pass
            return
        ensure_user(req.from_user)
        ch = verifier.start(uid, req.chat.id, req.chat.title or "")
        try:
            await bot.send_message(
                req.user_chat_id,
                f"🛡 <b>Verification</b>\n\nYou asked to join <b>{esc(req.chat.title or 'the group')}</b>.\n"
                f"To prove you're human:\n\n<b>{esc(ch.question)}</b>\n\n<i>3 tries · expires in 15 minutes</i>",
                reply_markup=challenge_kb(req.chat.id, ch),
            )
        except Exception:
            log.info("could not DM verification to %s", uid)
            verifier.cancel(uid, req.chat.id)  # request stays pending for the admins to decide

    @r.callback_query(F.data.startswith("vf:"))
    async def verify_cb(cb: CallbackQuery):
        try:
            _, chat_s, idx_s = cb.data.split(":")
            chat_id, idx = int(chat_s), int(idx_s)
        except ValueError:
            return await cb.answer()
        uid = cb.from_user.id
        title = verifier.title(uid, chat_id)
        res, nxt = verifier.check(uid, chat_id, idx)
        if res == "none":
            await cb.answer("This verification expired. Send your join request again.", show_alert=True)
            return await cb.message.edit_text("⌛ Verification expired. Request to join again.")
        if res == "ok":
            db.set_verified(uid)
            try:
                await bot.approve_chat_join_request(chat_id, uid)
                msg = f"✅ <b>Verified!</b> You're in <b>{esc(title)}</b>. Welcome!"
            except Exception:
                msg = "✅ Verified! An admin will let you in shortly."
            await cb.message.edit_text(msg + f"\n\n🎮 While you're here, try the games:", reply_markup=Kb(inline_keyboard=[[hub_btn("🎮 Open Game Hub")]]))
            return await cb.answer("Verified ✅")
        if res == "wrong":
            await cb.answer("❌ Wrong, try again", show_alert=False)
            return await cb.message.edit_text(
                f"🛡 <b>Verification</b>\n\n❌ Not quite. New question:\n\n<b>{esc(nxt.question)}</b>",
                reply_markup=challenge_kb(chat_id, nxt),
            )
        try:
            await bot.decline_chat_join_request(chat_id, uid)
        except Exception:
            pass
        await cb.answer("Verification failed", show_alert=True)
        await cb.message.edit_text("🚫 Verification failed 3 times, so your join request was declined. You can request again later.")

    @r.message(Command("verify"))
    async def verify_cmd(m: Message, command: CommandObject):
        if m.chat.type == ChatType.PRIVATE:
            return await m.reply("Use this in your group or channel discussion chat, where I am an admin.")
        mem = await bot.get_chat_member(m.chat.id, m.from_user.id)
        if mem.status not in ("creator", "administrator") and not is_admin(m.from_user.id):
            return
        a = (command.args or "").strip().lower()
        if a in ("on", "off"):
            db.kv_set(f"vf:{m.chat.id}", "1" if a == "on" else "0")
        state = "ON ✅" if verify_on(m.chat.id) else "OFF ⛔"
        await m.reply(
            f"🛡 Join-request verification is <b>{state}</b>\n"
            "I DM each person who requests to join a captcha and approve them when they pass.\n"
            "Requirement: I must be an admin with the <i>Invite users</i> permission and the group needs <i>Approve new members</i> turned on.\n"
            "Change it with <code>/verify on</code> or <code>/verify off</code>."
        )

    # ------------------------------------------------------------------ owner panel
    def panel_kb() -> Kb:
        vd = "ON" if db.kv_get("verify_default", "1") == "1" else "OFF"
        return Kb(inline_keyboard=[
            [Btn(text="📊 Stats", callback_data="ow:stats"), Btn(text="📢 Broadcast", callback_data="ow:bc")],
            [Btn(text="👥 Groups", callback_data="ow:chats"), Btn(text=f"🛡 Verification: {vd}", callback_data="ow:vf")],
            [Btn(text="🛠 Commands", callback_data="ow:help")],
            [Btn(text="🖥 Open in Mini App", web_app=WebAppInfo(url=settings.webapp_url + "?owner=1"))],
        ])

    def stats_text() -> str:
        s = db.stats()
        return (
            "📊 <b>Stats</b>\n\n"
            f"👥 Users: <b>{s['users']}</b> (+{s['new_today']} today)\n🚫 Banned: {s['banned']}\n"
            f"💬 Active groups/channels: <b>{s['chats']}</b>\n🎮 Matches: <b>{s['matches']}</b>\n"
            f"🏠 Live rooms: {len(rooms.rooms)}\n💰 Coins in circulation: {s['coins_in_circulation']}"
        )

    @r.message(Command("id"))
    async def my_id(m: Message):
        await m.reply(f"🆔 Your Telegram id: <code>{m.from_user.id}</code>\nOwner? Put it in <code>ADMIN_IDS</code> in the server's .env, then restart.")

    @r.message(Command("panel", "owner"))
    async def panel(m: Message):
        if not is_admin(m.from_user.id):
            return await m.reply(
                "🔒 Owner panel is for the bot owner only.\n"
                f"If you are the owner: send /id, copy your number into <code>ADMIN_IDS</code> in .env and restart the bot."
            )
        if m.chat.type != ChatType.PRIVATE:
            return await m.reply("Open the panel in my DM.")
        await m.answer(f"👑 <b>Owner panel</b> — {esc(settings.owner_name)}", reply_markup=panel_kb())

    @r.callback_query(F.data.startswith("ow:"))
    async def owner_cb(cb: CallbackQuery):
        uid = cb.from_user.id
        if not is_admin(uid):
            return await cb.answer("Owner only", show_alert=True)
        act = cb.data[3:]
        back = Kb(inline_keyboard=[[Btn(text="⬅️ Panel", callback_data="ow:home")]])
        if act == "home":
            pending_bc.pop(uid, None)
            return await show(cb, f"👑 <b>Owner panel</b> — {esc(settings.owner_name)}", panel_kb())
        if act == "stats":
            return await show(cb, stats_text(), back)
        if act == "chats":
            rows = db.c.execute("SELECT title,type FROM chats WHERE active=1 ORDER BY added DESC LIMIT 30").fetchall()
            body = "\n".join(f"• {esc(x['title'] or '?')} <i>({x['type']})</i>" for x in rows) or "None yet. Add me to a group!"
            return await show(cb, f"💬 <b>Groups</b>\n\n{body}", back)
        if act == "vf":
            db.kv_set("verify_default", "0" if db.kv_get("verify_default", "1") == "1" else "1")
            return await show(cb, f"👑 <b>Owner panel</b> — {esc(settings.owner_name)}\nDefault join verification updated.", panel_kb())
        if act == "help":
            return await show(cb, (
                "🛠 <b>Owner commands</b>\n\n"
                "<code>/addcoins id amount</code> — give (or take with −) coins\n"
                "<code>/ban id</code> · <code>/unban id</code>\n"
                "<code>/user id</code> — look a player up\n"
                "<code>/broadcast users|groups|all</code> — then send the message\n"
                "<code>/stats</code> · <code>/panel</code>\n\n"
                "Group admins: <code>/verify on|off</code>"), back)
        if act == "bc":
            kb = Kb(inline_keyboard=[
                [Btn(text="👤 Users (DM)", callback_data="ow:bct:users"), Btn(text="👥 Groups", callback_data="ow:bct:groups")],
                [Btn(text="🌍 Everyone", callback_data="ow:bct:all")],
                [Btn(text="⬅️ Panel", callback_data="ow:home")],
            ])
            return await show(cb, "📢 <b>Broadcast</b>\nWho should receive it?", kb)
        if act.startswith("bct:"):
            pending_bc[uid] = {"target": act[4:], "src": None}
            return await show(cb, f"📢 Target: <b>{act[4:]}</b>\n\nNow send me the message to broadcast (text, photo, video, anything). /cancel to abort.", back)
        if act == "no":
            pending_bc.pop(uid, None)
            return await show(cb, "❌ Cancelled.", back)
        if act == "go":
            st = pending_bc.pop(uid, None)
            if not st or not st.get("src"):
                return await cb.answer("Nothing to send", show_alert=True)
            await cb.answer("Sending…")
            asyncio.create_task(do_broadcast(cb.message, uid, st))

    def targets_for(kind: str) -> list:
        t = []
        if kind in ("users", "all"):
            t += db.user_ids()
        if kind in ("groups", "all"):
            t += db.chat_ids()
        return t

    async def do_broadcast(status_msg: Message, admin: int, st: dict):
        src_chat, src_msg = st["src"]
        targets = targets_for(st["target"])

        async def send(t):
            try:
                await bot.copy_message(t, src_chat, src_msg)
                return "ok"
            except TelegramRetryAfter as e:
                return ("retry", e.retry_after)
            except TelegramForbiddenError:
                return "blocked"
            except TelegramBadRequest:
                return "gone"
            except Exception:
                return "fail"

        async def progress(i, n):
            try:
                await status_msg.edit_text(f"📢 Sending… {i}/{n}")
            except Exception:
                pass

        res = await broadcast.run(targets, send, 0.05, progress)
        for t in res["blocked_ids"] + res["gone_ids"]:
            if t > 0:
                db.mark_dm(t, False)
            else:
                db.set_chat_active(t, False)
        try:
            await status_msg.edit_text(
                f"✅ <b>Broadcast done</b>\n\nDelivered: <b>{res['ok']}</b> / {res['total']}\n"
                f"Blocked/removed: {res['blocked'] + res['gone']}\nFailed: {res['fail']}"
            )
        except Exception:
            pass

    @r.message(Command("broadcast"))
    async def broadcast_cmd(m: Message, command: CommandObject):
        if not is_admin(m.from_user.id):
            return
        a = (command.args or "").strip().lower()
        if a not in ("users", "groups", "all"):
            return await m.reply("Usage: /broadcast users|groups|all\nThen send the message you want delivered.")
        pending_bc[m.from_user.id] = {"target": a, "src": None}
        await m.reply(f"📢 Target: <b>{a}</b> ({len(targets_for(a))} chats).\nSend the message now. /cancel to abort.")

    @r.message(Command("cancel"))
    async def cancel(m: Message):
        if pending_bc.pop(m.from_user.id, None):
            await m.reply("❌ Broadcast cancelled.")

    @r.message(lambda m: m.from_user is not None and m.from_user.id in pending_bc and pending_bc[m.from_user.id]["src"] is None
               and not (m.text or "").startswith("/"))
    async def capture_broadcast(m: Message):
        st = pending_bc[m.from_user.id]
        st["src"] = (m.chat.id, m.message_id)
        n = len(targets_for(st["target"]))
        await m.reply(
            f"👆 That message will be sent to <b>{n}</b> chat(s) ({st['target']}). Confirm?",
            reply_markup=Kb(inline_keyboard=[[Btn(text="✅ Send now", callback_data="ow:go"), Btn(text="❌ Cancel", callback_data="ow:no")]]),
        )

    @r.message(Command("addcoins"))
    async def addcoins(m: Message, command: CommandObject):
        if not is_admin(m.from_user.id):
            return
        try:
            uid, amount = (int(x) for x in (command.args or "").split()[:2])
        except ValueError:
            return await m.reply("Usage: /addcoins <user_id> <amount>")
        new = db.add_coins(uid, amount, f"admin:{m.from_user.id}")
        await m.reply("Done. New balance: %s" % new if new is not None else "Failed (unknown user or negative balance)")

    @r.message(Command("ban", "unban"))
    async def ban(m: Message, command: CommandObject):
        if not is_admin(m.from_user.id):
            return
        arg = (command.args or "").strip()
        if not arg.lstrip("-").isdigit():
            return await m.reply(f"Usage: /{command.command} <user_id>")
        uid = int(arg)
        if is_admin(uid):
            return await m.reply("Can't ban an owner.")
        ok = db.set_ban(uid, command.command == "ban")
        await m.reply(("🚫 Banned " if command.command == "ban" else "✅ Unbanned ") + str(uid) if ok else "Unknown user id.")

    @r.message(Command("user"))
    async def user_cmd(m: Message, command: CommandObject):
        if not is_admin(m.from_user.id):
            return
        arg = (command.args or "").strip()
        u = db.get_user(int(arg)) if arg.isdigit() else None
        if not u:
            return await m.reply("Usage: /user <user_id> (unknown id?)")
        await m.reply(
            f"👤 <b>{esc(u['name'])}</b> (@{esc(u['username'] or '-')}) <code>{u['id']}</code>\n💰 {u['coins']} · 🎮 {u['games']} · 🏆 {u['wins']}\n"
            f"🔥 streak {u['streak']} · 👥 refs {u['refs']} · 🚫 banned {bool(u['banned'])}"
        )

    @r.message(Command("stats"))
    async def stats(m: Message):
        if is_admin(m.from_user.id):
            await m.reply(stats_text())

    return bot, dp, ctx


async def prepare(bot: Bot, settings, ctx):
    """Fetch the bot username, register commands, descriptions and the menu button."""
    me = await bot.get_me()
    ctx["username"] = me.username
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_my_commands(COMMANDS)
    try:
        await bot.set_my_short_description(f"{len(GAME_INFO)}+ multiplayer games: Ludo, Chess, UNO, Teen Patti, Mafia. Owner: @{settings.owner_username}")
        await bot.set_my_description(
            f"🎮 {len(GAME_INFO)} multiplayer games right inside Telegram — Ludo, Chess, UNO, Teen Patti, Mafia, Carrom and more.\n"
            f"Owner: {settings.owner_name} (@{settings.owner_username}) · Sister bot: @{settings.sister_bot}"
        )
    except Exception:
        log.info("could not set bot descriptions")
    if settings.webapp_url.startswith("https://"):
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="🎮 Play", web_app=WebAppInfo(url=settings.webapp_url))
        )
    else:
        log.warning("WEBAPP_URL must be an https:// URL for Telegram mini apps")
