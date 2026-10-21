# ReplyFlow — AI Auto-Reply Hub (PRD)

## Original problem
Website + AI auto-reply chat (Facebook Messenger, Telegram) where the AI understands what clients want and makes replying easy and fast.

## User choices
Generic business configured in settings (info + FAQs; shop/services) · Telegram + Messenger + website chat · Claude Sonnet 4.5 / Gemini 3 Flash (Emergent LLM key) · Landing + admin dashboard · tokens pasted later.

## Architecture
FastAPI + MongoDB (settings, conversations, messages, users) · emergentintegrations LlmChat · JWT bearer admin auth (seeded from env) · React + shadcn, dark theme (Outfit/Manrope).

## Implemented (2026-06)
- Landing page with live AI demo chat + floating widget (web channel)
- Admin login; unified inbox with channel filters, search (incl. message text), unread counts, polling
- Per-conversation AI on/off (human takeover), manual reply, "Suggest replies" (3 one-tap AI suggestions)
- AI Settings: business name/type/info, FAQs, model, tone, reply language, global auto-reply, AI tester
- Channels: Telegram token → auto setWebhook (secret_token header check); Messenger callback URL, verify token, page token; webhooks ingest + AI reply + send back
- Tested: backend 20/20, frontend flows pass

## Iteration 2 (2026-06)
- Messenger webhook verifies X-Hub-Signature-256 with App secret (rejects otherwise)
- Website chat rate limit: 6/min per session, 20/min + 150/h per IP (real IP = XFF[-3], spoof-proof)
- Embed code `<script src=".../api/widget.js" async>` (data-color, data-position) → iframe /embed?site=host
- Quick replies (Settings) → one-tap send chips in inbox composer
- AI customer summary (intent, stage, details, next step), cached by message count; side panel ≥1280px, strip below, intent tag in list
- Tested: iteration_2 all flows pass; XFF bypass fixed after

## Iteration 3 (2026-06)
- Emergent-managed Google login added alongside email/password; only emails in AI Settings → Team access (settings.allowed_emails) + ADMIN_EMAIL may sign in; both methods issue the same JWT
- Tested: iteration_3 pass; minor fixes (login lockout uses real client IP, allowed_emails normalised server-side, Google errors → 401/502)

## Backlog
- P1: Rate limiter is in-memory (single process); move to Mongo/Redis if scaling
- P2: Instagram/WhatsApp, analytics, widget colour/greeting customisation UI, team members
