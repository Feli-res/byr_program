CREATE TABLE report_ai_jobs (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 report_id BIGINT UNSIGNED NOT NULL,
 post_version INT UNSIGNED NOT NULL,
 state ENUM('pending','running','completed','failed','skipped','unknown') NOT NULL DEFAULT 'pending',
 result JSON NULL,
 started_at DATETIME(6) NULL,
 finished_at DATETIME(6) NULL,
 UNIQUE KEY uq_report_ai_report(report_id),
 KEY ix_report_ai_state(state,id),
 FOREIGN KEY(report_id) REFERENCES reports(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
