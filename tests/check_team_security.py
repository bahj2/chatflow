import os, uuid, bcrypt, requests
from pymongo import MongoClient

API = open('/app/frontend/.env').read().split('REACT_APP_BACKEND_URL=')[1].split()[0] + '/api'
db = MongoClient('mongodb://localhost:27017')['replyflow']
H = lambda t: {'Authorization': f'Bearer {t}'}

admin = requests.post(f'{API}/auth/login', json={'email': 'admin@replyflow.com', 'password': 'admin123'}).json()['token']
tag = uuid.uuid4().hex[:6]
own = requests.post(f'{API}/auth/register', json={'email': f'owner_{tag}@test.com', 'password': 'secret123', 'business_name': f'Shop {tag}'}).json()
ot, bid = own['token'], own['user']['business_id']
print('register', bool(ot))
print('set pro', requests.post(f'{API}/admin/businesses/{bid}/plan', headers=H(admin), json={'plan': 'pro', 'days': 30}).status_code)

mem_email = f'member_{tag}@test.com'
s = requests.get(f'{API}/settings', headers=H(ot)).json()
s.update(allowed_emails=[mem_email], bakong_account_id='owner@aclb', telegram_token='', khqr_token='')
print('owner save team', requests.put(f'{API}/settings', headers=H(ot), json=s).status_code)

db.users.insert_one({'id': str(uuid.uuid4()), 'email': mem_email, 'role': 'member', 'business_id': bid,
                     'password_hash': bcrypt.hashpw(b'member123', bcrypt.gensalt()).decode(), 'created_at': 'x'})
r = requests.post(f'{API}/auth/login', json={'email': mem_email, 'password': 'member123'})
print('member login', r.status_code)
mt = r.json()['token']

ms = requests.get(f'{API}/settings', headers=H(mt)).json()
print('member sees bakong', ms['bakong_account_id'], '| secrets blank', ms['fb_app_secret'] == '' and ms['khqr_token'] == '')
ms.update(bakong_account_id='thief@aclb', allowed_emails=[mem_email, 'friend@x.com'], business_info='member edited info')
r = requests.put(f'{API}/settings', headers=H(mt), json=ms)
print('member save', r.status_code)
cur = requests.get(f'{API}/settings', headers=H(ot)).json()
print('bakong kept', cur['bakong_account_id'] == 'owner@aclb', '| team kept', cur['allowed_emails'] == [mem_email], '| info changed', cur['business_info'] == 'member edited info')
print('member telegram connect', requests.post(f'{API}/channels/telegram/connect', headers=H(mt), json={'base_url': 'https://x'}).status_code)
print('member inbox', requests.get(f'{API}/conversations', headers=H(mt)).status_code)

cur['allowed_emails'] = []
print('owner removes member', requests.put(f'{API}/settings', headers=H(ot), json=cur).status_code)
r = requests.get(f'{API}/conversations', headers=H(mt))
print('removed member inbox', r.status_code, r.json().get('detail'))
r = requests.post(f'{API}/auth/login', json={'email': mem_email, 'password': 'member123'})
print('removed member login', r.status_code, r.json().get('detail'))

# plan downgrade: member re-added, plan -> starter (1 login) => member blocked
cur['allowed_emails'] = [mem_email]
requests.put(f'{API}/settings', headers=H(ot), json=cur)
print('re-added member login', requests.post(f'{API}/auth/login', json={'email': mem_email, 'password': 'member123'}).status_code)
requests.post(f'{API}/admin/businesses/{bid}/plan', headers=H(admin), json={'plan': 'starter', 'days': 30})
r = requests.post(f'{API}/auth/login', json={'email': mem_email, 'password': 'member123'})
print('member after downgrade', r.status_code, r.json().get('detail'))

# session version: bump -> old owner token rejected
db.users.update_one({'id': own['user']['id']}, {'$inc': {'token_version': 1}})
r = requests.get(f'{API}/auth/me', headers=H(ot))
print('old session after bump', r.status_code, r.json().get('detail'))
print('owner relogin', requests.post(f'{API}/auth/login', json={'email': f'owner_{tag}@test.com', 'password': 'secret123'}).status_code)
u = db.users.find_one({'id': own['user']['id']})
print('email_verified flag', u.get('email_verified'))
print('rate_hits docs', db.rate_hits.count_documents({}))

# cleanup
db.users.delete_many({'email': {'$in': [mem_email, f'owner_{tag}@test.com']}})
for c in ('settings', 'subscriptions', 'invoices'):
    db[c].delete_many({'business_id': bid})
db.businesses.delete_one({'id': bid})
