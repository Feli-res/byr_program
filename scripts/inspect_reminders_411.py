import load_411 as l

print(l.db("SELECT id, JSON_UNQUOTE(JSON_EXTRACT(conditions,'$.brand')), owner_id FROM subscriptions WHERE id BETWEEN 101 AND 110;"))
print(l.db("SELECT id, brand FROM goods WHERE id BETWEEN 503 AND 512;"))
print(l.db("SELECT target_id, COUNT(*) FROM notifications WHERE kind='goods_match' AND target_id BETWEEN 503 AND 512 GROUP BY target_id;"))
