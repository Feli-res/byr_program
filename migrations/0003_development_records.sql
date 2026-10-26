-- Independent development probe; never exposed when DEV_TOOLS_ENABLED=false.
CREATE TABLE dev_records (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  body VARCHAR(500) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT ck_dev_record_body CHECK (CHAR_LENGTH(TRIM(body)) BETWEEN 1 AND 500)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
