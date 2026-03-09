import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ActiveCharacter:
    char_id: str
    chat_id: str
    name: str
    avatar_url: str
    webhook_id: int
    webhook_url: str
    follow_mode: str = "auto"


class SessionManager:
    def __init__(self):
        self._store_path = Path(__file__).resolve().parent / "session_store.json"
        self._user_tokens: dict[int, str] = {}
        self._active: dict[int, ActiveCharacter] = {}
        self._bot_message_turns: dict[int, dict[int, str]] = {}
        self._load_state()

    def _load_state(self) -> None:
        if not self._store_path.exists():
            return
        try:
            data = json.loads(self._store_path.read_text(encoding="utf-8"))
        except Exception:
            self._user_tokens = {}
            self._active = {}
            self._bot_message_turns = {}
            return

        raw_tokens = data.get("user_tokens", {})
        if isinstance(raw_tokens, dict):
            parsed_tokens: dict[int, str] = {}
            for user_id_raw, token in raw_tokens.items():
                try:
                    parsed_tokens[int(user_id_raw)] = str(token)
                except (TypeError, ValueError):
                    continue
            self._user_tokens = parsed_tokens

        raw_active = data.get("active_channels", {})
        if isinstance(raw_active, dict):
            parsed_active: dict[int, ActiveCharacter] = {}
            for channel_id_raw, payload in raw_active.items():
                try:
                    channel_id = int(channel_id_raw)
                except (TypeError, ValueError):
                    continue
                if not isinstance(payload, dict):
                    continue
                try:
                    parsed_active[channel_id] = ActiveCharacter(
                        char_id=str(payload.get("char_id") or ""),
                        chat_id=str(payload.get("chat_id") or ""),
                        name=str(payload.get("name") or "Character"),
                        avatar_url=str(payload.get("avatar_url") or ""),
                        webhook_id=int(payload.get("webhook_id") or 0),
                        webhook_url=str(payload.get("webhook_url") or ""),
                        follow_mode=str(payload.get("follow_mode") or "auto"),
                    )
                except Exception:
                    continue
            self._active = parsed_active

        raw_turns = data.get("bot_message_turns", {})
        if isinstance(raw_turns, dict):
            parsed_turns: dict[int, dict[int, str]] = {}
            for channel_id_raw, mapping in raw_turns.items():
                try:
                    channel_id = int(channel_id_raw)
                except (TypeError, ValueError):
                    continue
                if not isinstance(mapping, dict):
                    continue
                turns: dict[int, str] = {}
                for message_id_raw, turn_id in mapping.items():
                    try:
                        message_id = int(message_id_raw)
                    except (TypeError, ValueError):
                        continue
                    turns[message_id] = str(turn_id)
                if turns:
                    parsed_turns[channel_id] = turns
            self._bot_message_turns = parsed_turns

    def _save_state(self) -> None:
        payload = {
            "user_tokens": {str(user_id): token for user_id, token in self._user_tokens.items()},
            "active_channels": {
                str(channel_id): {
                    "char_id": c.char_id,
                    "chat_id": c.chat_id,
                    "name": c.name,
                    "avatar_url": c.avatar_url,
                    "webhook_id": c.webhook_id,
                    "webhook_url": c.webhook_url,
                    "follow_mode": c.follow_mode,
                }
                for channel_id, c in self._active.items()
            },
            "bot_message_turns": {
                str(channel_id): {str(message_id): turn_id for message_id, turn_id in turns.items()}
                for channel_id, turns in self._bot_message_turns.items()
            },
        }
        tmp = self._store_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        tmp.replace(self._store_path)

    def set_token(self, user_id: int, token: str):
        self._user_tokens[user_id] = token
        self._save_state()

    def get_token(self, user_id: int) -> Optional[str]:
        return self._user_tokens.get(user_id)

    def remove_token(self, user_id: int):
        self._user_tokens.pop(user_id, None)
        self._save_state()

    def has_session(self, user_id: int) -> bool:
        return user_id in self._user_tokens

    def spawn(self, channel_id: int, character: ActiveCharacter):
        self._active[channel_id] = character
        self._bot_message_turns[channel_id] = {}
        self._save_state()

    def get_active(self, channel_id: int) -> Optional[ActiveCharacter]:
        return self._active.get(channel_id)

    def despawn(self, channel_id: int) -> Optional[ActiveCharacter]:
        self._bot_message_turns.pop(channel_id, None)
        removed = self._active.pop(channel_id, None)
        self._save_state()
        return removed

    def is_spawned(self, channel_id: int) -> bool:
        return channel_id in self._active

    def track_bot_message_turn(self, channel_id: int, message_ids: list[int], turn_id: str) -> None:
        if not turn_id:
            return
        if channel_id not in self._bot_message_turns:
            self._bot_message_turns[channel_id] = {}
        for mid in message_ids:
            self._bot_message_turns[channel_id][mid] = turn_id
        self._save_state()

    def get_turn_for_message(self, channel_id: int, message_id: int) -> Optional[str]:
        return self._bot_message_turns.get(channel_id, {}).get(message_id)

    def is_tracked_bot_message(self, channel_id: int, message_id: int) -> bool:
        return message_id in self._bot_message_turns.get(channel_id, {})

    def get_latest_tracked_turn(self, channel_id: int) -> Optional[str]:
        entries = self._bot_message_turns.get(channel_id, {})
        if not entries:
            return None
        latest_id = max(entries.keys())
        return entries.get(latest_id)


sessions = SessionManager()
