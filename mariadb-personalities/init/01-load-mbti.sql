-- Loads MBTI personality labels into user_personalities.mbti_labels.
-- Runs automatically on first container init (when the data volume is empty).
-- The CSV is mounted read-only at /var/lib/mysql-files/data, which is MariaDB's
-- default secure_file_priv directory, so the server-side LOAD DATA INFILE below
-- is permitted. Schema matches mariadb-personalities/README.md.
USE user_personalities;

CREATE TABLE IF NOT EXISTS mbti_labels (
  id               BIGINT      PRIMARY KEY,  -- Twitter user ID
  mbti_personality VARCHAR(10),              -- MBTI type, e.g. infp / entj
  pers_id          INT                       -- numeric personality id
);

LOAD DATA INFILE '/var/lib/mysql-files/data/mbti_labels.csv'
  INTO TABLE mbti_labels
  FIELDS TERMINATED BY ','
  LINES TERMINATED BY '\n'
  IGNORE 1 LINES
  (id, mbti_personality, pers_id);
