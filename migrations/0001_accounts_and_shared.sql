-- 4.3 design converted to versioned application migrations.
SET NAMES utf8mb4;
SET SESSION time_zone = '+00:00';

CREATE TABLE system_locks (
  lock_key VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY
) ENGINE=InnoDB;
INSERT INTO system_locks VALUES ('administrators');

CREATE TABLE system_counters (
  counter_key VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  counter_value BIGINT UNSIGNED NOT NULL DEFAULT 0
) ENGINE=InnoDB;
INSERT INTO system_counters VALUES ('content_changes',0);

CREATE TABLE users (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  account_norm VARCHAR(24) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  password_hash VARCHAR(255) CHARACTER SET ascii NOT NULL,
  nickname VARCHAR(20) NOT NULL,
  bio VARCHAR(300) NOT NULL DEFAULT '',
  role ENUM('user','moderator','admin') NOT NULL DEFAULT 'user',
  status ENUM('active','banned') NOT NULL DEFAULT 'active',
  password_reset_required BOOLEAN NOT NULL DEFAULT FALSE,
  used_file_bytes BIGINT UNSIGNED NOT NULL DEFAULT 0,
  version INT UNSIGNED NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_user_account(account_norm),
  CHECK (CHAR_LENGTH(account_norm) BETWEEN 4 AND 24),
  CHECK (CHAR_LENGTH(nickname) BETWEEN 2 AND 20),
  CHECK (used_file_bytes <= 209715200)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE sessions (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT UNSIGNED NOT NULL,
  token_hash BINARY(32) NOT NULL,
  expires_at DATETIME(6) NOT NULL,
  revoked_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_session_hash(token_hash),
  KEY ix_session_user(user_id,revoked_at,expires_at),
  FOREIGN KEY(user_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE password_resets (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT UNSIGNED NOT NULL,
  issued_by BIGINT UNSIGNED NOT NULL,
  credential_hash BINARY(32) NOT NULL,
  expires_at DATETIME(6) NOT NULL,
  consumed_at DATETIME(6) NULL,
  revoked_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_reset_hash(credential_hash),
  KEY ix_reset_user(user_id,expires_at),
  FOREIGN KEY(user_id) REFERENCES users(id),
  FOREIGN KEY(issued_by) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE boards (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(30) NOT NULL,
  description VARCHAR(300) NOT NULL DEFAULT '',
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  version INT UNSIGNED NOT NULL DEFAULT 1,
  UNIQUE KEY uq_board_name(name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE board_moderators (
  board_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  PRIMARY KEY(board_id,user_id),
  KEY ix_moderator_user(user_id,board_id),
  FOREIGN KEY(board_id) REFERENCES boards(id),
  FOREIGN KEY(user_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE goods_categories (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(30) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  name VARCHAR(30) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE KEY uq_category_code(code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE campuses (
  code VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  name VARCHAR(20) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE files (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  owner_id BIGINT UNSIGNED NOT NULL,
  purpose ENUM('avatar','post_image','post_pdf','goods_image') NOT NULL,
  storage_key VARCHAR(180) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  original_name VARCHAR(255) NOT NULL,
  mime_type VARCHAR(80) CHARACTER SET ascii NOT NULL,
  size_bytes BIGINT UNSIGNED NOT NULL,
  sha256 BINARY(32) NOT NULL,
  width_px INT UNSIGNED NULL,
  height_px INT UNSIGNED NULL,
  state ENUM('staged','attached','cleanup_pending','cleaned') NOT NULL DEFAULT 'staged',
  expires_at DATETIME(6) NULL,
  cleaned_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_file_storage(storage_key),
  KEY ix_file_owner(owner_id,state),
  KEY ix_file_cleanup(state,expires_at),
  FOREIGN KEY(owner_id) REFERENCES users(id),
  CHECK (size_bytes BETWEEN 1 AND 10485760),
  CHECK ((purpose='avatar' AND mime_type IN ('image/jpeg','image/png','image/webp') AND size_bytes<=2097152)
    OR (purpose IN ('post_image','goods_image') AND mime_type IN ('image/jpeg','image/png','image/webp') AND size_bytes<=5242880)
    OR (purpose='post_pdf' AND mime_type='application/pdf' AND size_bytes<=10485760))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

