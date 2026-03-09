<p align="center">
  <img src="https://character.ai/icon.svg" width="96" alt="Character.AI" />
</p>

<h1 align="center">C.AI Wrapper for Discord</h1>

<p align="center">
  <strong>Bring any Character.AI persona to life inside Discord — as a real webhook with its name, avatar, and personality.</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="discord.py" src="https://img.shields.io/badge/discord.py-2.x-5865F2?style=flat-square&logo=discord&logoColor=white">
  <img alt="curl_cffi" src="https://img.shields.io/badge/transport-WebSocket-1E1E1E?style=flat-square">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-22c55e?style=flat-square">
</p>

<br>

---

## ✨ Features

| | |
|---|---|
| 🪝 **Webhook Personas** | Characters spawn as real Discord webhooks — correct name, avatar, everything. |
| 🔍 **Interactive Search** | Paginated search UI with image cards directly inside Discord. |
| 🎛️ **Follow Modes** | Auto (every message) or Reply-only (only when users reply to bot messages). |
| 🔄 **Regeneration** | Re-roll any tracked bot reply with `/regenerate`. |
| 💾 **Persistent Sessions** | Logins and active characters survive bot restarts via `session_store.json`. |
| 📡 **Streaming Replies** | Partial message edits show the character "typing" in real time. |

---

## 🤖 Commands

| Command | Description |
|---|---|
| `/login <email>` | Link your Character.AI account via magic-link email auth |
| `/logout` | Remove your saved session |
| `/search <query>` | Search characters, browse results, pick one, choose channel & follow mode |
| `/spawn <char_id>` | Spawn a character by ID into the current channel |
| `/chat <message>` | Send a message directly to the active character |
| `/regenerate [message_id]` | Regenerate the latest tracked reply, or a specific one by message ID |
| `/despawn` | Remove the active character webhook from this channel |
| `/delete` | Alias for `/despawn` |

---

## 🚀 Setup

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Create your environment file**
```bash
cp .env.example .env
```

**3. Add your Discord bot token**
```env
DISCORD_TOKEN=your_discord_bot_token_here
```

**4. Run the bot**
```bash
python bot.py
```

---

## 🔐 Discord Bot Requirements

Enable in the [Developer Portal](https://discord.com/developers/applications):
- ✅ **Message Content Intent**

Invite scopes:
- `bot` · `applications.commands`

Required permissions:
- `Send Messages` · `Manage Webhooks` · `Read Message History`

---

## 🔄 How Regeneration Works

The bot tracks a `message_id → turn_id` mapping for every webhook reply it sends.

- `/regenerate` — targets the most recent tracked reply in the channel
- `/regenerate message_id:<id>` — targets a specific tracked webhook reply by Discord message ID

---

## 📁 Project Structure

```
CharacterAI-Discord-Bot/
├── bot.py               # Discord slash commands & event loop
├── cai_client.py        # Character.AI WebSocket client
├── login.py             # Android mobile auth flow
├── recaptcha.py         # reCAPTCHA Enterprise solver
├── session_manager.py   # Persistent session & channel state
├── webhook_manager.py   # Webhook creation, sending, streaming
├── config.py            # Environment variable loader
├── requirements.txt
├── .env.example
└── session_store.json   # Auto-generated runtime state
```

---

## 🛡️ Security

> [!CAUTION]
> `session_store.json` contains user auth tokens. **Keep it private and out of version control.**

- Rotate your Discord bot token immediately if it leaks
- Keep `.env` in `.gitignore` (already included)

---

<p align="center">
  <sub>Built fully alone by Walter using <a href="https://discord.py.readthedocs.io">discord.py</a> · <a href="https://github.com/yifeikong/curl_cffi">curl_cffi</a> · <a href="https://character.ai">Character.AI</a></sub>
</p>
