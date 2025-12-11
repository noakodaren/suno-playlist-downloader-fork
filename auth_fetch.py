import argparse
import json
import subprocess
import sys
import time
from typing import Optional

from playwright.sync_api import sync_playwright, Route, Request


def bw_cmd(args, input_text: Optional[str] = None):
    cmd = ["bw"] + args
    # run bw and return stdout
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE if input_text else None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate(input_text)
    if p.returncode != 0:
        raise RuntimeError(f"bw command failed: {err}")
    return out.strip()


def ensure_bw_unlocked():
    # Ensure bw is unlocked and we have a session key
    try:
        session = bw_cmd(["session", "--quiet"]).strip()
        if session:
            return session
    except Exception:
        pass
    # If session not available, try to run `bw unlock` (this will prompt user)
    print("Bitwarden appears locked. Please unlock with: bw unlock")
    raise SystemExit("Unlock Bitwarden and run again.")


def upsert_bw_item(item_name: str, token: str, device_id: str, session_key: str):
    # Try to find an existing item by name
    try:
        out = subprocess.check_output(["bw", "list", "items", "--session", session_key], text=True)
        items = json.loads(out)
    except subprocess.CalledProcessError as e:
        raise RuntimeError("Failed to list Bitwarden items. Ensure bw is logged in and unlocked.")

    existing = None
    for it in items:
        if it.get('name') == item_name:
            existing = it
            break

    fields = [
        {"name": "token", "value": token, "type": 0},
        {"name": "device_id", "value": device_id, "type": 0},
    ]

    if existing:
        # update
        item_id = existing['id']
        existing['fields'] = fields
        payload = json.dumps(existing)
        p = subprocess.Popen(["bw", "edit", "item", item_id, "--session", session_key], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = p.communicate(payload)
        if p.returncode != 0:
            raise RuntimeError(f"Failed to edit Bitwarden item: {err}")
        print(f"Updated Bitwarden item '{item_name}'")
    else:
        # create a new login-type item
        item = {
            "type": 1,
            "name": item_name,
            "fields": fields
        }
        payload = json.dumps(item)
        p = subprocess.Popen(["bw", "create", "item", "--session", session_key], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = p.communicate(payload)
        if p.returncode != 0:
            raise RuntimeError(f"Failed to create Bitwarden item: {err}")
        print(f"Created Bitwarden item '{item_name}'")


def run_playwright(item_name: str, headless: bool):
    session_key = ensure_bw_unlocked()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()

        captured = {
            'bearer': None,
            'device_id': None,
        }

        def handle_route(route: Route, request: Request):
            try:
                # inspect outgoing request headers
                hdrs = request.headers
                auth = hdrs.get('authorization') or hdrs.get('Authorization')
                device = hdrs.get('device-id') or hdrs.get('device-id')
                if auth and 'Bearer ' in auth and not captured['bearer']:
                    captured['bearer'] = auth.split('Bearer ')[1]
                    print('Captured bearer token')
                if device and not captured['device_id']:
                    captured['device_id'] = device
                    print('Captured device-id')
            except Exception:
                pass
            return route.continue_()

        # route all requests to inspect headers
        context.route("**/*", handle_route)

        page = context.new_page()
        page.goto("https://suno.com/login", wait_until='networkidle')

        # Click 'Sign in with Google' button; selector may change — we try some heuristics
        try:
            # common text match
            page.click("text=Continue with Google")
        except Exception:
            try:
                page.click("text=Sign in with Google")
            except Exception:
                print("Could not find Google sign-in button automatically. Please click it in the opened browser window.")

        # Wait up to 60s for tokens to be captured
        for _ in range(60):
            if captured['bearer'] and captured['device_id']:
                break
            time.sleep(1)

        browser.close()

    if not captured['bearer'] or not captured['device_id']:
        raise RuntimeError('Failed to capture bearer token and/or device-id. Try running with --headed to see the browser and complete interactive login (and check selectors).')

    upsert_bw_item(item_name, captured['bearer'], captured['device_id'], session_key)
    print('Saved token + device-id to Bitwarden.')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--item-name', default='Suno API', help='Bitwarden item name to create/update')
    ap.add_argument('--headed', action='store_true', help='Run browser in headed mode')
    ap.add_argument('--headless', action='store_true', help='Run browser headless (default)')
    args = ap.parse_args()

    # default to headless unless headed passed
    headless = not args.headed
    try:
        run_playwright(args.item_name, headless=headless)
    except Exception as e:
        print('Error:', e)
        sys.exit(1)

# ... (keep all existing code) ...

def cli_main():
    """Entry point for console script."""
    ap = argparse.ArgumentParser(
        description='Authenticate with Suno and store credentials in Bitwarden'
    )
    ap.add_argument(
        '--item-name', 
        default='Suno API', 
        help='Bitwarden item name to create/update'
    )
    ap.add_argument(
        '--headed', 
        action='store_true', 
        help='Run browser in headed mode (recommended for Google SSO)'
    )
    args = ap.parse_args()

    headless = not args.headed
    try:
        run_playwright(args.item_name, headless=headless)
        return 0
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(cli_main())
