-- ============================================================
-- PetCare MySQL read-only account
-- Run as root once:  mysql -u root -p < create_readonly_user.sql
--
-- !!! Password is a PLACEHOLDER. Replace __READONLY_PASSWORD__
-- before executing, e.g.:
--     SET @pass = 'your-strong-password';
-- or edit the line below.
-- ============================================================

CREATE USER IF NOT EXISTS 'petcare_reader'@'localhost' IDENTIFIED BY '__READONLY_PASSWORD__';

-- read-only access to the petcare database only
GRANT SELECT ON petcare_db.* TO 'petcare_reader'@'localhost';

-- explicitly deny (MySQL has no DENY, so we simply do NOT grant):
--   INSERT / UPDATE / DELETE / CREATE / DROP / ALTER / FILE / SUPER ...
-- The account only ever gets SELECT, so all write/privilege operations fail.

FLUSH PRIVILEGES;

-- verify (should only show SELECT):
--   SHOW GRANTS FOR 'petcare_reader'@'localhost';
