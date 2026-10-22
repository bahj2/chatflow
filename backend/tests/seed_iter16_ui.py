# Iteration 16 UI seed: 3 TEST_ widget orders -> pending / expired / cancelled (statuses forced in Mongo)
import json
import sys
import time
import uuid

sys.path.insert(0, "/app/backend/tests")
from test_iter15_khqr_live import chat, khqrs, mdb  # noqa: E402

out = {}
for st in ["pending", "expired", "cancelled"]:
    sid = f"TEST_khqr16_ui_{st}_" + uuid.uuid4().hex[:5]
    rep = chat(sid, "I want to buy 2 Iced Palm Sugar Latte, confirmed")
    k = khqrs(rep)[0]
    if st != "pending":
        mdb.orders.update_one({"id": k["order_id"]}, {"$set": {"status": st}})
        mdb.messages.update_many({"attachments.order_id": k["order_id"]}, {"$set": {"attachments.$[a].status": st}},
                                 array_filters=[{"a.order_id": k["order_id"]}])
    out[st] = {"number": k["number"], "order_id": k["order_id"], "conv": mdb.orders.find_one({"id": k["order_id"]})["conversation_id"]}
    time.sleep(2)
print(json.dumps(out))
