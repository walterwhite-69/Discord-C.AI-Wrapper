import asyncio
import json
import os
import random
import re
import sys
import time
from urllib.parse import urlparse, parse_qs, quote_plus

from curl_cffi.requests import AsyncSession


DEBUG = os.environ.get("DEBUG", "1") == "1"

def dbg(msg: str):
    if DEBUG:
        print(f"  [DBG] {msg}", flush=True)

def log_request(method: str, url: str, headers: dict = None, body: str = None):
    if not DEBUG: return
    print(f"\n[>>] {method} {url}")
    if headers:
        for k, v in headers.items():
            val = str(v)[:20] + "..." if k.lower() in ("authorization", "cookie") and len(str(v)) > 20 else str(v)
            print(f"     {k}: {val}")
    if body:
        print(f"     Body: {body[:200]}{'...' if len(body) > 200 else ''}")

def log_response(resp, label: str = ""):
    if not DEBUG: return
    tag = f"({label}) " if label else ""
    print(f"[<<] {tag}HTTP {resp.status_code}")
    if resp.status_code >= 400:
        print(f"  [!] Error {resp.status_code}: {resp.text[:300]}")
    else:
        try:
            preview = json.dumps(resp.json())[:300]
        except Exception:
            preview = resp.text[:300]
        print(f"     Body: {preview}{'...' if len(resp.text) > 300 else ''}")

async def cf_delay(min_s: float = 0.5, max_s: float = 1.5):
    t = random.uniform(min_s, max_s)
    dbg(f"CF delay: sleeping {t:.2f}s")
    await asyncio.sleep(t)




CAI_BASE = "https://character.ai"
CAI_PLUS = "https://plus.character.ai"
FIREBASE_API_KEY_MOBILE = "AIzaSyBYjIdjN5T49bIWDGX00qyr_WMlRRVeMMU"
FIREBASE_SIGNIN_MOBILE = f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/emailLinkSignin?key={FIREBASE_API_KEY_MOBILE}"

POLLING_INTERVAL = 3
POLLING_TIMEOUT = 300

def _mobile_headers(extra: dict = None) -> dict:

    h = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip",
        "Accept-Language": "en",
        "Connection": "Keep-Alive",
        "Host": "character.ai",
        "origin-id": "android-v1.15.3-260306.110301",
        "user-agent": "Character.AI/1.15.3 (React Native; Android)",
    }
    if extra:
        h.update(extra)
    return h




async def send_login_email(session: AsyncSession, email: str, recaptcha_token: str) -> str:
    url = f"{CAI_BASE}/login/send?email={quote_plus(email)}&app=true&host=https:%2F%2Fcharacter.ai&mobileUniversalLoginLink=true"
    headers = _mobile_headers({
        "x-cai-recaptcha-token": recaptcha_token
    })

    log_request("GET", url, headers)
    await cf_delay(0.3, 0.8)

    resp = await session.get(
        url,
        headers=headers,
        impersonate="chrome124",
        timeout=30,
    )
    log_response(resp, "login/send")
    resp.raise_for_status()

    data = resp.json()
    if data.get("ok"):
        return data.get("result")
    raise RuntimeError(f"Failed to send email: {data}")




async def poll_for_magic_link(session: AsyncSession, uuid: str) -> str:
    url = f"{CAI_BASE}/login/polling?uuid={uuid}"
    headers = _mobile_headers()

    deadline = time.time() + POLLING_TIMEOUT
    poll_count = 0

    while time.time() < deadline:
        poll_count += 1
        log_request("GET", url)
        resp = await session.get(url, headers=headers, impersonate="chrome124", timeout=15)
        log_response(resp, f"polling #{poll_count}")
        resp.raise_for_status()
        data = resp.json()

        if data.get("result") == "done" and data.get("type") == "callback":
            action_url = data.get("value", "")
            if action_url:
                print(f"[login] Magic link clicked after {poll_count} polls.")
                return action_url
            raise RuntimeError(f"Polling done but no value URL: {data}")

        if data.get("result") == "waiting":
            print(f"[login] Waiting for magic link... (poll #{poll_count})", end="\r")
            await asyncio.sleep(POLLING_INTERVAL)
            continue

        raise RuntimeError(f"Unexpected polling response: {data}")

    raise TimeoutError("Timed out waiting for magic link click.")




async def process_magic_link(session: AsyncSession, action_url: str, email: str) -> str:
    print(f"[login] Processing magic link (Android Mobile Flow)...")


    oob_match = re.search(r'oobCode=([^&]+)', action_url)
    if not oob_match:
        raise RuntimeError("No oobCode found in action URL")
    oob_code = oob_match.group(1)


    print(f"[login] Trading Firebase oobCode for Mobile idToken...")
    fb_payload = {
        "email": email,
        "oobCode": oob_code,
        "clientType": "CLIENT_TYPE_ANDROID"
    }
    fb_headers = {
        "Accept-Encoding": "gzip",
        "Accept-Language": "en-US",
        "Connection": "Keep-Alive",
        "Content-Type": "application/json",
        "Host": "www.googleapis.com",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; ASUS_Z01QD Build/QKQ1.190825.002)",
        "X-Android-Cert": "03051DBCD40F4D44FFF9608B37348EA3B1BEFF0A",
        "X-Android-Package": "ai.character.app",
        "X-Client-Version": "Android/Fallback/X24000001/FirebaseCore-Android",
        "X-Firebase-Client": "H4sIAAAAAAAAAEWQzW7CMBCEXyXyGSeOU9rCrVLfAFUcGoQ28QYsHBvZS6QK8e6186NcZ0bf7M6TXRE8NQgU2P73yeCCltie3RwZbetC5iKXZdZpj5w82HB3nuqi_MyjkykcdIu8dwpNXXwdfg5nI0R5LjOwyjuteK8tD-oWQW9LuokYVRcQHmHits5jDKQqkXmElrgF0gPyZDcQklvlVb5itQ0ExqCvi4kBFswf6TaM0QQa5a7to7BdhRlQF5WchQdd03UxsuLvBqhzvl_oc108ytnYUO5G4JIm8Bek6c1qu7xpoY93H4_jIt9swxQQppGZFPKdi4qLD3Z6nTZsQB8iOK4u2esf0ye5y5IBAAA",
        "X-Firebase-GMPID": "1:458797720674:android:78bc41f75bd4767feb9d3b"
    }

    log_request("POST", FIREBASE_SIGNIN_MOBILE, fb_headers, json.dumps(fb_payload))
    await cf_delay(0.2, 0.5)
    fb_resp = await session.post(FIREBASE_SIGNIN_MOBILE, headers=fb_headers, json=fb_payload, impersonate="chrome124")
    log_response(fb_resp, "Firebase Mobile Sign In")
    fb_resp.raise_for_status()

    id_token = fb_resp.json().get("idToken")
    if not id_token:
        raise RuntimeError("Failed to get idToken from Firebase!")

    print(f"[login] Got Mobile Firebase idToken (len={len(id_token)}). Exchanging directly for Neo Token...")


    dj_url = f"{CAI_PLUS}/dj-rest-auth/google_idp/"
    dj_headers = _mobile_headers({
        "Host": "plus.character.ai",
        "Content-Type": "application/json"
    })
    dj_payload = {
        "id_token": id_token
    }

    log_request("POST", dj_url, dj_headers, json.dumps(dj_payload))
    await cf_delay(0.5, 1.0)
    dj_resp = await session.post(dj_url, headers=dj_headers, json=dj_payload, impersonate="chrome124")
    log_response(dj_resp, "DJ Rest Auth")
    dj_resp.raise_for_status()

    neo_token = dj_resp.json().get("key")
    if not neo_token:
        raise RuntimeError("Failed to get Neo token (key) from dj-rest-auth!")

    return neo_token




async def login(email: str, recaptcha_token: str, on_email_sent_hook=None) -> dict:









    async with AsyncSession(impersonate="chrome124") as session:
        print(f"[login] Starting Android Mobile Auth Flow for {email} ...")
        uuid = await send_login_email(session, email, recaptcha_token)
        print(f"[login] UUID: {uuid}")
        print(f"[login] Login Page (if needed): https://character.ai/login/{uuid}")
        print(f"[login] >>> Please check your email and click the magic link! <<<")

        if on_email_sent_hook:
            await on_email_sent_hook(uuid, email)

        action_url = await poll_for_magic_link(session, uuid)

        neo_token = await process_magic_link(session, action_url, email)

        print(f"\n[login] SUCCESS (Mobile Flow)!")
        print(f"  Neo API Token: {neo_token}")

        return {
            "web_next_auth": "",
            "token": neo_token,
            "email": email,
        }


async def _cli_test():
    print("=== Character.AI Android Mobile Login Test ===")

    if len(sys.argv) > 1:
        email = sys.argv[1]
        print(f"Using email from args: {email}")
    else:
        email = input("Enter email: ").strip()

    try:
        from recaptcha import solve_recaptcha
        print("Solving reCAPTCHA...")
        rc_token = await solve_recaptcha()
        print(f"reCAPTCHA token obtained (len={len(rc_token)})")
    except ImportError:
        print("recaptcha.py not found. Enter reCAPTCHA token manually:")
        rc_token = input("Token: ").strip()

    result = await login(email, rc_token)
    token = result["token"]
    print(f"\n{'='*50}")
    print(f"Authorization: Token {token}")
    print(f"{'='*50}")
    return token

if __name__ == "__main__":
    asyncio.run(_cli_test())
