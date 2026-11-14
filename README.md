# Telegram Game Hub (7 games)

A Telegram bot plus mini app for multiplayer games, modelled on LudoKingProbot.

| Game | Players | Command | Notes |
|---|---|---|---|
| 🎲 Ludo | 2-4 | `/playludo [bet]` | real rules: 6 to leave, captures, safe stars, exact finish |
| 🐍 Snakes & Ladders | 2-4 | `/playsnake [bet]` | 10 snakes, 9 ladders, exact roll to win, 6 rolls again |
| 🎯 Carrom | 2 | `/playcarrom [bet]` | server-side physics, drag back to aim and set power |
| 🔴 Connect Four | 2 | `/playc4 [bet]` | animated drops, winning line highlight |
| ❌ Tic-Tac-Toe | 2 | `/playttt [bet]` | |
| ✊ Rock Paper Scissors | 2 | `/playrps [bet]` | first to 2 wins, picks hidden until both are in |
| 🧠 Memory Match | 2 | `/playmemory [bet]` | 8 pairs, a match lets you go again |

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

## Tests
```bash
python3 -m unittest discover -s tests     # engines (all 7 games), wallet/payouts, auth, room flow
node tests/board.test.js                  # board geometry matches the engine
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
| Join button does nothing in a group | Set `APP_SHORT_NAME`, or users must have started the bot once |
