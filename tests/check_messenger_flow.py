"""Messenger flow check with a FAKE page token (Facebook's servers are not reached for real; only our webhook + AI side)."""
import hashlib, hmac, json, time, uuid, requests
from pymongo import MongoClient

API = open('/app/frontend/.env').read().split('REACT_APP_BACKEND_URL=')[1].split()[0] + '/api'
db = MongoClient('mongodb://localhost:27017')['replyflow']
tag = uuid.uuid4().hex[:6]
own = requests.post(f'{API}/auth/register', json={'email': f'fb_{tag}@test.com', 'password': 'secret123', 'business_name': f'FB Shop {tag}'}).json()
t, bid = own['token'], own['user']['business_id']
H = {'Authorization': f'Bearer {t}'}
s = requests.get(f'{API}/settings', headers=H).json()
s.update(fb_page_token='FAKE_PAGE_TOKEN', fb_app_secret='appsecret123', fb_verify_token='myverify', business_info='We sell T-shirts, $10 each. Open 9-18 daily.')
print('save fb settings', requests.put(f'{API}/settings', headers=H, json=s).status_code)
print('channel status', requests.get(f'{API}/channels/status', headers=H).json()['messenger'])

url = f'{API}/webhooks/messenger/{bid}'
r = requests.get(url, params={'hub.mode': 'subscribe', 'hub.verify_token': 'myverify', 'hub.challenge': 'CHALLENGE42'})
print('meta verify', r.status_code, r.text)
print('wrong verify token', requests.get(url, params={'hub.mode': 'subscribe', 'hub.verify_token': 'nope', 'hub.challenge': 'x'}).status_code)

body = json.dumps({'object': 'page', 'entry': [{'messaging': [{'sender': {'id': '99887766'}, 'message': {'mid': 'm1', 'text': 'How much is a T-shirt?'}}]}]}).encode()
sig = 'sha256=' + hmac.new(b'appsecret123', body, hashlib.sha256).hexdigest()
print('fake signature rejected', requests.post(url, data=body, headers={'X-Hub-Signature-256': 'sha256=bad', 'Content-Type': 'application/json'}).status_code)
print('signed message', requests.post(url, data=body, headers={'X-Hub-Signature-256': sig, 'Content-Type': 'application/json'}).status_code)

for _ in range(30):
    convs = requests.get(f'{API}/conversations', headers=H).json()
    items = convs.get('items', convs) if isinstance(convs, dict) else convs
    if items:
        msgs = requests.get(f"{API}/conversations/{items[0]['id']}/messages", headers=H).json()
        if any(m['role'] == 'ai' for m in msgs):
            break
    time.sleep(2)
print('inbox chat', items[0]['channel'] if items else None, '| name', items[0].get('name') if items else None)
for m in msgs:
    print(' ', m['role'], ':', m['text'][:120])

for c in ('settings', 'subscriptions', 'conversations', 'messages', 'ai_usage'):
    db[c].delete_many({'business_id': bid})
db.users.delete_many({'business_id': bid}); db.businesses.delete_one({'id': bid})
