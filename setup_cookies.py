#!/usr/bin/env python3
"""
One-time browser login to Substack. Reads credentials from .env, fills them in
automatically, and pauses only if a captcha appears. Run when substack.py fails.
"""

import json
import os
import pyotp
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

SUB_EMAIL       = os.environ["SUBSTACK_EMAIL"]
SUB_PASSWORD    = os.environ["SUBSTACK_PASSWORD"]
SUB_TOTP_SECRET = os.environ.get("SUBSTACK_TOTP_SECRET", "")
COOKIE_FILE     = os.path.join(os.path.dirname(__file__), ".substack_cookies.json")
PUB_BASE        = "https://giadaarchive.substack.com"


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        context = browser.new_context()
        page = context.new_page()

        print(f"Logging in as {SUB_EMAIL}...")
        page.goto("https://substack.com/sign-in", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Fill email
        email_field = page.query_selector('input[type="email"], input[name="email"]')
        if email_field:
            email_field.fill(SUB_EMAIL)
            page.wait_for_timeout(500)
            page.keyboard.press("Enter")
            page.wait_for_timeout(2000)
        else:
            print("  Could not find email field — please fill it in manually")

        # Click "Sign in with password" if shown
        for selector in ['a:has-text("password")', 'button:has-text("password")', '[data-testid="sign-in-with-password"]']:
            try:
                el = page.query_selector(selector)
                if el:
                    el.click()
                    page.wait_for_timeout(1500)
                    break
            except Exception:
                pass

        # After switching to password mode, Substack may show both email+password fields — re-fill email if empty
        email_field2 = page.query_selector('input[type="email"], input[name="email"]')
        if email_field2:
            current_val = email_field2.input_value()
            if not current_val:
                email_field2.fill(SUB_EMAIL)
                page.wait_for_timeout(300)

        # Fill password
        pw_field = page.query_selector('input[type="password"], input[name="password"]')
        if pw_field:
            pw_field.fill(SUB_PASSWORD)
            page.wait_for_timeout(500)
            page.keyboard.press("Enter")
            page.wait_for_timeout(2000)
        else:
            print("  Could not find password field — please fill it in manually")

        # If captcha appears, wait for user to solve it (up to 3 minutes)
        print("  If a captcha appears in the browser, solve it now.")
        print("  Waiting up to 3 minutes for login to complete...")

        # Poll until fully logged in (no more sign-in pages) or timeout
        logged_in = False
        totp_submitted = False
        for _ in range(60):
            page.wait_for_timeout(3000)
            url = page.url

            # Handle MFA page
            if "/mfa" in url or "/sign-in/mfa" in url:
                if SUB_TOTP_SECRET and not totp_submitted:
                    code = pyotp.TOTP(SUB_TOTP_SECRET).now()
                    print(f"  MFA page detected — entering TOTP: {code}")
                    # Try multiple selectors for the TOTP input
                    for sel in ['input[autocomplete="one-time-code"]', 'input[type="number"]', 'input[inputmode="numeric"]', 'input[name="token"]', 'input']:
                        try:
                            totp_field = page.query_selector(sel)
                            if totp_field and totp_field.is_visible():
                                totp_field.fill(code)
                                page.wait_for_timeout(500)
                                # Look for submit button
                                for btn_sel in ['button[type="submit"]', 'button:has-text("Verify")', 'button:has-text("Continue")', 'button:has-text("Submit")']:
                                    btn = page.query_selector(btn_sel)
                                    if btn and btn.is_visible():
                                        btn.click()
                                        break
                                else:
                                    page.keyboard.press("Enter")
                                totp_submitted = True
                                page.wait_for_timeout(2000)
                                break
                        except Exception:
                            pass
                continue

            # Check for inline TOTP field (not MFA page)
            totp_field = page.query_selector('input[autocomplete="one-time-code"], input[placeholder*="code" i]')
            if totp_field and totp_field.is_visible() and SUB_TOTP_SECRET and not totp_submitted:
                code = pyotp.TOTP(SUB_TOTP_SECRET).now()
                print(f"  Entering TOTP: {code}")
                totp_field.fill(code)
                page.wait_for_timeout(500)
                page.keyboard.press("Enter")
                totp_submitted = True
                page.wait_for_timeout(2000)
                continue

            # Check if we've left all sign-in pages
            if "sign-in" not in url and "login" not in url:
                logged_in = True
                break

        print(f"  URL after login: {page.url}")
        if not logged_in:
            print("  Timed out — session cookie not detected. Complete the login in the browser window.")

        # Navigate to publishing dashboard to confirm admin access
        page.goto(f"{PUB_BASE}/publish/posts", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        on_dashboard = "giadaarchive.substack.com/publish" in page.url
        print(f"  Publishing dashboard: {'YES' if on_dashboard else 'NO — ' + page.url}")

        cookies = context.cookies()
        browser.close()

        cookie_list = [
            {"name": c["name"], "value": c["value"], "domain": c.get("domain", ""), "path": c.get("path", "/")}
            for c in cookies
        ]

        with open(COOKIE_FILE, "w") as f:
            json.dump(cookie_list, f, indent=2)

        has_auth = any(c["name"] in ("substack.sid", "substack-sid") for c in cookie_list)
        print(f"\n{'Session saved' if has_auth else 'WARNING: no auth cookie'}  — {len(cookie_list)} cookies written to {COOKIE_FILE}")
        if on_dashboard:
            print("Login confirmed. You can now run: python3 substack.py")
        else:
            print("Did not reach the publishing dashboard. Check that your .env credentials match the giadaarchive owner account.")


if __name__ == "__main__":
    run()
