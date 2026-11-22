"""Runs app/bot.py against stub aiogram classes (aiogram isn't needed to run the tests).
Catches NameErrors/typos in handler bodies and checks the owner/verification/broadcast flows."""
import asyncio
import sys
import types
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock


def install_stubs():
    class Obs:
        def __init__(self, store, kind): self.store, self.kind = store, kind
        def __call__(self, *a, **k):
            def deco(fn):
                self.store.append((self.kind, fn, a))
                return fn
            return deco
        def outer_middleware(self, mw): pass

    class Router:
        def __init__(self):
            self.handlers = []
            self.message = Obs(self.handlers, "message"); self.callback_query = Obs(self.handlers, "cb")
            self.my_chat_member = Obs(self.handlers, "mcm"); self.chat_join_request = Obs(self.handlers, "jr")

    class Dispatcher:
        def __init__(self): pass
        def include_router(self, r): self.router = r
        def errors(self, *a, **k): return lambda f: f

    class Bot:
        def __init__(self, *a, **k):
            for n in ("send_message", "send_photo", "copy_message", "approve_chat_join_request", "decline_chat_join_request", "get_chat_member"):
                setattr(self, n, AsyncMock())

    class Simple:
        def __init__(self, *a, **k): self.__dict__.update(k); self.a = a

    class FMeta:
        def __getattr__(self, n): return self
        def __eq__(self, o): return self
        def startswith(self, *a): return self

    class Base(Exception):
        def __init__(self, *a, **k): super().__init__("x"); self.retry_after = 1

    def mod(name, **attrs):
        m = types.ModuleType(name); m.__dict__.update(attrs); sys.modules[name] = m; return m

    class CT(str):
        pass   # real aiogram: Chat.type is a plain str, there is no .value
    mod("aiogram", Bot=Bot, BaseMiddleware=object, Dispatcher=Dispatcher, F=FMeta(), Router=Router)
    mod("aiogram.client"); mod("aiogram.client.default", DefaultBotProperties=Simple)
    mod("aiogram.enums", ChatType=NS(PRIVATE=CT("private"), GROUP=CT("group"), SUPERGROUP=CT("supergroup"), CHANNEL=CT("channel")),
        ParseMode=NS(HTML="HTML"))
    mod("aiogram.exceptions", TelegramBadRequest=type("BR", (Exception,), {}), TelegramForbiddenError=type("FB", (Exception,), {}),
        TelegramRetryAfter=type("RA", (Exception,), {}))
    mod("aiogram.filters", Command=lambda *a, **k: ("cmd", a), CommandObject=object, CommandStart=lambda *a, **k: ("start",))
    types_ = {n: Simple for n in ("BotCommand", "CallbackQuery", "ChatJoinRequest", "ChatMemberUpdated", "FSInputFile", "MenuButtonWebApp", "Message", "WebAppInfo")}
    mod("aiogram.types", InlineKeyboardButton=Simple, InlineKeyboardMarkup=Simple, **types_)


install_stubs()
from app import bot as botmod  # noqa: E402
from app.config import Settings  # noqa: E402
from app.db import DB  # noqa: E402
from app.rooms import RoomManager  # noqa: E402


def msg(uid, text="", chat=None, cid=None):
    m = MagicMock()
    m.from_user = NS(id=uid, first_name="U%d" % uid, last_name=None, username="u%d" % uid, is_bot=False, full_name="U%d" % uid)
    m.chat = NS(id=cid or uid, type=chat or sys.modules["aiogram.enums"].ChatType.PRIVATE, title="Grp")
    m.message_id = 7
    m.text = text
    for n in ("answer", "reply", "edit_text", "edit_caption"):
        setattr(m, n, AsyncMock())
    m.photo = None
    return m


def cbq(uid, data):
    c = MagicMock()
    c.from_user = NS(id=uid, first_name="U", last_name=None, username="u", is_bot=False)
    c.data = data
    c.answer = AsyncMock()
    c.message = msg(uid)
    return c


class BotHandlerTests(unittest.TestCase):
    def setUp(self):
        self.s = Settings(bot_token="t", webapp_url="https://x.y", admin_ids=(1,), db_path=":memory:")
        self.db = DB(":memory:", 1000, 200)
        self.rooms = RoomManager(self.db, self.s)
        self.bot, self.dp, self.ctx = botmod.build(self.s, self.db, self.rooms)
        self.ctx["username"] = "TestBot"
        self.h = {fn.__name__: fn for _, fn, _ in self.dp.router.handlers}
        for u in (1, 2, 3):
            self.db.upsert_user(u, f"u{u}", f"u{u}", None)

    def run_(self, coro):
        return asyncio.run(coro)

    def test_all_handlers_registered(self):
        for n in ("start", "cb_home", "cb_games", "cb_cat", "cb_play", "join_request", "verify_cb", "owner_cb", "broadcast_cmd", "my_member"):
            self.assertIn(n, self.h)

    def test_start_sends_banner_with_credit(self):
        m = msg(2)
        self.run_(self.h["start"](m, NS(args="")))
        kw = self.bot.send_photo.call_args
        cap = kw.kwargs["caption"]
        self.assertIn("Advik_prakashh", cap)
        self.assertIn("Groupingabot", cap)

    def test_referral(self):
        self.run_(self.h["start"](msg(3), NS(args="ref_2")))
        self.assertEqual(self.db.get_user(2)["refs"], 1)

    def test_menu_pages(self):
        for d in ("home", "games", "profile", "top", "daily", "invite", "help"):
            c = cbq(2, "m:" + d)
            self.run_(self.h["cb_" + d](c))
        c = cbq(2, "m:cat:Classic")
        self.run_(self.h["cb_cat"](c))

    def test_play_from_dm(self):
        key = next(iter(botmod.GAME_INFO))
        c = cbq(2, "m:play:" + key)
        self.run_(self.h["cb_play"](c))
        self.assertEqual(len(self.rooms.rooms), 1)
        self.assertTrue(self.bot.send_message.called)

    def test_owner_gate(self):
        c = cbq(2, "ow:stats")
        self.run_(self.h["owner_cb"](c))
        c.answer.assert_called()
        self.assertEqual(c.answer.call_args.args[0], "Owner only")

    def test_owner_panel_pages(self):
        for a in ("home", "stats", "chats", "vf", "help", "bc"):
            self.run_(self.h["owner_cb"](cbq(1, "ow:" + a)))
        self.assertEqual(self.db.kv_get("verify_default"), "0")

    def test_broadcast_flow(self):
        self.db.upsert_chat(-55, "G", "supergroup")
        self.run_(self.h["broadcast_cmd"](msg(1, "/broadcast all"), NS(args="all")))
        self.run_(self.h["capture_broadcast"](msg(1, "hello")))
        go = cbq(1, "ow:go")

        async def flow():
            await self.h["owner_cb"](go)
            await asyncio.sleep(1.0)
        # speed up: patch the delay used inside run
        import app.broadcast as b
        orig = b.run

        async def fast(t, s, d=0.05, p=None, c=None):
            return await orig(t, s, 0, p, c)
        botmod.broadcast.run = fast
        try:
            self.run_(flow())
        finally:
            botmod.broadcast.run = orig
        self.assertEqual(self.bot.copy_message.call_count, 4)  # 3 users + 1 group

    def test_ban_blocks(self):
        self.run_(self.h["ban"](msg(1), NS(args="2", command="ban")))
        self.assertTrue(self.db.is_banned(2))
        self.run_(self.h["ban"](msg(1), NS(args="1", command="ban")))
        self.assertFalse(self.db.is_banned(1))

    def test_verification_flow(self):
        req = NS(chat=NS(id=-100, title="Club"), from_user=NS(id=2, first_name="B", last_name=None, username="b", is_bot=False), user_chat_id=2)
        self.run_(self.h["join_request"](req))
        self.assertTrue(self.bot.send_message.called)
        v = None
        # find the verifier through a wrong answer then the right one
        ch = self.bot.send_message.call_args.kwargs["reply_markup"]
        self.assertTrue(ch)
        # brute-force: pressing every option once must end in ok at some point or fail after 3
        approved = False
        for i in range(6):
            c = cbq(2, f"vf:-100:{i}")
            self.run_(self.h["verify_cb"](c))
            if self.bot.approve_chat_join_request.called:
                approved = True
                break
            if self.bot.decline_chat_join_request.called:
                break
        self.assertTrue(approved or self.bot.decline_chat_join_request.called)

    def test_verification_off(self):
        self.db.kv_set("verify_default", "0")
        req = NS(chat=NS(id=-100, title="Club"), from_user=NS(id=2, first_name="B", last_name=None, username="b", is_bot=False), user_chat_id=2)
        self.run_(self.h["join_request"](req))
        self.assertFalse(self.bot.send_message.called)

    def test_group_added_welcome(self):
        ev = NS(chat=NS(id=-9, type=sys.modules["aiogram.enums"].ChatType.SUPERGROUP, title="Fun"), new_chat_member=NS(status="member"), old_chat_member=NS(status="left"), from_user=NS(id=2, full_name="Bob", id_=2))
        self.run_(self.h["my_member"](ev))
        self.assertIn(-9, self.db.chat_ids())
        self.assertIn("Groupingabot", self.bot.send_photo.call_args.kwargs["caption"])

    def _group_msg(self, uid=2):
        return msg(uid, chat=sys.modules["aiogram.enums"].ChatType.SUPERGROUP, cid=-55)

    def test_group_picker_and_room(self):
        m = self._group_msg()
        self.run_(self.h["play_picker"](m))
        kb = m.answer.call_args.kwargs["reply_markup"].inline_keyboard
        data = [b.callback_data for row in kb for b in row if getattr(b, "callback_data", None)]
        self.assertIn("gp:ludo", data)
        self.assertIn("gp:uno", data)
        self.assertNotIn("gp:poker", data)                      # curated list only
        c = cbq(2, "gp:ludo"); c.message = self._group_msg()
        self.run_(self.h["cb_group_play"](c))
        self.assertEqual(len(self.rooms.rooms), 1)
        btn = c.message.answer.call_args.kwargs["reply_markup"].inline_keyboard[0][0]
        self.assertIn("?start=join_", btn.url)                  # groups can't open web_app buttons
        m2 = self._group_msg()
        self.run_(self.h["rooms_cmd"](m2))
        self.assertIn("Open rooms", m2.reply.call_args.args[0])

    def test_group_start_and_addgroup(self):
        m = self._group_msg()
        self.run_(self.h["start"](m, NS(args="")))
        self.assertTrue(m.answer.called)
        m2 = msg(2)
        self.run_(self.h["addgroup"](m2))
        url = m2.reply.call_args.kwargs["reply_markup"].inline_keyboard[0][0].url
        self.assertIn("startgroup=", url)
        self.assertIn("admin=", url)

    def test_join_buttons_follow_app_detection(self):
        self.ctx["app_ok"], self.ctx["app_short"] = False, "play"
        m = msg(2)
        self.run_(self.h["create_cmd"](m, NS(args=None, command="playludo"))) if "create_cmd" in self.h else None
        c = cbq(2, "m:play:ludo")
        self.run_(self.h["cb_play"](c))
        b = self.bot.send_message.call_args.kwargs["reply_markup"].inline_keyboard[0][0]
        self.assertTrue(hasattr(b, "web_app") and b.web_app is not None)   # private chat: web_app button
        self.ctx["app_ok"] = True
        c = cbq(2, "m:play:ludo")
        self.run_(self.h["cb_play"](c))
        b = self.bot.send_message.call_args.kwargs["reply_markup"].inline_keyboard[0][0]
        self.assertIn("t.me/TestBot/play?startapp=", b.url)

    def test_gate_middleware_in_group(self):
        """Regression: Gate used chat.type.value, which crashes in groups (type is a plain str)."""
        gate = botmod.Gate(self.db, lambda u: {"id": u.id})
        m = self._group_msg()
        m.__class__ = botmod.Message if isinstance(botmod.Message, type) else m.__class__
        called = []

        async def handler(ev, data):
            called.append(1)
        self.run_(gate(handler, m, {}))
        self.assertEqual(called, [1])

    def test_arcade_in_group_and_deeplink(self):
        g = self._group_msg()
        self.run_(self.h["arcade_cmd"](g))
        kb = g.answer.call_args.kwargs["reply_markup"].inline_keyboard
        urls = [b.url for row in kb for b in row]
        self.assertEqual(len(urls), 24)
        self.assertTrue(all("start=arc_" in u for u in urls))            # groups can't open web_app buttons
        m = msg(2)
        self.run_(self.h["start"](m, NS(args="arc_bricks")))
        b = self.bot.send_photo.call_args.kwargs["reply_markup"].inline_keyboard[0][0]
        self.assertIn("?arcade=bricks", b.web_app.url)
        self.assertIn("Groupingabot", self.bot.send_photo.call_args.kwargs["caption"])
        p = msg(2)
        self.run_(self.h["arcade_cmd"](p))
        b = p.answer.call_args.kwargs["reply_markup"].inline_keyboard[0][0]
        self.assertIsNotNone(b.web_app)

    def test_per_game_command_and_cover(self):
        import os
        for k, _, _ in botmod.ARCADE:
            self.assertTrue(os.path.exists(os.path.join(botmod.COVERS, k + ".png")), k)
        m = msg(2, "/snake")
        self.run_(self.h["arcade_one"](m, NS(command="snake")))
        kb = self.bot.send_photo.call_args.kwargs["reply_markup"].inline_keyboard
        self.assertIn("?arcade=snake", kb[0][0].web_app.url)
        g = self._group_msg()
        self.run_(self.h["arcade_one"](g, NS(command="memoflip")))
        kb = self.bot.send_photo.call_args.kwargs["reply_markup"].inline_keyboard
        self.assertTrue(kb[0][0].url.endswith("arc_memoflip_n55"))
        self.assertIn("AAKASH", self.bot.send_photo.call_args.kwargs["caption"])

    def test_owner_give_commands(self):
        before = self.db.get_user(2)["coins"]
        self.run_(self.h["give"](msg(2, "/give"), NS(args="2 500")))                 # non-owner: ignored
        self.assertEqual(self.db.get_user(2)["coins"], before)
        m = msg(1, "/give")
        self.run_(self.h["give"](m, NS(args="@u2 500")))
        self.assertEqual(self.db.get_user(2)["coins"], before + 500)
        r = msg(1, "/give")
        r.reply_to_message = NS(from_user=NS(id=3))
        self.run_(self.h["give"](r, NS(args="50")))
        self.assertEqual(self.db.get_user(3)["coins"], 1050)
        b3 = self.db.get_user(3)["coins"]
        self.run_(self.h["giveall"](msg(1, "/giveall"), NS(args="10")))
        self.assertEqual(self.db.get_user(3)["coins"], b3 + 10)
        grp = sys.modules["aiogram.enums"].ChatType.SUPERGROUP
        self.db.chat_user_add(-100, 2)
        b2, b3 = self.db.get_user(2)["coins"], self.db.get_user(3)["coins"]
        self.run_(self.h["givegroup"](msg(1, "/givegroup", chat=grp, cid=-100), NS(args="25")))
        self.assertEqual(self.db.get_user(2)["coins"], b2 + 25)
        self.assertEqual(self.db.get_user(3)["coins"], b3)                           # not in that group

    def test_group_arcade_board(self):
        self.assertEqual(botmod.parse_arc("snake_n1001234"), ("snake", -1001234))
        self.assertEqual(botmod.parse_arc("snake"), ("snake", None))
        g = self._group_msg()
        self.run_(self.h["arcade_cmd"](g))
        urls = [b.url for row in g.answer.call_args.kwargs["reply_markup"].inline_keyboard for b in row]
        self.assertTrue(all(u.endswith("_n55") for u in urls))           # the group id rides along in the link
        self.assertEqual(len(urls), 24)
        e = self._group_msg()
        self.run_(self.h["arcade_top"](e))
        self.assertIn("No arcade scores", e.reply.call_args.args[0])
        self.db.arc_group_score(-55, 1, "snake", 12); self.db.arc_group_score(-55, 1, "snake", 9)
        self.db.arc_group_score(-55, 2, "flap", 5); self.db.arc_group_score(-55, 1, "flap", 3)
        e = self._group_msg()
        self.run_(self.h["arcade_top"](e))
        txt = e.reply.call_args.args[0]
        self.assertIn("Group Arcade Ranking", txt)
        self.assertLess(txt.index("U1") if "U1" in txt else txt.index("u1"), txt.index("u2") if "u2" in txt else 10**6)
        m = msg(2)
        self.run_(self.h["start"](m, NS(args="arc_snake_n55")))
        self.assertIn("&g=-55", self.bot.send_photo.call_args.kwargs["reply_markup"].inline_keyboard[0][0].web_app.url)

    def test_ping_and_plain_link_fallback(self):
        m = msg(2)
        self.run_(self.h["ping"](m))
        self.assertIn("Pong", m.reply.call_args.args[0])
        g = self._group_msg()
        g.reply = AsyncMock(side_effect=[Exception("BUTTON_URL_INVALID"), None])   # first send (with button) is rejected
        self.run_(self.h["play"](g, NS(args=None, command="playludo")))
        self.assertEqual(g.reply.call_count, 2)                                    # fell back to a plain link
        self.assertIn("start=join_", g.reply.call_args.args[0])

    def test_bot_replaced_when_lobby_full(self):
        r = self.rooms.create(1, "tictactoe", 0)
        from app.rooms import Player
        r.players = [Player(1, "a", "a", None, coins=1), Player(-1, "bot", "bot", None, coins=1, is_bot=True)]
        class WS:
            async def send_json(self, x): pass
        self.run_(self.rooms.join(r, {"id": 2, "name": "B", "username": "b", "coins": 10}, WS()))
        self.assertEqual(sorted(p.uid for p in r.players), [1, 2])


if __name__ == "__main__":
    unittest.main()
