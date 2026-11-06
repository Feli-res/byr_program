"""Read-only counters after the patched 4.11 run."""
import load_411 as l

print("docs", l.db("SELECT kind,state,COUNT(*) FROM search_documents GROUP BY kind,state;"))
print("jobs", l.db("SELECT state,COUNT(*) FROM search_index_jobs GROUP BY state;"))
print("goods502", l.db("""
SELECT d.source_id,d.indexed_at,g.created_at,
       TIMESTAMPDIFF(SECOND,g.created_at,d.indexed_at)
FROM search_documents d JOIN goods g ON g.id=d.source_id
WHERE d.kind='goods' AND d.source_id=502;
"""))
print("counts", l.db("""
SELECT (SELECT COUNT(*) FROM users),(SELECT COUNT(*) FROM posts),
       (SELECT COUNT(*) FROM comments),(SELECT COUNT(*) FROM goods),
       (SELECT COUNT(*) FROM messages),(SELECT COUNT(*) FROM subscriptions),
       (SELECT COUNT(*) FROM conversations);
"""))
print("duplicates", l.db("SELECT COUNT(*) FROM (SELECT conversation_id,sender_id,client_message_id,COUNT(*) c FROM messages GROUP BY conversation_id,sender_id,client_message_id HAVING c>1) x;"))
