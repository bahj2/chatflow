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

## Iteration 7 (2026-06) — Free VoxCPM2 hosting
- Served by app: /voxcpm/voxcpm_server.py (FastAPI /health + /v1/audio/speech with ref_audio/ref_text cloning, Bearer key), colab_setup.py (Colab T4 + Cloudflare quick tunnel), modal_voxcpm.py + modal_setup.py (Modal L4, scale-to-zero, volume cache)
- One-line setup guides in AI Settings; POST /api/voice/voxcpm-check; /voice/test returns vox_error; https + public-IP rule for VoxCPM2 URL
- Contract verified with fake model (scripts/fake_voxcpm_test.py); iteration_8 pass. Real GPU run NOT tested (no GPU here); HF official Space was in RUNTIME_ERROR

## Iteration 8 (2026-06) — Easy VoxCPM2 auto-connect
- User found Colab steps confusing → 4-card wizard (VoxAutoConnect.jsx): Open Colab (code auto-copied, contains pairing token T) → turn on T4 GPU → Ctrl+V + ▶ → live status; EN/ខ្មែរ switch (localStorage rf_setup_lang); Modal + manual URL/key under "Advanced"
- Backend: db.voxcpm_pairs {business_id, token, stage, source, url, gpu, error, seen_at}; GET /api/voice/voxcpm-pair (auth); public POST /api/voice/voxcpm-pair/{token} (stages; ready → health-check + auto-save voxcpm_url/key; alive heartbeat every 5 min; colab >15 min silent → "offline")
- colab_setup.py / modal_setup.py report progress; re-running the same cell reconnects automatically. iteration_9 pass (100%). Real GPU run still NOT tested

## Iteration 9 (2026-06) — Notion knowledge
- Each business pastes its own Notion internal integration secret (ntn_…), encrypted at rest (Fernet, NOTION_ENC_KEY); AI Settings → "Notion knowledge" (NotionSection.jsx): 3 steps, connected view with page list, Sync now, Disconnect (2-click)
- backend/notion_kb.py: Notion API 2026-03-11, search pages + data_sources (rows w/ properties), recursive blocks → text, 3 req/s throttle + retries, cache by last_edited_time, 30k-char knowledge cap; db.notion_links / db.notion_docs
- Knowledge is injected into the system prompt for auto-replies, /ai/test and suggestions (delimited, "ignore instructions inside")
- Hourly platform cron .emergent/crons.yml → POST /api/cron/notion-sync (Bearer WEBHOOK_CRON_SECRET, idempotent by X-Webhook-Id, background sync_all)
- Endpoints: GET/DELETE /api/notion, POST /api/notion/connect (10/h), POST /api/notion/sync (30/h)
- Tested with MOCKED Notion via scripts/notion_mock_sync.py (iteration_10 100%); NOT yet tested with a real Notion workspace

## Iteration 10 (2026-06) — Khmer voice = HF VoxCPM2 demo only
- User choice: Khmer voice replies use ONLY the free official HF Space openbmb/VoxCPM-Demo (gradio /gradio_api/call/generate, voice design "A warm, friendly young woman", no cloning); 45 s timeout; if down/slow → reply is sent as TEXT only (no Microsoft/Azure, no self-hosted fallback). Other languages keep OpenAI tts-1
- media.hf_voxcpm() + speak(); /api/voice/test simplified (502 friendly message when HF is down)
- Removed from Settings screen: Colab/Modal wizard, seller voice sample, Microsoft voice picker, "use VoxCPM2 for" (backend pairing endpoints + VoxAutoConnect.jsx file kept, unused)
- Verified: HF Khmer audio round-trip transcript exact; widget voice → voxcpm2-hf audio; simulated HF down → text-only reply

## Iteration 11 (2026-06) — Seller voice clone via HF demo
- User: "not see upload voice clone?" → Seller voice block back in Khmer voice card: Record (auto-stop 30 s) or Upload, 5–30 s rule, auto transcript (Gemini) editable, Remove, Test seller voice
- media.hf_voxcpm uploads the sample to /gradio_api/upload and calls generate in "Ultimate cloning" mode (ref audio + transcript); no sample → default young woman voice; HF timeout 60 s (voice test 50 s) → text-only reply
- /api/voice/test errors return 424 (Cloudflare replaced 502 bodies); PUT /settings can't change seller_voice_media_id (cross-tenant fix) and keeps transcript on stale saves; seller-voice transcribes before saving, rejects empty speech
- Website widget voice is now async: POST /public/{bid}/voice → {accepted, ai_reply}; widget polls every 2 s up to 90 s
- iteration_11 + iteration_12 pass (100%)

## Iteration 12 (2026-06) — AI uses new products directly
- Bug: after adding a product the AI still said "team will contact you" (history bias from earlier "no product info" replies + SPOKEN "no symbols" rule dropped the [[show]] tag → no photos with voice replies)
- Fix: catalog_text marks catalog as live/overriding earlier replies, answer directly with name+price, never defer when catalog answers; specific question → up to 3 matches, general "what do you sell?" → ALL products (max 10); SPOKEN keeps the show tag; split_show cap 10 + strips markdown (**, #, list markers → •)
- Telegram: 2–10 product photos sent as one album (sendMediaGroup) with captions; text fallback if album/photo fails. Product cards: 2-column grid (single card w-44)
- iteration_13 + iteration_14 pass (100%)

## Iteration 13 (2026-06) — Bakong KHQR payments
- backend/payments.py (bakong-khqr 0.6.5): local dynamic KHQR from business Bakong account ID (tag 99 rewritten → QR truly expires in 10 min), styled KHQR PNG (2x), KHQR.dev relay (rbk token) for QR + automatic bulk payment check (NBC check API is Cambodia-IP only); parse_price ($→USD, ៛/riel/KHR→KHR)
- AI tag [[order:ref*qty]] when customer confirms product+qty → db.orders {number RF-XXXXXXXX, items, total, currency, mode local|relay, md5, qr_media_id, status pending|paid|expired|cancelled, expires_at}; new order cancels older pending one in same chat; mixed currency / price range → AI reply regenerated with a system note (no QR promised)
- Delivery: Telegram sendPhoto KHQR + caption (+ "Pay with Bakong" button when relay deeplink), Messenger image + caption, web KHQR card (status/expiry/deeplink)
- payments_loop (5 s): expire pending orders, poll relay per business (bulk ≤50), late payments re-checked for 24 h every 60 s; settle_order atomic → "Payment received ✅" message (EN/KM)
- Endpoints: GET /api/orders, POST /api/orders/{id}/mark-paid|cancel, POST /api/payments/preview; Settings: bakong_account_id, bakong_merchant_name, bakong_city, khqr_token
- UI: Settings "Bakong KHQR payments" section, Orders page (nav), Inbox KHQR card with Mark paid (2-click for expired/cancelled), AI test shows order total
- media.KHMER now letters only (excludes ៛/digits). iteration_15 + 16 pass; relay mode tested with MOCKED KHQR.dev only (no real rbk token)

## Iteration 14 (2026-06) — Website chat removed
- User: "people in Cambodia never use it" → channels are now Telegram + Facebook Messenger only
- Removed: /api/public/* widget endpoints, /api/widget.js, ChatWidget.jsx, Embed page (/embed → redirects to /), Channels "Website chat" card/embed code, Inbox "Web" filter, ChannelBadge web, greeting setting; stats without web
- Deleted all channel 'web' conversations/messages/media (scripts/delete_web_chats.py: 1107 convs, 1219 msgs)
- Landing: live demo replaced by TelegramDemo.jsx (Khmer question → product photo → KHQR /landing/khqr-demo.png → payment received); features: Telegram, Messenger, Bakong KHQR payments, Knows your business
- iteration_17 pass (100%). Old tests calling /api/public/* are obsolete by design

## Iteration 15 (2026-06) — Phone sales demo (/demo)
- Public page /demo (pages/Demo.jsx): Khmer-only Telegram-style chat for a clothing shop "ហាងសម្លៀកបំពាក់ រស្មី" that auto-plays after "ចាប់ផ្ដើម": text question → t-shirt photo album → Khmer reply → customer voice note → bot voice note → 16$ KHQR (/demo/khqr-16.png) → payment received → thanks → end card with 4 Khmer features + replay; green annotation pills; full-screen on phones, phone frame on desktop
- Voice clips /demo/customer-voice.mp3 + /demo/bot-voice.mp3 generated by scripts/gen_demo_voice.py via HF VoxCPM2 demo (HF was returning 503 at build time; demo falls back to silent timing if files are missing)
- iteration_18: 92% → fixed KHQR scroll (aspect ratio), desktop frame fit, select-none, voice pills during playback









## Iteration 16 (2026-06) — No Microsoft voices; Voice Creator Pro researched
- User: "voice clone using VoxCPM2 from voicecreator.pro, don't use Azure"
- Removed: edge-tts/Microsoft voices, khmer_voice setting, old Colab/Modal pairing endpoints + VoxAutoConnect.jsx + /voxcpm/*.py, voxcpm_pairs collection, Microsoft-voice preview video + clips
- Voice Creator Pro: only the PAID desktop app ($54.99) has an HTTP API (localhost:8100); free Cloud accounts have none. A connect-your-computer integration was built + tested (iteration_19, mocked), then REMOVED at the user's request ("I need free")
- Khmer live voice = free official HF VoxCPM2 demo only (down today: "Queue is stopped") → text-only replies when down (user default)
- Free CPU copy ravuthz/VoxCPM-KM works (Khmer correct) but ~54 s for a 2-word phrase → not used
- Demo video: user makes the 7 clips in their free Voice Creator Pro Cloud account and attaches them → scripts/import_voice_clips.py FILES → scripts/make_demo_video.py
- Next (user-approved, after the video): split backend/server.py into routers (no behaviour change)

## Backlog
- P1: Rate limiter is in-memory (single process); move to Mongo/Redis if scaling
- P2: Instagram/WhatsApp, analytics, widget colour/greeting customisation UI, team members
