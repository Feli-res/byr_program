-- Keep revocation reasons with the session so live connections can explain closure.
ALTER TABLE sessions ADD COLUMN revocation_reason
  ENUM('logout','password_changed','password_reset','banned') NULL AFTER revoked_at;
