"""Telegram bot (aiogram 3). Creates rooms from chat commands and links players into the mini app."""
from __future__ import annotations

import html
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)

from .games import GAME_INFO
from .games.base import GameError

log = logging.getLogger("bot")

PLAY_CMDS = {info["cmd"]: key for key, info in GAME_INFO.items()}  # e.g. {"playludo": "ludo", ...}

COMMANDS = (
    [BotCommand(command="start", description="Open the game hub"), BotCommand(command="games", description="List all games")]
    + [BotCommand(command=i["cmd"], description=f"{i['emoji']} Start {i['title']}: /{i['cmd']} [bet]") for i in GAME_INFO.values()]
    + [
        BotCommand(command="balance", description="Your coin balance"),
        BotCommand(command="daily", description="Claim your daily bonus"),
        BotCommand(command="top", description="Leaderboard"),
        BotCommand(command="help", description="How to play"),
    ]
)


def games_list() -> str:
    return "\n".join(
        f"{i['emoji']} <b>{i['title']}</b> ({i['min'] if i['min'] == i['max'] else str(i['min']) + '-' + str(i['max'])} players): /{i['cmd']} [bet]"
        for i in GAME_INFO.values()
    )


def fmt_wait(sec: int) -> str:
    h, m = sec // 3600, (sec % 3600) // 60
    return f"{h}h {m}m" if h else f"{m}m"


def build(settings, db, rooms):
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    r = Router()
    dp.include_router(r)
    ctx = {"username": ""}

    def ensure_user(tg_user):
        name = " ".join(x for x in (tg_user.first_name, tg_user.last_name) if x) or tg_user.username or str(tg_user.id)
        return db.upsert_user(tg_user.id, name[:40], tg_user.username or f"user_{tg_user.id}", None)

    def app_link(code=None):
        if settings.app_short_name and ctx["username"]:
            base = f"https://t.me/{ctx['username']}/{settings.app_short_name}"
            return f"{base}?startapp={code}" if code else base
        return None

    def join_markup(code: str, private: bool, label: str):
        link = app_link(code)
        if link:
            btn = InlineKeyboardButton(text=label, url=link)
        elif private:
            btn = InlineKeyboardButton(text=label, web_app=WebAppInfo(url=f"{settings.webapp_url}?room={code}"))
        else:  # groups can't use web_app buttons: bounce through a private chat
            btn = InlineKeyboardButton(text=label, url=f"https://t.me/{ctx['username']}?start=join_{code}")
        return InlineKeyboardMarkup(inline_keyboard=[[btn]])

    def hub_markup():
        link = app_link()
        if link:
            btn = InlineKeyboardButton(text="🎮 Open Game Hub", url=link)
        else:
            btn = InlineKeyboardButton(text="🎮 Open Game Hub", web_app=WebAppInfo(url=settings.webapp_url))
        return InlineKeyboardMarkup(inline_keyboard=[[btn]])

    @r.message(CommandStart())
    async def start(m: Message, command: CommandObject):
        u = ensure_user(m.from_user)
        arg = command.args or ""
        if arg.startswith("join_"):
            code = arg[5:].upper()
            room = rooms.get(code)
            if room is None:
                return await m.answer("😕 That game room has expired. Ask for a new one.")
            return await m.answer(
                f"🎲 <b>{room.game_type.title()}</b> room <code>{code}</code>\nTap below to join!",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="🎮 Join game", web_app=WebAppInfo(url=f"{settings.webapp_url}?room={code}"))]]
                ),
            )
        await m.answer(
            f"👋 Welcome, <b>{html.escape(u['name'])}</b>!\n\n"
            f"💰 You have <b>{u['coins']}</b> coins.\n"
            "Play Ludo, Carrom, Snakes &amp; Ladders and more with friends. In a group, use /games to see every game and its command.",
            reply_markup=hub_markup(),
        )

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
            return await m.reply(html.escape(str(e)))
        info = GAME_INFO[game_type]
        private = m.chat.type == ChatType.PRIVATE
        text = (
            f"{info['emoji']} <b>{info['title']} - New Game</b>\n\n"
            f"🔗 Room : <code>{room.code}</code>\n"
            f"👤 Host : {html.escape(u['name'])}\n"
            f"👥 Players : 0/{info['max']}\n"
            f"💰 Bet : {bet if bet else 'Free'}\n\n"
            "Tap the button below to join!"
        )
        await m.reply(text, reply_markup=join_markup(room.code, private, f"🎮 Join {info['title']}"))

    @r.message(Command(*PLAY_CMDS))
    async def play(m: Message, command: CommandObject):
        await create_game(m, command, PLAY_CMDS[command.command])

    @r.message(Command("games"))
    async def games(m: Message):
        await m.reply("🎮 <b>Games</b>\n\n" + games_list() + "\n\nAdd a number for a coin bet, e.g. <code>/playludo 100</code>")

    @r.message(Command("balance"))
    async def balance(m: Message):
        u = ensure_user(m.from_user)
        await m.reply(f"💰 Balance: <b>{u['coins']}</b> coins\n🏆 Wins: {u['wins']} / {u['games']} games")

    @r.message(Command("daily"))
    async def daily(m: Message):
        u = ensure_user(m.from_user)
        ok, coins, wait = db.claim_daily(u["id"])
        if ok:
            await m.reply(f"🎁 +{settings.daily_bonus} coins! Balance: <b>{coins}</b>")
        else:
            await m.reply(f"⏳ Come back in {fmt_wait(wait)} for your next bonus.")

    @r.message(Command("top"))
    async def top(m: Message):
        rows = db.leaderboard(10)
        if not rows:
            return await m.reply("No games played yet. Be the first!")
        lines = [f"{i}. {html.escape(x['name'])} — {x['wins']} wins" for i, x in enumerate(rows, 1)]
        await m.reply("🏆 <b>Leaderboard</b>\n\n" + "\n".join(lines))

    @r.message(Command("help"))
    async def help_(m: Message):
        await m.reply(
            "🎮 <b>How to play</b>\n\n"
            + games_list() + "\n\n"
            "/games — list all games\n"
            "/daily — free daily coins\n"
            "/balance — your coins\n"
            "/top — leaderboard\n\n"
            "Coins are virtual and have no cash value."
        )

    @r.message(Command("addcoins"))
    async def addcoins(m: Message, command: CommandObject):
        if m.from_user.id not in settings.admin_ids:
            return
        try:
            uid, amount = (int(x) for x in (command.args or "").split()[:2])
        except ValueError:
            return await m.reply("Usage: /addcoins <user_id> <amount>")
        new = db.add_coins(uid, amount, f"admin:{m.from_user.id}")
        await m.reply("Done. New balance: %s" % new if new is not None else "Failed (unknown user or negative balance)")

    @r.message(Command("stats"))
    async def stats(m: Message):
        if m.from_user.id not in settings.admin_ids:
            return
        s = db.stats()
        await m.reply(
            f"👥 Users: {s['users']}\n🎮 Matches: {s['matches']}\n"
            f"💰 Coins in circulation: {s['coins_in_circulation']}\n🏠 Live rooms: {len(rooms.rooms)}"
        )

    return bot, dp, ctx


async def prepare(bot: Bot, settings, ctx):
    """Fetch the bot username, register commands and the menu button."""
    me = await bot.get_me()
    ctx["username"] = me.username
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_my_commands(COMMANDS)
    if settings.webapp_url.startswith("https://"):
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="🎮 Play", web_app=WebAppInfo(url=settings.webapp_url))
        )
    else:
        log.warning("WEBAPP_URL must be an https:// URL for Telegram mini apps")
