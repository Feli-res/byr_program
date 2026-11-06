"""Read-only counters for the 4.11 isolated database."""
import load_411 as l

print("search_documents", l.db("SELECT kind,state,COUNT(*) FROM search_documents GROUP BY kind,state;"))
print("jobs", l.db("SELECT state,COUNT(*) FROM search_index_jobs GROUP BY state;"))
print("ready_lag_seconds", l.db("SELECT MAX(TIMESTAMPDIFF(SECOND,indexed_at,UTC_TIMESTAMP(6))) FROM search_documents WHERE state='ready';"))
print("counts", l.db("SELECT (SELECT COUNT(*) FROM users),(SELECT COUNT(*) FROM posts),(SELECT COUNT(*) FROM comments),(SELECT COUNT(*) FROM goods),(SELECT COUNT(*) FROM messages),(SELECT COUNT(*) FROM subscriptions),(SELECT COUNT(*) FROM conversations);"))
print("duplicate_messages", l.db("SELECT COUNT(*) FROM (SELECT conversation_id,sender_id,client_message_id,COUNT(*) c FROM messages GROUP BY conversation_id,sender_id,client_message_id HAVING c>1) x;"))
print("recent_goods", l.db("SELECT id,brand,title FROM goods ORDER BY id DESC LIMIT 8;"))
