# Skill: Re-authenticate Substack Session

Re-run the one-time browser login to Substack when `substack.py` fails with an authentication error.

**Script:** `setup_cookies.py`
**Run when:** `substack.py` fails with a login/auth error

---

## When to use

- `substack.py` throws a 401 or redirect-to-login error
- Substack session cookies have expired (typically every few weeks)
- After a password change or TOTP reset

---

## Prerequisites in .env

```env
SUBSTACK_EMAIL=...
SUBSTACK_PASSWORD=...
SUBSTACK_TOTP_SECRET=...   # Base32 TOTP secret (optional — only if 2FA is enabled)
```

---

## Process

```bash
python3 setup_cookies.py
```

The script:
1. Opens a real Chromium browser window (not headless)
2. Navigates to `substack.com/sign-in`
3. Fills in email and password automatically
4. Handles TOTP 2FA automatically if `SUBSTACK_TOTP_SECRET` is set
5. Pauses if a CAPTCHA appears — complete it manually in the browser window
6. Saves cookies to `.substack_cookies.json`

After the script completes, re-run `substack.py` as normal.

---

## Output

- `.substack_cookies.json` written to the repo root
- `substack.py` reads this file on every run — once refreshed, scheduling resumes normally

---

## Notes

- The browser window is visible (not headless) — do not close it until the script says "Done"
- If CAPTCHA appears and you miss it, the script will hang. Just re-run it
- TOTP is generated from `SUBSTACK_TOTP_SECRET` using `pyotp` — no manual entry needed
