# spam-remover

A Discord bot that automatically removes **spam joiners** — accounts that join the
server and immediately post "🎁 free giveaway / free Nitro / DM me to claim" scams —
so a club officer never has to delete the message and kick the person by hand.

When a new member's message is judged to be spam, the bot **deletes the message,
kicks the user** (they can rejoin, so a mistake is recoverable), and **posts a notice
to an officer channel** with the user, the channel it was posted in, the deleted
text, and the reason.

Each notice has three **officer buttons** (only usable by members with Kick/Ban
permission):

- **👢 Kick** — remove them from the server; they can rejoin with an invite.
- **🔨 Ban** — permanent ban; they cannot rejoin unless unbanned.
- **✅ Not spam** — dismiss a false positive; records who cleared it.

Clicking any one disables the buttons and stamps who acted, so two officers can't
double-act on the same notice.

## Quick start

```bash
git clone https://github.com/jayM-11/spam-remover.git
cd spam-remover
uv sync --extra dev          # or: pip install -e ".[dev]"
cp .env.example .env         # then edit .env with your keys
python -m spam_remover.bot
```

You need:

1. A Discord bot token (`DISCORD_TOKEN`)
2. An Anthropic API key (`ANTHROPIC_API_KEY`)
3. An officer channel ID (`OFFICER_CHANNEL_ID`)

Leave `DRY_RUN=true` (the default) until you are confident detection is solid.

## How it decides

Two stages, cheapest first:

1. **Rules (instant, free):** keyword / link / `@everyone` heuristics catch obvious
   scams — "free nitro", server-invite links plus promo wording, etc.
2. **Claude (only for borderline cases):** a message with a link or mention but no
   obvious scam wording is sent to Claude Haiku for a yes/no spam judgment. Clean and
   obviously-spammy messages never hit the API, so cost stays near zero.

Only messages from **recent joiners** (default: first 48 hours) are scanned, and
members with a **trusted role** are never scanned — so established members are untouched.

## Safety: start in DRY RUN

`DRY_RUN=true` (the default) makes the bot **detect and notify officers but take no
action**. Run it this way for a few days to confirm it isn't flagging real members,
then set `DRY_RUN=false` to let it delete and kick.

## Discord setup (one time)

1. **Create the bot:** <https://discord.com/developers/applications> → *New Application*
   → *Bot* tab → *Reset Token* and copy it into `DISCORD_TOKEN`.
2. **Enable privileged intents** (Bot tab → *Privileged Gateway Intents*):
   - ✅ **Message Content Intent** — required to read message text.
   - ✅ **Server Members Intent** — required to know when members joined.
3. **Invite the bot** with the *Kick Members*, *Ban Members*, and *Manage Messages*
   permissions (OAuth2 → URL Generator → scope `bot`, then those three). Those
   power the 👢 Kick and 🔨 Ban buttons on officer notices.
4. **Position the bot's role above** the roles spammers would have (a bot can only
   kick members below it).
5. **Get channel/role IDs:** enable *Developer Mode* (Settings → Advanced), then
   right-click a channel or role → *Copy ID*.

## Configuration

Copy `.env.example` to `.env` and fill it in:

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DISCORD_TOKEN` | ✅ | — | Bot token. |
| `ANTHROPIC_API_KEY` | ✅ | — | Key for the Claude borderline-classifier. |
| `OFFICER_CHANNEL_ID` | ✅ | — | Channel where notices are posted. |
| `NEW_MEMBER_WINDOW_HOURS` | | `48` | Only scan members who joined within this many hours. |
| `TRUSTED_ROLE_IDS` | | — | Comma-separated role IDs that are never scanned. |
| `MONITORED_CHANNEL_IDS` | | all | Comma-separated channels to watch; empty = all. |
| `SPAM_KEYWORDS` | | — | Extra comma-separated spam keywords. |
| `DRY_RUN` | | `true` | When true, detect & notify only — no delete/kick. |
| `ANTHROPIC_MODEL` | | `claude-haiku-4-5-20251001` | Model for classification. |

Requires **Python 3.11+**.

## Run locally

```bash
uv sync --extra dev          # or: pip install -e ".[dev]"
cp .env.example .env         # then edit .env
python -m spam_remover.bot
```

## Run the tests

```bash
uv sync --extra dev          # first time only (installs pytest + pytest-asyncio)
uv run pytest -v             # or, without uv:  pip install -e ".[dev]" && pytest -v
```

**What success looks like:** every test passes — you should see a green summary like
`N passed in 0.2s` and no `F`/`E` markers. The suite is fully offline (no Discord or
Anthropic calls — the LLM and Discord objects are faked), so it needs no tokens.

What each file proves:

- `tests/test_rules.py` — obvious scams ("free nitro…") are flagged `SPAM`, normal
  greetings are `CLEAN`, and bare links/mentions are `SUSPECT` (handed to the LLM).
- `tests/test_classifier.py` — `SPAM`/`CLEAN` decisions **never call the LLM** (the
  cost short-circuit), and only `SUSPECT` messages reach it.
- `tests/test_moderation.py` — normal mode deletes + kicks + notifies; **`DRY_RUN`
  notifies only** and never deletes or kicks; a missing officer channel doesn't crash.
- `tests/test_views.py` — officer Kick / Ban / Not-spam buttons enforce permissions
  and disable after a single action.

If a test fails, the output names the case and shows expected-vs-actual — most likely a
keyword needs tuning in `spam_remover/detection/rules.py`.

### Live smoke test (optional, needs a throwaway server)

1. Fill `.env` with a test bot token + a test server's officer channel ID, keep `DRY_RUN=true`.
2. `python -m spam_remover.bot` → log should read `Logged in as … — DRY RUN (no kicks)`.
3. From a second, freshly-joined, non-trusted account post `🎁 free nitro, dm me` →
   an officer-channel notice appears **and the message is NOT deleted** (dry run).
4. Post `hey all!` → no notice.
5. Set `DRY_RUN=false`, repeat step 3 → message is deleted, the account is kicked, and
   the notice fires.

## Deploy (host-agnostic)

The repo ships a `Dockerfile`; the bot needs a **persistent process** (a Discord
gateway connection), not a cron or a sleeping serverless function.

- **Railway:** New Project → Deploy from repo. Add the env vars from the table above.
  It builds the Dockerfile and keeps the process running.
- **Fly.io:** `fly launch` (detects the Dockerfile) → `fly secrets set DISCORD_TOKEN=… ANTHROPIC_API_KEY=… OFFICER_CHANNEL_ID=…` → `fly deploy`. Scale to 1 always-on machine.
- **A VPS / Raspberry Pi:** `docker build -t spam-remover . && docker run --env-file .env --restart unless-stopped spam-remover`.

Avoid Render's free web tier and anything that sleeps on idle — it drops the gateway
connection.

## Project layout

```
spam_remover/
  config.py            # env -> typed Config
  bot.py               # gateway client + thin event handlers
  moderation.py        # delete / kick / officer notice (+ DRY_RUN)
  views.py             # officer Kick / Ban / Not-spam buttons on the notice
  detection/
    rules.py           # pure rule pre-filter (SPAM / CLEAN / SUSPECT)
    llm.py             # Claude Haiku judge for borderline messages
    classifier.py      # orchestrates rules -> llm
tests/                 # pytest suite for rules, classifier, moderation, views
.env.example           # copy to .env and add your keys
Dockerfile             # always-on container for Railway / Fly / VPS
```
