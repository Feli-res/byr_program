-- Account throttling survives Redis loss and service restart.
CREATE TABLE auth_login_limits (
  key_hash BINARY(32) PRIMARY KEY,
  failures INT UNSIGNED NOT NULL DEFAULT 0,
  window_started_at DATETIME(6) NOT NULL,
  locked_until DATETIME(6) NULL,
  KEY ix_login_limit_expiry(window_started_at)
) ENGINE=InnoDB;

