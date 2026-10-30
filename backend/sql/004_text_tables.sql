BEGIN;

-- Running upgrade 0003 -> 0004

ALTER TABLE projects ADD COLUMN short_title TEXT;

ALTER TABLE project_resources ADD COLUMN content_text TEXT;

ALTER TABLE project_resources ADD COLUMN structured_data JSON;

UPDATE alembic_version SET version_num='0004' WHERE alembic_version.version_num = '0003';

COMMIT;

