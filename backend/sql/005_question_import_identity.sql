BEGIN;

-- Running upgrade 0004 -> 0005

ALTER TABLE project_questions ADD COLUMN import_key TEXT;

ALTER TABLE project_questions ADD CONSTRAINT uq_project_questions_project_import_key UNIQUE (project_id, import_key);

UPDATE alembic_version SET version_num='0005' WHERE alembic_version.version_num = '0004';

COMMIT;

