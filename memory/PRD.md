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

## Iteration 4 (2026-06) — Multi-business SaaS + scale
- Self sign-up (/signup, email+password or Google) → each signup gets its own business: settings, AI, quick replies, team, Telegram/Messenger, inbox, embed code
- All data scoped by business_id (tenant isolation verified); old single-tenant data migrated into admin's business; admin = superadmin with Businesses overview page
- Per-business URLs: /api/public/{bid}/..., /api/webhooks/telegram/{bid}, /api/webhooks/messenger/{bid}, widget.js data-business
- Inbox paging (50/page, compound cursor, infinite scroll, total count, debounced search); indexes added; AI reply retries (3x)
- Load test (scripts/load_test_100.py): 100 simultaneous chats → 100/100 AI replies, 6.7s total, p50 5.5s, p95 6.6s; 3,000-chat inbox: page ≈47ms, search ≈60ms
- Admin's real bot @Dev_nara_bot webhook re-pointed to new URL after migration
- Tested: iteration_4 + iteration_5 pass

## Iteration 5 (2026-06) — Voice + product photos
- Voice in: web widget mic (MediaRecorder), Telegram voice/audio, Messenger audio → ffmpeg (imageio-ffmpeg) → whisper-1 transcript
- Voice out (only when customer sent voice; per-business toggle + 9 OpenAI tts-1 voices); Telegram sendVoice, Messenger audio attachment, web <audio>
- Khmer: VoxCPM2 (self-hosted, OpenAI-compatible /v1/audio/speech) with seller voice clone (sample upload/record → 16k wav, auto transcript); used for Khmer (or all) replies; falls back to OpenAI on error/unset. NOT tested against a real VoxCPM2 server
- Products page (≤300/business) with images in Emergent Object Storage; AI catalog in prompt, [[show:refs]] tag → product photo + name + price sent (Telegram sendPhoto, Messenger image, web cards)
- Media served via /api/media/{id} (seller voice requires ?auth token)
- Tested: iteration_6 pass (19/20, delete-404 fixed after)

## Iteration 6 (2026-06) — Khmer voice clarity fix
- Root cause: whisper-1 romanized Khmer speech (AI couldn't understand); tts-1 Khmer ~21% intelligible
- STT → Gemini 3 Flash audio transcription (native script) with Whisper fallback; old Sambath transcripts corrected
- Khmer TTS → Microsoft native neural voices via edge-tts (Sreymom female 97.7% / Piseth male 92.4% round-trip clarity), fallback gpt-4o-mini-tts (92%, slow); VoxCPM2 still first if configured
- Spoken replies: no emoji/symbols, numbers as words, no English words; Noto Sans Khmer font fallback; preview uses unsaved selection; Literal validation for voice fields
- Tested: iteration_7 8/8 pass
- Note: edge-tts is Microsoft Edge's free read-aloud service (unofficial); official Azure Speech key = same voices, more reliable for production

## Backlog
- P1: Rate limiter is in-memory (single process); move to Mongo/Redis if scaling
- P2: Instagram/WhatsApp, analytics, widget colour/greeting customisation UI, team members
