CREATE TABLE posts (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  author_id BIGINT UNSIGNED NOT NULL,
  board_id BIGINT UNSIGNED NOT NULL,
  title VARCHAR(100) NOT NULL,
  body_markdown MEDIUMTEXT NOT NULL,
  visibility ENUM('public','hidden') NOT NULL DEFAULT 'public',
  pinned BOOLEAN NOT NULL DEFAULT FALSE,
  version INT UNSIGNED NOT NULL DEFAULT 1,
  deleted_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY ix_post_feed(board_id,visibility,deleted_at,pinned,created_at,id),
  KEY ix_post_owner(author_id,created_at,id),
  FOREIGN KEY(author_id) REFERENCES users(id),
  FOREIGN KEY(board_id) REFERENCES boards(id),
  CHECK (CHAR_LENGTH(title) BETWEEN 2 AND 100),
  CHECK (CHAR_LENGTH(body_markdown) BETWEEN 1 AND 20000)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE comments (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  post_id BIGINT UNSIGNED NOT NULL,
  author_id BIGINT UNSIGNED NOT NULL,
  parent_id BIGINT UNSIGNED NULL,
  body VARCHAR(2000) NOT NULL,
  visibility ENUM('public','hidden') NOT NULL DEFAULT 'public',
  deleted_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_comment_post(id,post_id),
  KEY ix_comment_list(post_id,created_at,id),
  KEY ix_comment_parent(parent_id,post_id),
  FOREIGN KEY(post_id) REFERENCES posts(id),
  FOREIGN KEY(author_id) REFERENCES users(id),
  FOREIGN KEY(parent_id,post_id) REFERENCES comments(id,post_id),
  CHECK (CHAR_LENGTH(body) BETWEEN 1 AND 2000)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE post_likes (
  post_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY(post_id,user_id),
  FOREIGN KEY(post_id) REFERENCES posts(id),
  FOREIGN KEY(user_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE post_favorites (
  post_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY(post_id,user_id),
  KEY ix_favorite_user(user_id,created_at,post_id),
  FOREIGN KEY(post_id) REFERENCES posts(id),
  FOREIGN KEY(user_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE goods (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  seller_id BIGINT UNSIGNED NOT NULL,
  category_id BIGINT UNSIGNED NOT NULL,
  campus_code VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  title VARCHAR(100) NOT NULL,
  description VARCHAR(5000) NOT NULL,
  brand VARCHAR(100) NULL,
  model VARCHAR(100) NULL,
  purpose VARCHAR(100) NULL,
  condition_code ENUM('new','like_new','good','fair') NOT NULL,
  price_cents INT UNSIGNED NOT NULL,
  location_text VARCHAR(100) NOT NULL DEFAULT '',
  attributes JSON NULL,
  state ENUM('on_sale','reserved','sold','off_shelf') NOT NULL DEFAULT 'on_sale',
  moderation ENUM('clear','restricted') NOT NULL DEFAULT 'clear',
  version INT UNSIGNED NOT NULL DEFAULT 1,
  deleted_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY ix_goods_filter(state,moderation,deleted_at,campus_code,category_id,price_cents),
  KEY ix_goods_seller(seller_id,created_at,id),
  KEY ix_goods_updated(updated_at,id),
  FOREIGN KEY(seller_id) REFERENCES users(id),
  FOREIGN KEY(category_id) REFERENCES goods_categories(id),
  FOREIGN KEY(campus_code) REFERENCES campuses(code),
  CHECK (price_cents <= 9999999),
  CHECK (CHAR_LENGTH(title) BETWEEN 2 AND 100),
  CHECK (CHAR_LENGTH(description) BETWEEN 1 AND 5000),
  CHECK (campus_code <> 'other' OR CHAR_LENGTH(location_text) BETWEEN 1 AND 100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE file_bindings (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  file_id BIGINT UNSIGNED NOT NULL,
  kind ENUM('avatar','post_image','post_pdf','goods_image') NOT NULL,
  avatar_user_id BIGINT UNSIGNED NULL,
  post_id BIGINT UNSIGNED NULL,
  goods_id BIGINT UNSIGNED NULL,
  position_no TINYINT UNSIGNED NOT NULL DEFAULT 1,
  UNIQUE KEY uq_binding_file(file_id),
  UNIQUE KEY uq_binding_avatar(avatar_user_id),
  UNIQUE KEY uq_binding_post(post_id,kind,position_no),
  UNIQUE KEY uq_binding_goods(goods_id,kind,position_no),
  FOREIGN KEY(file_id) REFERENCES files(id),
  FOREIGN KEY(avatar_user_id) REFERENCES users(id),
  FOREIGN KEY(post_id) REFERENCES posts(id),
  FOREIGN KEY(goods_id) REFERENCES goods(id),
  CHECK ((kind='avatar' AND avatar_user_id IS NOT NULL AND post_id IS NULL AND goods_id IS NULL AND position_no=1)
    OR (kind='post_image' AND post_id IS NOT NULL AND avatar_user_id IS NULL AND goods_id IS NULL AND position_no BETWEEN 1 AND 9)
    OR (kind='post_pdf' AND post_id IS NOT NULL AND avatar_user_id IS NULL AND goods_id IS NULL AND position_no BETWEEN 1 AND 2)
    OR (kind='goods_image' AND goods_id IS NOT NULL AND avatar_user_id IS NULL AND post_id IS NULL AND position_no BETWEEN 1 AND 6))
) ENGINE=InnoDB;

CREATE TABLE conversations (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_low_id BIGINT UNSIGNED NOT NULL,
  user_high_id BIGINT UNSIGNED NOT NULL,
  last_sequence BIGINT UNSIGNED NOT NULL DEFAULT 0,
  context_goods_id BIGINT UNSIGNED NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_conversation_pair(user_low_id,user_high_id),
  KEY ix_conversation_high(user_high_id,updated_at,id),
  KEY ix_conversation_low(user_low_id,updated_at,id),
  FOREIGN KEY(user_low_id) REFERENCES users(id),
  FOREIGN KEY(user_high_id) REFERENCES users(id),
  FOREIGN KEY(context_goods_id) REFERENCES goods(id),
  CHECK (user_low_id < user_high_id)
) ENGINE=InnoDB;

CREATE TABLE messages (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  conversation_id BIGINT UNSIGNED NOT NULL,
  sequence_no BIGINT UNSIGNED NOT NULL,
  sender_id BIGINT UNSIGNED NOT NULL,
  client_message_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  body VARCHAR(2000) NOT NULL,
  body_hash BINARY(32) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_message_retry(conversation_id,sender_id,client_message_id),
  UNIQUE KEY uq_message_sequence(conversation_id,sequence_no),
  FOREIGN KEY(conversation_id) REFERENCES conversations(id),
  FOREIGN KEY(sender_id) REFERENCES users(id),
  CHECK (CHAR_LENGTH(body) BETWEEN 1 AND 2000)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE conversation_reads (
  conversation_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  last_read_sequence BIGINT UNSIGNED NOT NULL DEFAULT 0,
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY(conversation_id,user_id),
  FOREIGN KEY(conversation_id) REFERENCES conversations(id),
  FOREIGN KEY(user_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE subscriptions (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  owner_id BIGINT UNSIGNED NOT NULL,
  name VARCHAR(100) NOT NULL,
  original_query VARCHAR(1000) NULL,
  conditions JSON NOT NULL,
  conditions_schema_version INT UNSIGNED NOT NULL DEFAULT 1,
  config_version INT UNSIGNED NOT NULL DEFAULT 1,
  interval_minutes SMALLINT UNSIGNED NOT NULL,
  state ENUM('active','paused','error','deleted') NOT NULL DEFAULT 'active',
  cursor_change_seq BIGINT UNSIGNED NOT NULL DEFAULT 0,
  needs_full_scan BOOLEAN NOT NULL DEFAULT TRUE,
  next_due_at DATETIME(6) NULL,
  last_checked_at DATETIME(6) NULL,
  cycle_key CHAR(36) CHARACTER SET ascii NULL,
  retry_count TINYINT UNSIGNED NOT NULL DEFAULT 0,
  lease_token CHAR(36) CHARACTER SET ascii NULL,
  lease_until DATETIME(6) NULL,
  last_error_code VARCHAR(64) CHARACTER SET ascii NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY ix_subscription_owner(owner_id,state,id),
  KEY ix_subscription_due(state,next_due_at,lease_until),
  FOREIGN KEY(owner_id) REFERENCES users(id),
  CHECK (interval_minutes BETWEEN 5 AND 1440),
  CHECK (retry_count BETWEEN 0 AND 3),
  CHECK (CHAR_LENGTH(name) BETWEEN 1 AND 100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE subscription_runs (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  subscription_id BIGINT UNSIGNED NOT NULL,
  cycle_key CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  attempt_no TINYINT UNSIGNED NOT NULL DEFAULT 0,
  config_version INT UNSIGNED NOT NULL,
  lease_token CHAR(36) CHARACTER SET ascii NOT NULL,
  upper_change_seq BIGINT UNSIGNED NOT NULL,
  state ENUM('running','succeeded','retry_wait','failed','cancelled') NOT NULL,
  error_code VARCHAR(64) CHARACTER SET ascii NULL,
  started_at DATETIME(6) NOT NULL,
  finished_at DATETIME(6) NULL,
  UNIQUE KEY uq_run_attempt(subscription_id,cycle_key,attempt_no),
  KEY ix_run_history(subscription_id,started_at,id),
  FOREIGN KEY(subscription_id) REFERENCES subscriptions(id),
  CHECK (attempt_no BETWEEN 0 AND 3)
) ENGINE=InnoDB;

CREATE TABLE scheduler_slots (
  slot_no TINYINT UNSIGNED PRIMARY KEY,
  subscription_id BIGINT UNSIGNED NULL,
  lease_token CHAR(36) CHARACTER SET ascii NULL,
  lease_until DATETIME(6) NULL,
  FOREIGN KEY(subscription_id) REFERENCES subscriptions(id),
  CHECK (slot_no IN (1,2))
) ENGINE=InnoDB;
INSERT INTO scheduler_slots(slot_no) VALUES (1),(2);

CREATE TABLE subscription_matches (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  subscription_id BIGINT UNSIGNED NOT NULL,
  goods_id BIGINT UNSIGNED NOT NULL,
  run_id BIGINT UNSIGNED NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_subscription_goods(subscription_id,goods_id),
  FOREIGN KEY(subscription_id) REFERENCES subscriptions(id),
  FOREIGN KEY(goods_id) REFERENCES goods(id),
  FOREIGN KEY(run_id) REFERENCES subscription_runs(id)
) ENGINE=InnoDB;

CREATE TABLE notifications (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  recipient_id BIGINT UNSIGNED NOT NULL,
  kind ENUM('goods_match','report_result','system') NOT NULL,
  match_id BIGINT UNSIGNED NULL,
  target_type ENUM('goods','post','report','announcement','none') NOT NULL,
  target_id BIGINT UNSIGNED NULL,
  safe_summary VARCHAR(300) NOT NULL,
  read_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_notification_match(match_id),
  KEY ix_notification_owner(recipient_id,read_at,created_at,id),
  FOREIGN KEY(recipient_id) REFERENCES users(id),
  FOREIGN KEY(match_id) REFERENCES subscription_matches(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE reports (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  reporter_id BIGINT UNSIGNED NOT NULL,
  target_type ENUM('post','comment','goods','message') NOT NULL,
  post_id BIGINT UNSIGNED NULL,
  comment_id BIGINT UNSIGNED NULL,
  goods_id BIGINT UNSIGNED NULL,
  message_id BIGINT UNSIGNED NULL,
  reason VARCHAR(1000) NOT NULL,
  necessary_context JSON NOT NULL,
  state ENUM('pending','resolved','dismissed') NOT NULL DEFAULT 'pending',
  resolved_by BIGINT UNSIGNED NULL,
  resolution VARCHAR(1000) NULL,
  version INT UNSIGNED NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  resolved_at DATETIME(6) NULL,
  KEY ix_report_owner(reporter_id,created_at,id),
  KEY ix_report_queue(state,created_at,id),
  FOREIGN KEY(reporter_id) REFERENCES users(id),
  FOREIGN KEY(post_id) REFERENCES posts(id),
  FOREIGN KEY(comment_id) REFERENCES comments(id),
  FOREIGN KEY(goods_id) REFERENCES goods(id),
  FOREIGN KEY(message_id) REFERENCES messages(id),
  FOREIGN KEY(resolved_by) REFERENCES users(id),
  CHECK (CHAR_LENGTH(reason) BETWEEN 1 AND 1000),
  CHECK ((target_type='post' AND post_id IS NOT NULL AND comment_id IS NULL AND goods_id IS NULL AND message_id IS NULL)
    OR (target_type='comment' AND comment_id IS NOT NULL AND post_id IS NULL AND goods_id IS NULL AND message_id IS NULL)
    OR (target_type='goods' AND goods_id IS NOT NULL AND post_id IS NULL AND comment_id IS NULL AND message_id IS NULL)
    OR (target_type='message' AND message_id IS NOT NULL AND post_id IS NULL AND comment_id IS NULL AND goods_id IS NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE announcements (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(100) NOT NULL,
  body_markdown MEDIUMTEXT NOT NULL,
  state ENUM('draft','published','retracted') NOT NULL DEFAULT 'draft',
  created_by BIGINT UNSIGNED NOT NULL,
  version INT UNSIGNED NOT NULL DEFAULT 1,
  published_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY ix_announcement_public(state,published_at,id),
  FOREIGN KEY(created_by) REFERENCES users(id),
  CHECK (CHAR_LENGTH(title) BETWEEN 2 AND 100),
  CHECK (CHAR_LENGTH(body_markdown) BETWEEN 1 AND 20000)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE audit_logs (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  actor_id BIGINT UNSIGNED NOT NULL,
  action VARCHAR(64) CHARACTER SET ascii NOT NULL,
  target_type VARCHAR(40) CHARACTER SET ascii NOT NULL,
  target_id BIGINT UNSIGNED NULL,
  reason VARCHAR(1000) NOT NULL,
  safe_changes JSON NOT NULL,
  request_id CHAR(36) CHARACTER SET ascii NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY ix_audit_target(target_type,target_id,created_at),
  FOREIGN KEY(actor_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE content_changes (
  change_seq BIGINT UNSIGNED PRIMARY KEY,
  kind ENUM('post','goods') NOT NULL,
  post_id BIGINT UNSIGNED NULL,
  goods_id BIGINT UNSIGNED NULL,
  source_version INT UNSIGNED NOT NULL,
  operation ENUM('upsert','remove') NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY ix_changes_goods(goods_id,change_seq),
  FOREIGN KEY(post_id) REFERENCES posts(id),
  FOREIGN KEY(goods_id) REFERENCES goods(id),
  CHECK ((kind='post' AND post_id IS NOT NULL AND goods_id IS NULL)
    OR (kind='goods' AND goods_id IS NOT NULL AND post_id IS NULL))
) ENGINE=InnoDB;

CREATE TABLE search_documents (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  kind ENUM('post','goods') NOT NULL,
  source_id BIGINT UNSIGNED NOT NULL,
  source_version INT UNSIGNED NOT NULL,
  content_hash BINARY(32) NOT NULL,
  embedding_model VARCHAR(100) CHARACTER SET ascii NULL,
  embedding_dimension INT UNSIGNED NULL,
  vector_key VARCHAR(180) CHARACTER SET ascii NULL,
  state ENUM('pending','ready','failed','removed') NOT NULL DEFAULT 'pending',
  indexed_at DATETIME(6) NULL,
  UNIQUE KEY uq_search_source(kind,source_id)
) ENGINE=InnoDB;

CREATE TABLE search_index_jobs (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  change_seq BIGINT UNSIGNED NOT NULL,
  state ENUM('pending','running','succeeded','failed') NOT NULL DEFAULT 'pending',
  retry_count INT UNSIGNED NOT NULL DEFAULT 0,
  next_due_at DATETIME(6) NOT NULL,
  lease_until DATETIME(6) NULL,
  error_code VARCHAR(64) CHARACTER SET ascii NULL,
  UNIQUE KEY uq_index_change(change_seq),
  KEY ix_index_due(state,next_due_at),
  FOREIGN KEY(change_seq) REFERENCES content_changes(change_seq)
) ENGINE=InnoDB;

CREATE TABLE outbox_events (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  recipient_id BIGINT UNSIGNED NOT NULL,
  event_type VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  source_id BIGINT UNSIGNED NOT NULL,
  safe_reference JSON NOT NULL,
  state ENUM('pending','sent','expired') NOT NULL DEFAULT 'pending',
  attempts INT UNSIGNED NOT NULL DEFAULT 0,
  next_due_at DATETIME(6) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_outbox_event(recipient_id,event_type,source_id),
  KEY ix_outbox_due(state,next_due_at),
  FOREIGN KEY(recipient_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE consumer_offsets (
  consumer_key VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  last_change_seq BIGINT UNSIGNED NOT NULL DEFAULT 0
) ENGINE=InnoDB;
INSERT INTO consumer_offsets VALUES ('search_index',0);

INSERT INTO boards(name,description) VALUES ('学习交流','课程、竞赛与学习经验'),('校园生活','校区生活与日常交流');
INSERT INTO campuses(code,name) VALUES ('shahe','沙河'),('xitucheng','西土城'),('other','其他');
INSERT INTO goods_categories(code,name) VALUES ('digital','数码设备'),('books','图书资料'),('daily','生活用品'),('other','其他');
