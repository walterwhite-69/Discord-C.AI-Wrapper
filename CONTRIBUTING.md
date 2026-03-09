<p align="center">
  <img src="https://character.ai/icon.svg" width="72" alt="Character.AI" />
</p>

<h1 align="center">Contributing to C.AI Wrapper for Discord</h1>

<p align="center">
  Thanks for taking the time to contribute! Here's everything you need to get started.
</p>

---

## 📋 Before You Start

- Check [open issues](https://github.com/walterwhite-69/Discord-C.AI-Wrapper/issues) to avoid duplicate work
- For large changes, open an issue first to discuss the approach
- All PRs should target the `main` branch

---

## 🛠️ Development Setup

```bash
# 1. Fork and clone the repo
git clone https://github.com/your-username/Discord-C.AI-Wrapper.git
cd CharacterAI-Discord-Bot

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy the env file and fill in your token
cp .env.example .env
```

---

## 🌿 Branch Naming

| Type | Pattern | Example |
|---|---|---|
| Feature | `feat/short-description` | `feat/typing-indicator` |
| Bug fix | `fix/short-description` | `fix/webhook-not-deleted` |
| Refactor | `refactor/short-description` | `refactor/session-manager` |
| Docs | `docs/short-description` | `docs/readme-update` |

---

## ✅ Pull Request Checklist

Before submitting a PR, make sure:

- [ ] Code runs without errors (`python bot.py`)
- [ ] No hardcoded tokens, emails, or secrets in the diff
- [ ] Comments removed from code (keep code self-explanatory)
- [ ] `session_store.json` is **not** included in the commit
- [ ] PR description explains **what** changed and **why**

---

## 🐛 Reporting Bugs

Open an issue and include:

1. What you did
2. What you expected to happen
3. What actually happened (paste the full traceback)
4. Python version and OS

---

## 💡 Suggesting Features

Open an issue with the `enhancement` label and describe:

- The problem you're trying to solve
- Your proposed solution
- Any alternatives you considered

---

## 🔐 Security Issues

**Do not open a public issue for security vulnerabilities.**  
Reach out privately so it can be patched before disclosure.

---

## 📄 License

By contributing, you agree that your work will be released under the [MIT License](LICENSE).
