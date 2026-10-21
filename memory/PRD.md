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

## Backlog
- P1: Messenger X-Hub-Signature-256 check (app secret); rate limit public chat
- P1: Embeddable widget script for external websites
- P2: Customer context panel (intent, summary), quick-reply templates, Instagram/WhatsApp, analytics
