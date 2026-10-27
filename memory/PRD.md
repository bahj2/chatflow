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
- HF VoxCPM2 demo back up (2026-06): live Khmer seller-clone voice test OK in 2.4 s
- Demo video DONE with VoxCPM2 voices only: scripts/gen_demo_voice_hf.py (narrator = energetic young man, customer = cheerful young woman, seller = app default warm young woman; first clip of each voice reused as clone ref; each clip transcribed back + retried) → scripts/make_demo_video.py → /demo/replyflow-demo.mp4 (1080x1920, 54.8 s)
- Demo.jsx: voice-note bubble shows the real clip length from timeline.json
- User's own clips can still replace them: scripts/import_voice_clips.py FILES → make_demo_video.py
- Next (user-approved, after the video): split backend/server.py into routers (no behaviour change)

## Iteration 17 (2026-06) — Replyflow AI logo
- User logo (blue + purple reply bubbles) → transparent icon /brand/logo-icon.png, /brand/favicon.png, /brand/apple-touch-icon.png, /favicon.ico
- components/Brand.jsx (BRAND = "Replyflow AI", BrandMark) used in Landing nav, Login, Signup, Dashboard sidebar; tab title + meta description updated
- User picked both "rename" and "keep": brand lockups read "Replyflow AI", sentences/body copy keep "ReplyFlow"; sales video unchanged (user chose "only the app")
- Mobile dashboard header: business name truncates properly; hidden for superadmin (no room with the extra Businesses tab)

## Iteration 18 (2026-06) — Each shop = a different person (name, greeting, cloned voice)
- User: bot 1-3 / page 1-3 are separate shops (separate client accounts), each with its own person: voice + name + greeting
- Settings.assistant_name (max 40) → system prompt "Your name is X…"; Settings.greeting (max 500) → sent on Telegram /start (greeting only) and as the first message of every new chat (then the AI answers)
- get_or_create_conv returns is_new=True only when it created the chat
- UI: AI Settings → Business: "Seller name" + "Greeting for new customers"; Voice card title shows "<name>’s voice (voice clone)", notes each shop has its own
- Verified with tests/check_shop_voices.py (3 shops, VoxCPM2 HF): clone pitch follows each shop's sample (147→150 Hz man, 254→262 Hz young woman, 167→185 Hz elderly woman); greetings + names correct per shop; test shops deleted afterwards

## Iteration 19 (2026-06) — One bot / one page per shop (no mix-ups)
- PUT /settings: 409 if the Telegram bot (matched by bot id = token part before ":", so a revoked/regenerated token of the same bot is also caught) or the Facebook page (Settings.fb_page_id from Graph /me, set server-side) already belongs to another shop
- POST /channels/telegram/connect re-checks before setWebhook
- Verified: tests/check_unique_channels.py (same bot 409, same bot new secret 409, own bot 200, re-save 200; FB same page 409 / other page 200 with stubbed Graph lookup)
- Seller voice clones are stored per shop (settings.seller_voice_media_id per business_id), never shared

## Iteration 20 (2026-06) — UI redesign + light/dark toggle
- User (Khmer): "make the UI prettier"; chose Landing + Login/Signup + Dashboard; brand = logo blue→purple gradient, green kept as accent (AI-on / success / paid); light/dark toggle
- index.css: light :root + .dark tokens (background, surface, card, muted, border, primary indigo), .btn-brand / .bg-brand / .text-brand gradients, .card-shadow, theme-aware .grid-bg, color-scheme per theme
- lib/theme.js ThemeProvider (localStorage rf_theme, default dark) + public/index.html pre-paint script; components/ThemeToggle.jsx (data-testid theme-toggle) on Landing nav, auth pages, dashboard sidebar/mobile bar; Toaster follows theme
- scripts/theme_codemod.py converted hardcoded slate/white/#hex classes in all components/pages to tokens (TelegramDemo + Demo keep Telegram dark look)
- New: components/AuthShell.jsx (gradient showcase panel + form side) used by Login/Signup; Landing rebuilt (eyebrow pill, gradient headline, stat cards, 6 feature cards incl. Khmer voice + product photos, numbered steps, gradient CTA band, footer); Dashboard sidebar (business card, gradient active indicator, theme toggle); Settings sections are cards
- iteration_20: frontend 100% pass (both themes, 1920 + 390)

## Iteration 21 (2026-06) — Subscriptions (KHQR) + backend split
- Plans (backend/billing.py): Free trial 14 d/200 replies, Starter $10/1,000, Pro $25/3,000, Business $59/8,000 (30 days), top-up +1,000 replies $5; AI replies pause when the plan ends or replies run out (messages still reach the inbox); real AI cost tracked per shop/month (db.ai_usage)
- User choices: Pro/Business only = voice replies (Starter/trial answer voice messages in text), seller voice clone, Notion knowledge, team logins (1 / 3 / 10; ended plans = 1). NOT locked: AI summaries, suggested replies, seller name & greeting
- Payments: shops pay the platform admin's Bakong account (admin's AI Settings → Bakong KHQR). Auto turn-on when the admin's business has a KHQR.dev token (relay poll); otherwise admin confirms in Businesses → "Plan payments to check" (pending + expired, last 2 days, 2-click). Admin can also "Set plan" per shop (POST /api/admin/businesses/{bid}/plan {plan, days}; same plan running → days added)
- Fix: invoice QR no longer uploaded to object storage (was HTTP 500); invoice keeps the KHQR string and GET /api/billing/invoices/{id}/qr.png renders it
- Admin Businesses page: Paying shops + Plan revenue stats, Plan / AI cost columns, Set plan dialog
- backend/server.py split (no behaviour change, same 48 routes + 2 new): core.py (env, db, auth deps, Settings, rate limit, require_pro, platform_settings), ai.py, conversations.py, orders.py (KHQR orders + payments loop), replies.py (handle_incoming, deliver), routers/{auth,admin,settings,webhooks,inbox,shop,voice,notion,channels,subscriptions}.py
- iteration_21: backend 28/28 (tests/test_iter21_billing_refactor.py, run with -n 0), frontend 100%; minor follow-ups fixed after (ended plan team=1, Notion knowledge in suggest/ai-test only for Pro, top-up hidden when plan ended)
- Old unit tests importing `server` internals (test_iter12/13/14/15 unit, check_unique_channels.py) are obsolete after the split

## Backlog
- P1: Rate limiter is in-memory (single process); move to Mongo/Redis if scaling
- P1: Plan expiry reminders to shop owners; Khmer UI for Billing
- P2: Instagram/WhatsApp, analytics, team members

## Iteration 22 (2026-10) — Code check + "fix all until it works"
- Workspace was a fresh import: backend/.env + frontend/.env were missing, DB empty, node_modules broken. Recreated .env (local Mongo, DB_NAME=replyflow, Emergent LLM key, new JWT_SECRET / NOTION_ENC_KEY / WEBHOOK_CRON_SECRET, admin admin@replyflow.com / admin123); preview URL for REACT_APP_BACKEND_URL
- requirements.txt: litellm line had a #sha256 suffix that conflicted with emergentintegrations' pin → removed suffix (pip install works again)
- New JWT_SECRET → old Telegram webhook secrets no longer match: each shop must press "Save & connect" in Channels again
- Team security: sessions carry token_version ("tv"); members are signed out (401) when removed from Team access or when the plan no longer includes their seat (sorted allowed_emails order); owner-only: payment fields, channel tokens, team list, seller voice clone + transcript, Notion connect/disconnect, Telegram connect, billing checkout; members get secret fields blanked in GET /settings
- Google sign-in on a password account created without email proof (email_verified False) turns that password off + ends older sessions (password_off toast)
- Rate limiter moved to MongoDB (rate_hits, TTL); sign-up limit counted only after the duplicate-email check
- Frontend: 401 interceptor signs out only the rejected session and shows the reason on /login; owner-only notes for members (Settings, Channels, Billing)
- Tests: iteration_22 + iteration_23 pass; backend/tests/test_iter22_team_security.py, test_iter23_member_fixes.py; tests/check_team_security.py, tests/check_google_verify.py (Google reply stubbed)

## Iteration 23 (2026-10) — One-click "Connect with Facebook"
- User: "how make it easy" → chose one-click button; no Meta app yet (guide given in-app)
- Platform-owned Meta app (env: META_APP_ID, META_APP_SECRET, optional META_LOGIN_CONFIG_ID, META_WEBHOOK_VERIFY_TOKEN [generated]); Graph v26.0; button shows only when ID + secret + verify token are set
- backend/routers/meta.py: POST /api/meta/facebook/start (owner) → Facebook login URL (state in db.oauth_states, 10-min TTL); GET /api/meta/facebook/callback → code → long-lived user token → /me/accounts → db.fb_choices (token sealed with Fernet, 1-h TTL) → /dashboard/channels?fb=pick (or ?fb_error=); GET /api/meta/facebook/pages (taken flag); POST /api/meta/facebook/pages/{id}/connect → page token + POST /{page}/subscribed_apps (messages) → settings fb_page_token/fb_page_id/fb_page_name/fb_oauth=True; DELETE /api/meta/facebook (unsubscribe + clear); GET /api/meta/status
- One app-level webhook GET/POST /api/webhooks/meta/page (platform verify token, X-Hub-Signature-256 with platform app secret), routed by entry.id → shop with fb_oauth; shared dispatch_messenger() with the per-shop manual webhook (unchanged)
- Page token never sent to the browser in oauth mode; PUT /settings keeps oauth connection fields
- GET /api/admin/meta-setup (superadmin): redirect URI, webhook URL, verify token, permissions, status
- Frontend components/FacebookConnect.jsx: FacebookConnect (button, page picker, auto-connect when only 1 page, connected card with Change page / Disconnect, manual setup under "Advanced") + MetaSetupCard (admin-only 7-step guide with copy boxes) in Channels
- Verified: tests/check_facebook_connect.py (Graph STUBBED) all steps pass; UI screenshots desktop + 390; manual Messenger flow still works (tests/check_messenger_flow.py)
- NOT tested against real Meta (no app yet). Meta requires a Privacy Policy URL; App Review + Business verification needed before non-tester shops can connect

## Iteration 24 (2026-10) — Facebook live with real Meta app
- Real Meta app "Replyflow AI" (App ID in META_APP_ID) — keys verified; connected Page "Replyflow AI" to Vaa's business; real customer (SanVan Sambath) messages → AI replies delivered (messenger send 200, text + product image) after app published Live
- Fixes: page tokens taken from /me/accounts (no pages_read_engagement needed); Channels auto-finishes a pending Page pick even if ?fb=pick is lost (status.pending); httpx INFO logging off (tokens in URLs); POST /api/admin/meta-setup/webhook registers app Page webhook via Graph (/{app}/subscriptions) + status in admin card
- Public /privacy, /terms, /data-deletion pages (Legal.jsx, contact mond24036@gmail.com) + landing footer links — required by Meta to publish
- Manual Messenger setup hidden from shops (only platform admin, or shops already using it)
- Still needed for OTHER shops' Pages: Business verification + App Review (Advanced Access for pages_show_list, pages_messaging, pages_manage_metadata). Preview URL used in Meta; after deploy update redirect URI + press "Set up message webhook" on live site

## Iteration 25 (2026-10) — "Continue with Facebook" sign-in / sign-up
- User wanted website login as direct as the Facebook click → blue Continue/Sign up with Facebook on /login + /signup (shown only when META app configured; GET /api/auth/facebook/available)
- POST /api/auth/facebook/start (rate-limited) → same Facebook dialog + same registered callback (/api/meta/facebook/callback, state.purpose="login"), scopes public_profile,email + the 3 Page permissions → one step signs in AND shares the Page
- Identity: users.fb_uid first; else Facebook-confirmed email via shared auth.sign_in_verified() (same as Google: team join, unverified-password takeover protection); else fb-{id}@facebook.local account. New shop is named after the first shared Page
- Shared Pages saved as pending fb_choices → user lands on /dashboard/channels which auto-connects a single Page
- Session handoff: one-time login code (db.login_codes, 2-min TTL) → /auth/facebook page → POST /api/auth/facebook/finish → normal JWT (token never in URL)
- Verified: tests/check_facebook_login.py (Graph STUBBED) 8 scenarios pass; real button reaches Facebook login with the real app. Not yet tried by a real person end to end

## Iteration 26 (2026-10) — Instant "Connect with Facebook"
- The person's 60-day Facebook approval (user token) is kept sealed on users (fb_user_token_enc, fb_token_exp 55 d) after Facebook sign-in or any Connect
- POST /api/meta/facebook/quick (owner): remembered approval + 1 free Page → connects instantly (no Facebook screens); several Pages → in-app picker; none/expired/revoked → Facebook login URL (stale key cleared)
- Channels Connect button uses quick; picker has "Page not in the list? Choose it on Facebook"; Change page still opens Facebook
- tests/check_facebook_quick.py (Graph STUBBED) pass; connect + login tests still pass; Vaa's real connection untouched

## Iteration 27 (2026-10) — Connect in a small Facebook window
- Channels Connect / Change page open Facebook in a centered popup (display=popup) over our site; state.popup → callback returns to /fb-done (FacebookDone.jsx) which postMessages {source:"replyflow-fb", fb|fb_error} to the opener (same origin only) and closes; Channels then auto-connects one Page or shows the in-app picker
- Popup blocked → same-tab redirect fallback; popup opened as a tab without opener → /fb-done continues to /dashboard/channels; closed early → status re-check (guarded against double finish)
- /api/meta/status returns remembered → button uses instant quick connect when the person's Facebook approval is remembered, otherwise the popup
- Browser-verified: popup opens real Facebook, main page stays on Channels, /fb-done closes itself and the picker appears (desktop + 390 px, no overflow)

## Iteration 28 (2026-10) — Facebook "like Telegram" (paste Page token)
- Why: clients without a role on the platform Meta app get "Feature Unavailable" until Tech Provider + Business verification + App Review. Shop's OWN Meta app needs no review for its own Page (proved with Replyflow AI page)
- POST /api/meta/facebook/token {page_token, app_secret, base_url} (owner): debug_token (token inspects itself → app_id, type), personal token with one Page → uses that Page token, /me → page id/name, app secret checked via client_credentials, taken check, saves token/secret/new verify token, registers the shop's per-shop webhook (/api/webhooks/messenger/{bid}) on THEIR app via /{app_id}/subscriptions (Meta verifies instantly), subscribes Page (subscribed_apps). Clear errors for bad/expired token or wrong secret
- /api/meta/status: connected for token mode too, via = facebook|token; Disconnect clears token mode too
- PUT /settings: non-superadmin can't change fb_* fields (stale forms can't wipe a connection)
- Channels: blue button + "Or paste your Page token — like Telegram" (2 fields + Connect + 4-step how-to with our /privacy URL); connected card shows "with your Page token" (no Change page)
- tests/check_facebook_token.py (Graph STUBBED) all pass; real Graph rejects a bad token with the friendly message; UI desktop + 390 ok

## Iteration 29 (2026-10) — Clients: one button only + Meta App Review kit
- Clients see only "Connect with Facebook" (+ note: "Feature Unavailable" = waiting for Meta approval); Page-token box only for platform admin or shops already connected by token
- Admin MetaSetupCard → "Show Meta App Review answers": copy-ready texts for pages_show_list, pages_messaging, pages_manage_metadata, public_profile, email, reviewer test steps (uses current site URL) + 7-step ~2-min screen-recording script
- Approval path for user: Business verification → Become a Tech Provider → App Review (Advanced access) → Live. Recommend publishing the site first so Meta reviews the permanent URL

## Iteration 30 (2026-10) — Founder Bakong account
- Founder (superadmin business) Bakong account: tit_sambath@bkrt, merchant name "Replyflow AI" → subscription KHQR pays the founder (verified: Starter $10 invoice QR contains tit_sambath@bkrt)
- Founder's Bakong Open API token kept as secret BAKONG_TOKEN (backend env), injected by core.platform_settings() (unless a KHQR.dev rbk token is saved)
- payments: jwt_valid() (exp from token, no network) + can_check(); valid JWT → local QR with mode "relay" (auto-checked via KHQR(jwt).check_bulk_payments direct to api-bakong); billing.auto_confirm/poll use can_check
- The token the user gave EXPIRED 2026-06-06 (Bakong 401) → currently manual confirm in Admin Billing; user must renew at api-bakong.nbc.gov.kh and update BAKONG_TOKEN via secure box
- Iteration 30b: founder can paste a Bakong token (eyJ) in AI Settings → Bakong KHQR payments (superadmin only; shops still rbk only); checked on save (expiry + live Bakong call). bakong_khqr lib reports a rejected token as "UNPAID" → payments now call api-bakong directly for JWT (_bakong), single check_transaction_by_md5 per invoice (bulk endpoint returns 403 HTML to non-Cambodia servers). DB token wins over BAKONG_TOKEN secret; orders loop uses can_check. Founder's current token (secret) is EXPIRED → manual confirm until renewed

## Iteration 31 (2026-10) — KHQR.dev "not working" fix
- Cause: Vaa's business saved a KHQR.dev token whose store accepts only KHR; USD prices ($25) were rejected → customers got replies without QR; preview 400. Plus KHQR.dev limits: 1 req/s per token and 8 req/60 s per server IP (all shops)
- payments: convert() at USD_KHR_RATE (default 4100, env) + _relay_any retries in the store's currency and remembers it per token (_store_currency); make_qr returns amount/currency actually in the QR
- orders: order total/currency = QR amount, price_total/price_currency keep the original; caption "102,500៛ ($25.00)"
- billing: invoice amount/currency from QR + price_usd (in INV_FIELDS); admin revenue sums price_usd; UI money(amount,currency,priceUsd)
- _relay_call: per-token 1.1 s spacing; shared per-IP budget (_MAX 7/60 s, 3 kept for customer QRs; background payment check + deeplink only use spare budget); rate limit → follow "Retry in Ns" if it fits else friendly BUSY; IP-limit fills window with entries expiring after the pause (sorted deque); "Failed to validate store payment link" retried up to 2 times
- /api/payments/preview no longer calls token_ok first (saves a call)
- Tests: iteration_24/25/26 + tests/test_iter24*, test_iter25_khqr_followups.py (live), test_iter26_khqr_budget_unit.py (19 unit) pass

## Iteration 32 (2026-10) — KHQR.dev billing, Facebook "Coming soon", professional dashboard
- Founder billing now uses the KHQR.dev rbk_ token (founder settings khqr_token), so plans turn on automatically. KHQR.dev QR pays KHQR.dev's ABA PayWay merchant ("DevPro by S.HOU"), which pays out to the founder. It does NOT pay tit_sambath@bkrt directly. The old BAKONG_TOKEN (JWT) expired on 6 Jun 2026.
- Facebook locked for shops: META_PUBLIC=false in backend/.env. locked_for() in routers/meta.py blocks start/quick (403) and Facebook sign-in; Channels shows a "Coming soon" card. Superadmin is unaffected. Set META_PUBLIC=true after Meta App Review.
- Design pass: shared PageHeader (components/PageHeader.jsx), grouped sidebar + plan chip, refined Section, tables, plan cards, redesigned KHQR pay dialog.
- Tested in iteration_28 (100% backend and frontend).
- Backlog: show the plan chip on mobile; on the deployed app, paste the rbk_ token into the admin AI Settings → Payments (the production DB is separate).

## Iteration 33 (2026-10) — Products stock + categories, AI Settings tabs
- Products: category + stock (null = not tracked). PATCH /api/products/{id}/stock. Stock goes down by itself when an order is paid (orders.settle_order). AI catalog shows the stock; order_problem blocks sold-out items and quantities above what's left.
- Products page: summary cards (total/in/low ≤3/sold out) that filter the grid, category chips, stock pill + stepper on each card, dialog with category + Track stock switch.
- AI Settings split into tabs: Business / AI & voice / Knowledge / Payments / Team.
- Switch "on" is now emerald so it's visible in dark mode.
- Tested in iteration_29 (100%); the LOW issues it found are fixed.
- Backlog: product variants (sizes/colors), SKU, hide product from AI, low-stock alert, CSV import/export, personality presets, shop hours.

## Iteration 34 (2026-10) — Free trial + Khmer tutorial video
- Trial: 14 days, 200 replies, Pro features (Notion, 3 logins), voice-to-voice off. PLANS[*]["voice"]; view() returns voice; effective() uses voice; require_voice in core.py is used by routers/voice.py.
- Landing: hero "Start 14-day free trial", #video section, #pricing with trial card + 3 plans (components/LandingPricing.jsx). Dashboard: sidebar play button opens the tutorial video.
- Video: /app/frontend/public/videos/replyflow-tour.mp4 (2:02, 1280x720, Khmer voice gpt-4o-mini-tts "shimmer", soft style, Khmer captions burned in through the browser overlay) + poster jpg. Rebuild: /app/video_build (scenes.json → tts.py → seed.py → record.py → mux.py). Demo shop tour@replyflow.com. The Playwright ffmpeg was swapped for the imageio-ffmpeg binary at /pw-browsers/ffmpeg-1013.
- Note: the HF VoxCPM2 demo (Khmer voice replies) returned 503 during this session.
- Tested in iteration_30 (100%).

## Iteration 35 (2026-10) — Professional sign-up / login
- New components/AuthFields.jsx: inputs with labels and icons, show/hide password, strength meter (Too weak/Weak/Good/Strong with a checklist), trial badge, secure note.
- Sign-up now needs 8+ characters with a letter and a number (checked in the browser and in RegisterIn.field_validator in routers/auth.py). Existing logins are not affected.
- Signup button reads "Start free trial", with a Terms/Privacy note. Login says "Welcome back".
