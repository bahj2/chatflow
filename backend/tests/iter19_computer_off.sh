#!/bin/bash
# Iteration 19: 'computer off' case (mock stopped, tunnel up) + webhook basic checks
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)/api
TUNNEL=${VCP_TUNNEL:-https://studios-sectors-saver-list.trycloudflare.com}
KM='សួស្តីបង! អរគុណដែលបានទាក់ទងមក។'
TOK=$(curl -s -X POST $API/auth/login -H 'Content-Type: application/json' -d '{"email":"vcp-test@example.com","password":"vcptest123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
H="Authorization: Bearer $TOK"
echo "connect:"; curl -s -o /dev/null -w '%{http_code}\n' -X POST $API/voice/vcp/connect -H "$H" -H 'Content-Type: application/json' -d "{\"url\":\"$TUNNEL\",\"key\":\"test-key\"}"
kill $(pgrep -f 'scripts/mock_vcp.py'); sleep 2
echo "only_vcp (mock off):"; curl -s -w ' %{http_code} %{time_total}s\n' -X POST $API/voice/test -H "$H" -H 'Content-Type: application/json' -d "{\"text\":\"$KM\",\"only_vcp\":true}"
echo "general khmer (mock off):"; curl -s -w ' %{http_code} %{time_total}s\n' -X POST $API/voice/test -H "$H" -H 'Content-Type: application/json' -d "{\"text\":\"$KM\"}"
(cd /app && setsid nohup python3 /app/scripts/mock_vcp.py port=8199 key=test-key > /tmp/mock_vcp.log 2>&1 &)
sleep 3
echo "only_vcp (mock back):"; curl -s -w ' %{http_code}\n' -X POST $API/voice/test -H "$H" -H 'Content-Type: application/json' -d "{\"text\":\"$KM\",\"only_vcp\":true}"
curl -s -o /dev/null -X DELETE $API/voice/vcp -H "$H"
BID=$(curl -s $API/auth/me -H "$H" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("business_id") or d.get("user",{}).get("business_id"))')
echo "tg webhook no secret:"; curl -s -w ' %{http_code}\n' -X POST $API/webhooks/telegram/$BID -H 'Content-Type: application/json' -d '{}'
echo "messenger verify bad token:"; curl -s -w ' %{http_code}\n' "$API/webhooks/messenger/$BID?hub.mode=subscribe&hub.verify_token=bad&hub.challenge=1"
