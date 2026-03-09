import asyncio
import json
import urllib.parse
import uuid as _uuid_mod
from typing import Any, Optional

from curl_cffi.requests import AsyncSession


NEO_BASE = "https://neo.character.ai"
CAI_BASE = "https://character.ai"


def _http_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Token {token}",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        "Origin": "https://character.ai",
        "Referer": "https://character.ai/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36"
        ),
    }


def _ws_headers() -> dict[str, str]:
    return {
        "Origin": "https://character.ai",
        "Referer": "https://character.ai/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36"
        ),
    }


def _parse_json(raw: str) -> dict[str, Any] | None:
    try:
        return json.loads(raw)
    except Exception:
        return None


def _extract_turn(evt: dict[str, Any]) -> dict[str, Any]:
    if isinstance(evt.get("turn"), dict):
        return evt["turn"]
    payload = evt.get("payload")
    if isinstance(payload, dict) and isinstance(payload.get("turn"), dict):
        return payload["turn"]
    return {}


def _extract_turn_id(evt: dict[str, Any]) -> str:
    turn = _extract_turn(evt)
    turn_key = turn.get("turn_key", {}) if isinstance(turn.get("turn_key"), dict) else {}
    return str(turn_key.get("turn_id") or "")


def _extract_final_ai_text(
    evt: dict[str, Any], user_id: Optional[str] = None
) -> tuple[Optional[str], bool]:
    turn = _extract_turn(evt)
    if not turn:
        return None, False

    author = turn.get("author", {}) if isinstance(turn.get("author"), dict) else {}
    author_id = str(author.get("author_id", ""))
    is_human_flag = author.get("is_human")
    if isinstance(is_human_flag, bool):
        is_human = is_human_flag
    elif user_id and author_id:
        is_human = author_id == str(user_id)
        is_human = False

    if is_human:
        return None, False

    candidates = turn.get("candidates", [])
    if not isinstance(candidates, list) or not candidates:
        return None, False

    first = candidates[0] if isinstance(candidates[0], dict) else {}
    text = first.get("raw_content")
    if not text:
        return None, False

    is_final = bool(first.get("is_final", False))
    return str(text), is_final


class CAIClient:
    def __init__(self, token: str):
        self.token = token
        self._user_id: Optional[str] = None
        self._username: Optional[str] = None

    async def close(self) -> None:
        return None

    async def validate_token(self) -> dict:
        url = f"{NEO_BASE}/user/"
        headers = _http_headers(self.token)
        async with AsyncSession(impersonate="chrome124", headers=headers) as session:
            resp = await session.get(url)
            if resp.status_code == 401:
                raise ValueError("Invalid token (401 Unauthorized)")
            if resp.status_code != 200:
                raise ValueError(f"Token validation failed (HTTP {resp.status_code})")

            data = resp.json()
            self._user_id = str(data["user"]["user"]["id"])
            self._username = str(data["user"]["user"]["username"])
            return data

    async def _ensure_user(self) -> None:
        if not self._user_id or not self._username:
            await self.validate_token()

    async def search_characters(self, query: str) -> list[dict]:
        search_payload = {
            "0": {
                "json": {
                    "searchQuery": query,
                    "tagId": None,
                    "sortedBy": "popular",
                    "filters": None,
                    "cursor": None,
                },
                "meta": {
                    "values": {
                        "tagId": ["undefined"],
                        "filters": ["undefined"],
                        "cursor": ["undefined"],
                    }
                },
            }
        }
        input_str = json.dumps(search_payload)
        url = (
            f"{CAI_BASE}/api/trpc/search.search?batch=1"
            f"&input={urllib.parse.quote(input_str)}"
        )

        headers = {
            "Authorization": f"Token {self.token}",
            "Origin": "https://character.ai",
        }
        async with AsyncSession(impersonate="chrome124", headers=headers) as session:
            resp = await session.get(url)
            if resp.status_code != 200:
                print(f"[!] Search error: HTTP {resp.status_code} - {resp.text[:200]}")
                return []
            data = resp.json()
            try:
                return data[0]["result"]["data"]["json"]["characters"]
            except (KeyError, IndexError, TypeError):
                print(f"[!] Search parse error: {str(data)[:300]}")
                return []

    async def get_character_info(self, char_id: str) -> dict:
        url = f"{NEO_BASE}/character/{char_id}/"
        headers = _http_headers(self.token)
        async with AsyncSession(impersonate="chrome124", headers=headers) as session:
            resp = await session.get(url)
            if resp.status_code != 200:
                raise ValueError(f"Character not found (HTTP {resp.status_code})")
            data = resp.json()
            return data.get("character", data)

    def get_avatar_url(self, avatar_file_name: str) -> str:
        if not avatar_file_name:
            return ""
        if avatar_file_name.startswith("http://") or avatar_file_name.startswith("https://"):
            return avatar_file_name
        cleaned = avatar_file_name.lstrip("/")

        return f"https://characterai.io/i/200/static/avatars/{cleaned}?webp=true&anim=0"

    async def _connect_ws(self, session: AsyncSession):
        last_err: Exception | None = None

        try:
            return await session.ws_connect(
                url="wss://neo.character.ai/ws/",
                headers=_ws_headers(),
                cookies={"HTTP_AUTHORIZATION": f"Token {self.token}"},
            )
        except Exception as e:
            last_err = e

        try:
            headers = _ws_headers()
            headers["Authorization"] = f"Token {self.token}"
            return await session.ws_connect(
                url="wss://neo.character.ai/ws/",
                headers=headers,
            )
        except Exception as e:
            last_err = e

        raise RuntimeError(f"WS connect failed: {last_err}")

    async def start_chat(self, char_id: str) -> dict:
        await self._ensure_user()

        chat_id = str(_uuid_mod.uuid4())
        greeting: Optional[str] = None
        greeting_turn_id: Optional[str] = None
        ws_error: Optional[str] = None
        ws_char_name: Optional[str] = None

        for attempt in range(2):
            async with AsyncSession(impersonate="chrome124") as session:
                ws = None
                try:
                    ws = await self._connect_ws(session)
                    req_id = f"{_uuid_mod.uuid4().hex[:20]}{char_id[-12:]}"

                    await ws.send_json(
                        {
                            "command": "create_chat",
                            "request_id": req_id,
                            "payload": {
                                "chat_type": "TYPE_ONE_ON_ONE",
                                "chat": {
                                    "chat_id": chat_id,
                                    "creator_id": self._user_id,
                                    "visibility": "VISIBILITY_PRIVATE",
                                    "character_id": char_id,
                                    "type": "TYPE_ONE_ON_ONE",
                                },
                                "with_greeting": True,
                            },
                            "origin_id": "web-next",
                        }
                    )

                    deadline = asyncio.get_running_loop().time() + 24.0
                    while asyncio.get_running_loop().time() < deadline:
                        raw = await asyncio.wait_for(ws.recv_str(), timeout=8.0)
                        evt = _parse_json(raw)
                        if not evt:
                            continue

                        cmd = evt.get("command")
                        if cmd == "neo_error":
                            ws_error = evt.get("comment", "Unknown neo_error")
                            raise RuntimeError(f"create_chat neo_error: {ws_error}")

                        if cmd == "create_chat_response":
                            c = evt.get("chat", {})
                            if isinstance(c, dict) and c.get("chat_id"):
                                chat_id = str(c["chat_id"])

                        turn = _extract_turn(evt)
                        author = turn.get("author", {}) if isinstance(turn.get("author"), dict) else {}
                        if author.get("name"):
                            ws_char_name = str(author["name"])

                        maybe_text, is_final = _extract_final_ai_text(evt, self._user_id)
                        if maybe_text and is_final:
                            greeting = maybe_text
                            tid = _extract_turn_id(evt)
                            greeting_turn_id = tid or None
                            break

                    break
                except Exception as e:
                    ws_error = str(e)
                    if attempt == 1:
                        print(f"[!] WS start_chat error: {ws_error}")
                finally:
                    if ws is not None:
                        try:
                            await ws.close()
                        except Exception:
                            pass

            if greeting or attempt == 1:
                break

        char_name = ws_char_name or char_id
        avatar_url = ""
        try:
            char = await self.get_character_info(char_id)
            char_name = char.get("name", char_id)
            avatar_url = self.get_avatar_url(char.get("avatar_file_name", ""))
        except Exception:
            pass

        if not avatar_url and ws_char_name:
            try:
                candidates = await self.search_characters(ws_char_name)
                match = None
                for c in candidates:
                    if str(c.get("external_id") or "") == char_id:
                        match = c
                        break
                if match is None:
                    for c in candidates:
                        if str(c.get("name") or "").strip().lower() == ws_char_name.strip().lower():
                            match = c
                            break
                if match and match.get("avatar_file_name"):
                    avatar_url = self.get_avatar_url(str(match.get("avatar_file_name")))
            except Exception:
                pass

        if ws_error and not greeting:
            print(f"[!] start_chat completed without greeting. Last WS issue: {ws_error}")

        return {
            "chat_id": chat_id,
            "greeting": greeting,
            "greeting_turn_id": greeting_turn_id,
            "char_name": char_name,
            "avatar_url": avatar_url,
        }

    async def send_message_with_meta(self, char_id: str, chat_id: str, text: str) -> dict:
        await self._ensure_user()

        if not text.strip():
            return {"text": "(Error: Empty message)", "turn_id": None, "updates": []}

        last_error = "No response from character"

        for attempt in range(3):
            async with AsyncSession(impersonate="chrome124") as session:
                ws = None
                try:
                    ws = await self._connect_ws(session)

                    req_id = str(_uuid_mod.uuid4())
                    turn_id = str(_uuid_mod.uuid4())
                    cand_id = str(_uuid_mod.uuid4())

                    await ws.send_json(
                        {
                            "command": "create_and_generate_turn",
                            "request_id": req_id,
                            "payload": {
                                "chat_type": "TYPE_ONE_ON_ONE",
                                "num_candidates": 1,
                                "tts_enabled": False,
                                "selected_language": "",
                                "character_id": char_id,
                                "user_name": self._username,
                                "turn": {
                                    "turn_key": {
                                        "turn_id": turn_id,
                                        "chat_id": chat_id,
                                    },
                                    "author": {
                                        "author_id": str(self._user_id),
                                        "is_human": True,
                                        "name": self._username,
                                    },
                                    "candidates": [
                                        {
                                            "candidate_id": cand_id,
                                            "raw_content": text,
                                        }
                                    ],
                                    "primary_candidate_id": cand_id,
                                },
                                "previous_annotations": {
                                    "boring": 0,
                                    "not_boring": 0,
                                    "inaccurate": 0,
                                    "not_inaccurate": 0,
                                    "repetitive": 0,
                                    "not_repetitive": 0,
                                    "out_of_character": 0,
                                    "not_out_of_character": 0,
                                    "bad_memory": 0,
                                    "not_bad_memory": 0,
                                    "long": 0,
                                    "not_long": 0,
                                    "short": 0,
                                    "not_short": 0,
                                    "ends_chat_early": 0,
                                    "not_ends_chat_early": 0,
                                    "funny": 0,
                                    "not_funny": 0,
                                    "interesting": 0,
                                    "not_interesting": 0,
                                    "helpful": 0,
                                    "not_helpful": 0,
                                },
                                "generate_comparison": False,
                            },
                            "origin_id": "web-next",
                        }
                    )

                    partial_text: Optional[str] = None
                    partial_turn_id: Optional[str] = None
                    updates: list[str] = []
                    deadline = asyncio.get_running_loop().time() + 45.0
                    while asyncio.get_running_loop().time() < deadline:
                        raw = await asyncio.wait_for(ws.recv_str(), timeout=10.0)
                        evt = _parse_json(raw)
                        if not evt:
                            continue

                        cmd = evt.get("command")
                        if cmd == "neo_error":
                            comment = evt.get("comment", "Unknown")
                            return {"text": f"(Error: {comment})", "turn_id": None, "updates": []}

                        maybe_text, is_final = _extract_final_ai_text(evt, self._user_id)
                        if maybe_text:
                            partial_text = maybe_text
                            tid = _extract_turn_id(evt)
                            if tid:
                                partial_turn_id = tid
                            if (not is_final) and maybe_text and (not updates or updates[-1] != maybe_text):
                                if len(updates) < 3:
                                    updates.append(maybe_text)
                            if is_final:
                                return {"text": maybe_text, "turn_id": partial_turn_id, "updates": updates}

                    if partial_text:
                        return {"text": partial_text, "turn_id": partial_turn_id, "updates": updates}

                    last_error = "Character timed out with no output"
                except asyncio.TimeoutError:
                    last_error = "Socket timeout while waiting for response"
                except Exception as e:
                    last_error = str(e)
                finally:
                    if ws is not None:
                        try:
                            await ws.close()
                        except Exception:
                            pass

        return {"text": f"(Error talking to character: {last_error})", "turn_id": None, "updates": []}

    async def send_message(self, char_id: str, chat_id: str, text: str) -> str:
        result = await self.send_message_with_meta(char_id, chat_id, text)
        return str(result.get("text") or "")

    async def regenerate_turn_candidate(self, char_id: str, chat_id: str, turn_id: str) -> dict:
        await self._ensure_user()
        if not turn_id:
            return {"text": "(Error: Missing turn ID for regeneration)", "turn_id": None}

        last_error = "No regenerated response"
        for attempt in range(2):
            async with AsyncSession(impersonate="chrome124") as session:
                ws = None
                try:
                    ws = await self._connect_ws(session)
                    req_id = str(_uuid_mod.uuid4())
                    await ws.send_json(
                        {
                            "command": "generate_turn_candidate",
                            "request_id": req_id,
                            "payload": {
                                "chat_type": "TYPE_ONE_ON_ONE",
                                "tts_enabled": False,
                                "selected_language": "",
                                "character_id": char_id,
                                "user_name": self._username,
                                "turn_key": {
                                    "turn_id": turn_id,
                                    "chat_id": chat_id,
                                },
                                "previous_annotations": {
                                    "boring": 0,
                                    "not_boring": 0,
                                    "inaccurate": 0,
                                    "not_inaccurate": 0,
                                    "repetitive": 0,
                                    "not_repetitive": 0,
                                    "out_of_character": 0,
                                    "not_out_of_character": 0,
                                    "bad_memory": 0,
                                    "not_bad_memory": 0,
                                    "long": 0,
                                    "not_long": 0,
                                    "short": 0,
                                    "not_short": 0,
                                    "ends_chat_early": 0,
                                    "not_ends_chat_early": 0,
                                    "funny": 0,
                                    "not_funny": 0,
                                    "interesting": 0,
                                    "not_interesting": 0,
                                    "helpful": 0,
                                    "not_helpful": 0,
                                },
                            },
                            "origin_id": "web-next",
                        }
                    )

                    partial_text: Optional[str] = None
                    partial_turn_id: Optional[str] = None
                    deadline = asyncio.get_running_loop().time() + 45.0
                    while asyncio.get_running_loop().time() < deadline:
                        raw = await asyncio.wait_for(ws.recv_str(), timeout=10.0)
                        evt = _parse_json(raw)
                        if not evt:
                            continue

                        if evt.get("command") == "neo_error":
                            comment = evt.get("comment", "Unknown")
                            return {"text": f"(Error: {comment})", "turn_id": None}

                        maybe_text, is_final = _extract_final_ai_text(evt, self._user_id)
                        if maybe_text:
                            partial_text = maybe_text
                            tid = _extract_turn_id(evt)
                            if tid:
                                partial_turn_id = tid
                            if is_final:
                                return {"text": maybe_text, "turn_id": partial_turn_id}

                    if partial_text:
                        return {"text": partial_text, "turn_id": partial_turn_id}

                    last_error = "Regeneration timed out with no output"
                except asyncio.TimeoutError:
                    last_error = "Socket timeout while waiting for regeneration"
                except Exception as e:
                    last_error = str(e)
                finally:
                    if ws is not None:
                        try:
                            await ws.close()
                        except Exception:
                            pass

        return {"text": f"(Error regenerating: {last_error})", "turn_id": None}
