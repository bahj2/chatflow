# Auth Testing Playbook (ReplyFlow)

App uses its own JWT bearer token (localStorage `rf_token`) for BOTH login methods.
- Password: POST /api/auth/login {email,password} -> {token,user}
- Google (Emergent-managed): Login button -> https://auth.emergentagent.com/?redirect=<origin>/dashboard
  -> returns to /dashboard#session_id=... -> frontend AuthCallback POST /api/auth/google {session_id}
  -> backend calls https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data (X-Session-ID)
  -> email must be in settings.allowed_emails (or ADMIN_EMAIL) else 403 -> issues same JWT.

## Tests
1. curl POST /api/auth/google {"session_id":"bogus"} -> 401
2. Password login still works; GET /api/auth/me with Bearer token -> user
3. Login page shows google-login-btn; clicking navigates to auth.emergentagent.com with redirect=<origin>/dashboard
4. /dashboard#session_id=bogus -> shows "Signing you in…" then redirects to /login with login-error text
5. AI Settings -> Team access: add email (allowed-email-input, add-allowed-email-btn), Save, reload -> persists; remove works
Real Google sign-in cannot be automated (needs a real Google account).

## Forgot password (added 2026-10)
- POST /api/auth/forgot-password {email} -> always {"ok":true} (no account enumeration). Limits: 1/min per email, 5/hour per email, 10/hour per IP. Superadmin is skipped (their password comes from ADMIN_PASSWORD env).
- Stores db.password_resets {email,user_id,digest,tries,exp}. digest = HMAC-SHA256(key=JWT_SECRET, msg=f"{email}:{code}").hexdigest()
- Tests can't read the email: after forgot-password, overwrite `digest` with the HMAC of a known code (e.g. 424242) using JWT_SECRET from /app/backend/.env.
- POST /api/auth/reset-password {email,code,password} -> {token,user} (auto sign-in). Wrong code -> 400; after 5 wrong tries the record is deleted; single use. Bumps token_version (old sessions get 401), sets email_verified true, clears login lockouts.
- Password policy (register + reset): 8+ characters with a letter and a number.
- Email: Emergent managed email (backend/mailer.py), from_name = EMAIL_FROM_NAME ("Replyflow AI").
