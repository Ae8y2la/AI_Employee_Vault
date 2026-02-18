"""
Gmail OAuth2 Auth Helper — Manual Code Paste (Reliable)
=========================================================
Opens browser for consent, then you paste the redirect URL back.
Works with any Desktop/Installed app credentials.

Usage:
    python Agents/gmail_auth.py
"""

import sys
import json
import webbrowser
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import Request, urlopen

VAULT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = VAULT_ROOT / "Agents"
CREDS_FILE = AGENTS_DIR / "credentials.json"
TOKEN_FILE = AGENTS_DIR / "token.json"
ENV_FILE = VAULT_ROOT / ".env"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]


def _update_env_value(key: str, value: str) -> None:
    if not ENV_FILE.exists():
        ENV_FILE.write_text(f"{key}={value}\n", encoding="utf-8")
        return
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    found = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        k, _, _ = stripped.partition("=")
        if k.strip() == key:
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    print("=" * 60)
    print("  Gmail OAuth2 Setup")
    print("=" * 60)

    # Load credentials.json
    if not CREDS_FILE.exists():
        print(f"\nERROR: credentials.json not found at: {CREDS_FILE}")
        sys.exit(1)

    creds_data = json.loads(CREDS_FILE.read_text(encoding="utf-8"))
    installed = creds_data.get("installed", {})
    client_id = installed.get("client_id", "")
    client_secret = installed.get("client_secret", "")
    redirect_uri = "http://localhost"

    if not client_id or not client_secret:
        print("\nERROR: Invalid credentials.json")
        sys.exit(1)

    print(f"\n  Client ID: {client_id[:30]}...")
    print(f"  Project:   {installed.get('project_id', 'unknown')}")

    # Build auth URL
    auth_url = "https://accounts.google.com/o/oauth2/auth?" + urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    })

    print(f"\n  Opening browser...\n")
    webbrowser.open(auth_url)

    print("=" * 60)
    print("  STEPS:")
    print("  1. Sign in with your Google account")
    print("  2. Click 'Advanced' then 'Go to ... (unsafe)'")
    print("  3. Allow all permissions")
    print("  4. You will be redirected to a page that WONT LOAD")
    print("  5. COPY the full URL from the address bar")
    print("     It looks like: http://localhost/?code=4/0A...")
    print("  6. PASTE it below and press Enter")
    print("=" * 60)

    user_input = input("\nPaste the URL here: ").strip()

    # Extract code
    auth_code = ""
    if "code=" in user_input:
        parsed = urlparse(user_input)
        params = parse_qs(parsed.query)
        if "code" in params:
            auth_code = params["code"][0]
    else:
        auth_code = user_input

    if not auth_code:
        print("ERROR: No authorization code found")
        sys.exit(1)

    print(f"\n  Code received: {auth_code[:25]}...")
    print("  Exchanging for tokens...")

    # Exchange code for tokens
    token_data = urlencode({
        "code": auth_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }).encode()

    req = Request(
        "https://oauth2.googleapis.com/token",
        data=token_data,
        method="POST",
    )
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urlopen(req) as resp:
            tokens = json.loads(resp.read())
    except Exception as e:
        error_body = ""
        if hasattr(e, "read"):
            try:
                error_body = e.read().decode()
            except Exception:
                pass
        print(f"\n  ERROR: Token exchange failed: {e}")
        if error_body:
            print(f"  Details: {error_body}")
        sys.exit(1)

    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")

    if not refresh_token:
        print("\n  ERROR: No refresh token received!")
        print("  Go to https://myaccount.google.com/permissions")
        print("  Remove this app, then try again.")
        sys.exit(1)

    print(f"  Access token:  {access_token[:20]}...")
    print(f"  Refresh token: {refresh_token[:20]}...")

    # Save token.json
    TOKEN_FILE.write_text(json.dumps({
        "token": access_token,
        "refresh_token": refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": SCOPES,
    }, indent=2), encoding="utf-8")
    print(f"  Saved: token.json")

    # Get email
    email = ""
    try:
        profile_req = Request("https://www.googleapis.com/gmail/v1/users/me/profile")
        profile_req.add_header("Authorization", f"Bearer {access_token}")
        with urlopen(profile_req) as resp:
            profile = json.loads(resp.read())
            email = profile.get("emailAddress", "")
            print(f"  Gmail: {email}")
    except Exception:
        pass

    # Update .env
    _update_env_value("GMAIL_CLIENT_ID", client_id)
    _update_env_value("GMAIL_CLIENT_SECRET", client_secret)
    _update_env_value("GMAIL_REFRESH_TOKEN", refresh_token)
    if email:
        _update_env_value("GMAIL_USER_EMAIL", email)
        _update_env_value("SMTP_USERNAME", email)
        _update_env_value("SMTP_FROM_ADDRESS", email)

    print("\n" + "=" * 60)
    print("  SUCCESS! Gmail OAuth2 is configured.")
    print("=" * 60)
    if email:
        print(f"  Email: {email}")
    print(f"  Test:  python Agents/gmail_watcher.py --once")
    print("=" * 60)


if __name__ == "__main__":
    main()
