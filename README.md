# GAMELY - Telegram Game Hub Bot (28 games)

Owner: AAKASH (@Advik_prakashh) · Sister bot: @Groupingabot (group and channel management)

| Game | Players | Command | Category |
|---|---|---|---|
| 🎲 Ludo | 2-4 | `/playludo [bet]` | Classic |
| 🐍 Snakes & Ladders | 2-4 | `/playsnake [bet]` | Classic |
| 🎯 Carrom | 2-2 | `/playcarrom [bet]` | Classic |
| 🔴 Connect Four | 2-2 | `/playc4 [bet]` | Classic |
| ❌ Tic-Tac-Toe | 2-2 | `/playttt [bet]` | Classic |
| ✊ Rock Paper Scissors | 2-2 | `/playrps [bet]` | Classic |
| 🧠 Memory Match | 2-2 | `/playmemory [bet]` | Classic |
| ♟️ Chess | 2-2 | `/playchess [bet]` | Board |
| 🔵 Checkers | 2-2 | `/playcheckers [bet]` | Board |
| ⚫ Reversi | 2-2 | `/playreversi [bet]` | Board |
| ⭕ Gomoku | 2-2 | `/playgomoku [bet]` | Board |
| ❎ Ultimate Tic-Tac-Toe | 2-2 | `/playuttt [bet]` | Board |
| 🚢 Battleship | 2-2 | `/playbattleship [bet]` | Board |
| 🟥 UNO | 2-6 | `/playuno [bet]` | Cards |
| 🎱 Crazy Eights | 2-5 | `/playcrazy8 [bet]` | Cards |
| 🐟 Go Fish | 2-4 | `/playgofish [bet]` | Cards |
| 🂡 Blackjack | 2-5 | `/playblackjack [bet]` | Casino |
| 🃏 Teen Patti | 2-6 | `/playteenpatti [bet]` | Casino |
| 🐷 Pig | 2-4 | `/playpig [bet]` | Casino |
| 🎲 Liar's Dice | 2-5 | `/playliar [bet]` | Casino |
| 🎱 Bingo | 2-6 | `/playbingo [bet]` | Party |
| 🪵 Nim | 2-2 | `/playnim [bet]` | Brain |
| 🥜 Mancala | 2-2 | `/playmancala [bet]` | Brain |
| 🔲 Dots & Boxes | 2-2 | `/playdots [bet]` | Brain |
| 🕵️ Mafia | 4-10 | `/playmafia [bet]` | Party |
| 🔤 Hangman | 2-6 | `/playhangman [bet]` | Party |
| 🎯 Mastermind | 2-2 | `/playmastermind [bet]` | Brain |
| ❓ Trivia Quiz | 2-6 | `/playtrivia [bet]` | Brain |

Bot features: banner welcome with sister-bot and owner credit, DM menu (games by category, profile, daily streak bonus, leaderboard,
invite and earn up to 700 coins per friend, help), owner panel `/panel` (stats, broadcast to users/groups/all, ban/unban, coins,
verification switch), join-request verification (captcha in DM, approve on pass, decline after 3 fails; groups use `/verify on|off`),
welcome message when added to a group. Put your Telegram id in `ADMIN_IDS` to unlock the owner panel.

All games share: lobby with room code and share button, host start, computer players (free games), entry bets,
turn timers, AFK handling, rematch, chat and sound. `/games` lists them in the bot.
- **Coins**: starting balance, daily bonus, entry bets with a house fee, leaderboard, admin commands
- **Security**: all game logic runs on the server, and Telegram `initData` is verified, so players can't cheat or impersonate anyone

```
Telegram chat --/playludo--> bot --"Join" button--> mini app (webapp/)
                                                        |  WebSocket (wss)
                                                        v
                      Caddy (HTTPS) --> FastAPI server (app/) --> SQLite (data/ludo.db)
```

## What you need

| Item | Notes |
|---|---|
| A VPS | Ubuntu 22.04/24.04, 1 GB RAM is enough. Open ports 22, 80, 443 |
| A domain | Telegram mini apps require HTTPS. A free subdomain (DuckDNS, etc.) works |
| A bot token | From @BotFather |

## Setup

### 1. Domain
Create a DNS **A record** `game.yourdomain.com` pointing to the VPS IP address. Wait a few minutes.

### 2. Bot (in @BotFather)
1. `/newbot`, then copy the token.
2. Optional but recommended, for links like `t.me/YourBot/play?startapp=CODE`: `/newapp`, choose your bot, set the **Web App URL** to `https://game.yourdomain.com`, and set the short name to `play`.
3. `/setcommands` is not needed, because the bot registers its own commands.
4. For groups: `/setjoingroups` -> Enable.

### 3. Put the code on the VPS
From your phone (Termux) or anywhere:
```bash
ssh root@YOUR_VPS_IP
git clone https://github.com/YOU/YOUR_REPO.git game && cd game      # or: scp the zip and unzip it
bash scripts/setup_vps.sh        # installs Docker, opens the firewall, creates .env
nano .env                        # fill in BOT_TOKEN, DOMAIN, WEBAPP_URL, APP_SHORT_NAME, ADMIN_IDS
bash scripts/setup_vps.sh        # run again: builds and starts everything
docker compose logs -f game      # look for "Bot @YourBot started"
```
Caddy fetches the HTTPS certificate automatically on first start.

### 4. Play
Add the bot to a group and send `/playludo` (or `/playludo 100` for a 100-coin bet). Tap **Join**, then the host taps **START GAME**. In the lobby, the host can add computer players to fill empty seats in free games.

## Commands
`/start` `/playludo [bet]` `/playttt [bet]` `/balance` `/daily` `/top` `/help`
Admin (IDs in `ADMIN_IDS`): `/addcoins <user_id> <amount>`, `/stats`

## Updating
```bash
cd game && git pull && docker compose up -d --build
```
Players in a running game are disconnected for a few seconds and reconnect automatically, but rooms live in memory, so unfinished games are lost on restart. Update when it's quiet.

## Backups
Everything is in `data/ludo.db`:
```bash
cp data/ludo.db backup-$(date +%F).db
```

## Adding another game
1. Copy `app/games/tictactoe.py`, and implement `current`, `handle`, `auto_play`, `remove_player` and `public_state`.
2. Register it in `app/games/__init__.py` (both `GAMES` and `GAME_INFO`, including its `cmd`).
3. Add a `build` and `apply` renderer in `webapp/games.js` and register it with `HUB.UI.<game_type> = {build, apply}`.

The `/playX` bot command, lobby, bets, payouts, timers, AFK, bots, chat and rematch all work automatically.

## Also included (v2.1)
- **Arcade** (solo, pays coins, server-validated, daily cap 6000): Break Bricks, TapVerse (tap to earn + upgrades), QuickDrop, GridPop, PocketFarm (idle farm)
- **Spectators**: anyone who opens a room that is full or running watches it live (👁 count, "Take a seat" in the lobby)
- **Emoji reactions** floating over the game, ❓ how-to-play for every game (also ⓘ on the home cards), invite message presets
- **Owner panel**: `/panel` in the bot and 👑 Owner in the mini app (stats, broadcast, give coins, ban). Send `/id` to the bot and put the number in `ADMIN_IDS`
- **Host transfer**: if the host is offline for 70 s in a lobby, another connected player becomes host
- Smooth 3D dice tumble, centred and smoother UNO/card layout

## MongoDB (optional)
Set `MONGO_URI` (and optionally `MONGO_DB`) in `.env`, for example a free MongoDB Atlas cluster:
`MONGO_URI=mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`
SQLite stays the fast working store; every few seconds changed users, coins, matches, chats and settings are mirrored into MongoDB, and on start-up an empty
local database is restored from MongoDB. So the data survives hosts with temporary disks (Railway, Render...). If MongoDB is unreachable the bot keeps running on SQLite.
Atlas: allow your server's IP under Network Access.

## Not finished yet
Quiet background ambience plays only in a few games (calm drone in chess, checkers, gomoku, reversi, mancala, dominoes, word duel, ultimate tic-tac-toe; wind in Tank Duel; engine hum in Car Racing; dark pad in Quest, TeleArena, Mafia). Ludo and Carrom have none. It follows the 🔊 button and stops when the app is hidden.

New arcade games (solo, pay coins, server-validated): ByteBlock, TileDash, NeonSlice, MintTap, TurboCoin.
Idle/pet games that keep growing while you are away (progress saved on the server, daily arcade cap applies): IdleSprout, PixelPaws, TinyWorld, MiniRealm.

**v3.3 - groups, links, curated lineup.** The home screen and bot menus now show a focused set of classics (Ludo, UNO, Carrom, Chess, Snakes & Ladders, Checkers, Connect Four, Tic-Tac-Toe, Dominoes, Battleship, Dots & Boxes, Hangman, Bingo, Teen Patti, Mafia, Scribble, Trivia, Tank Duel, Car Racing, Memory, Crazy Eights). Every other game still works through its `/play...` command; set `SHOW_ALL_GAMES=1` to list them all again. Groups: `/play` opens a game picker, `/rooms` lists open lobbies, `/addgroup` and the "Add me to a Group" button open Telegram's add-to-group dialog with admin rights pre-selected; group and admin command menus are registered separately. Chess has arc-lift moves, capture bursts, castling, check shake and checkmate topple; UNO has new card faces, a fanned hand and opponent card fans; Scribble computer players now guess (wrong guesses first) and never draw.

**v3.7 new games:** 🏏 Hand Cricket (`/playcricket`, the 90s school-bench classic: pick 1-6 at the same time, same number = OUT; fist-shake reveal, stump-flying wickets, 4/6 call-outs, crowd, confetti) and 🃏 Bluff / Cheat (`/playbluff`, 3-6 players: claim cards face-down, call BLUFF, flip reveal and verdict).

**Join links / Play button:** `t.me/<bot>/play?startapp=CODE` only works if a Mini App named `play` exists in BotFather: `/newapp` > pick the bot > Web App URL = your `WEBAPP_URL` > short name `play`. The bot probes this at start-up (`APP_LINKS=auto`); when the app is missing it logs a warning and uses in-chat Join buttons (private chats) and `t.me/<bot>?start=join_CODE` links (groups), which always work. Also in BotFather: `/setjoingroups` > Enable so the bot can be added to groups.

New in the previous version (50 games): Scribble (`/playscribble`, draw & guess with a live shared canvas, 2-8 players). The WebSocket flood guard was raised (40 → 120 messages / 5 s) so fast tapping in ClickRush no longer disconnects players. Before that (49 games): Would You Rather (`/playwyr`), Guess the Number (`/playguess`), EmojiQuiz (`/playemoji`), Penalty Shootout (`/playpenalty`). The mini app now reconnects as soon as you come back to it after the phone slept. Before that: Poker Showdown (`/playpoker`), Yahtzee (`/playyahtzee`), Simon Duel (`/playsimon`), MathBlitz (`/playmath`). Invite links now survive server restarts (rooms are remembered for 24 h) and bots in timed games (ChatClash, PingPlay, MathBlitz) act on time. Earlier: Tank Duel (`/playtank`), Car Racing (`/playrace`), Dominoes (`/playdominoes`), Word Duel (`/playword`), Adventure Quest (`/playquest`), ClickRush (`/playclick`), PartyDrop (`/playdrop`), ChatClash (`/playchat`), PingPlay (`/playping`), CoinPulse (`/playcoin`), SquadDuel (`/playsquad`), TeleArena (`/playtele`).

## Tests
```bash
python3 -m unittest discover -s tests     # engines (all 7 games), wallet/payouts, auth, room flow
node tests/board.test.js                  # board geometry matches the engine
python3 tests/e2e_party.py                # Mafia, Hangman, Mastermind, Trivia smoke test
python3 tests/e2e_v21.py                  # arcade, owner panel, spectators, reactions
python3 tests/e2e_shots.py [game ...]     # needs `playwright`: plays every game in a real headless browser, saves screenshots
```
`e2e_shots.py` runs the real room manager and engines against the real mini app without Telegram or FastAPI, which makes it a good
smoke test after any change to the frontend.
For a quick look in a browser without Telegram, set `DEV_MODE=1` and open `https://your-domain/?dev=anyname&room=CODE`. **Turn it off again for production**, because with it on anyone can log in as any user.

## Limits and notes
- **Run one server process.** Rooms are in memory (this is fine for hundreds of players on a small VPS). Scaling out needs Redis.
- **Coins are virtual.** Don't add cash deposits or withdrawals unless you've checked the law where you and your players live. Real-money games are restricted or banned in many places, including parts of India, and Telegram's rules also restrict gambling in bots.
- The bot uses polling, so it needs no webhook setup.

## Troubleshooting
| Problem | Fix |
|---|---|
| Mini app shows "Please open this game from Telegram" | Open it from the bot's button, not a browser |
| Blank page or certificate error | DNS not pointing to the VPS yet, or ports 80/443 closed. Check `docker compose logs caddy` |
| Bot silent | Wrong `BOT_TOKEN`. Check `docker compose logs game` |
| "Session expired, reopen the app" | Close and reopen the mini app |
| Bot ignores `/play@Bot` in a group | 1) `docker compose logs -f bot` then send the command: you should see `group command '/play@...'`. Nothing logged = Telegram is not delivering (the bot isn't in that group, or **a second copy of the bot with the same token is running** and stealing updates - stop every other deployment/Termux/Railway instance). 2) Send `/ping@Bot` - it answers with chat type and the bot's role. 3) Make sure you deployed the latest zip and restarted (`docker compose up -d --build`). |
| Join button does nothing in a group | Set `APP_SHORT_NAME`, or users must have started the bot once |
