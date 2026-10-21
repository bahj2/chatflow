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
