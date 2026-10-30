BEGIN;

-- Running upgrade 0001 -> 0002

ALTER TABLE projects ALTER COLUMN cohort_id DROP NOT NULL;

ALTER TABLE projects ADD COLUMN background TEXT;

ALTER TABLE projects ADD COLUMN content_kind TEXT DEFAULT 'unspecified' NOT NULL;

ALTER TABLE projects ADD COLUMN content_notice TEXT;

ALTER TABLE projects ADD COLUMN content_tags JSON DEFAULT '[]' NOT NULL;

ALTER TABLE projects ADD CONSTRAINT ck_projects_valid_content_kind CHECK (content_kind IN ('unspecified', 'documented', 'reconstructed', 'fictional'));

ALTER TABLE journey_entries ADD COLUMN method_tags JSON DEFAULT '[]' NOT NULL;

ALTER TABLE project_resources ADD COLUMN usage_role TEXT DEFAULT 'output' NOT NULL;

ALTER TABLE project_resources ADD COLUMN caption TEXT;

ALTER TABLE project_resources ADD COLUMN alt_text TEXT;

ALTER TABLE project_resources ADD COLUMN source_name TEXT;

ALTER TABLE project_resources ADD COLUMN source_url TEXT;

ALTER TABLE project_resources ADD COLUMN original_url TEXT;

ALTER TABLE project_resources ADD COLUMN creator_credit TEXT;

ALTER TABLE project_resources ADD COLUMN original_activity TEXT;

ALTER TABLE project_resources ADD COLUMN provenance_note TEXT;

ALTER TABLE project_resources ADD COLUMN rights_status TEXT DEFAULT 'unconfirmed' NOT NULL;

ALTER TABLE project_resources ADD COLUMN rights_note TEXT;

ALTER TABLE project_resources ADD COLUMN file_size_bytes BIGINT;

ALTER TABLE project_resources ADD COLUMN width INTEGER;

ALTER TABLE project_resources ADD COLUMN height INTEGER;

ALTER TABLE project_resources ADD COLUMN duration_seconds NUMERIC(12, 3);

ALTER TABLE project_resources ADD CONSTRAINT ck_project_resources_valid_usage_role CHECK (usage_role IN ('output', 'process', 'reference'));

ALTER TABLE project_resources ADD CONSTRAINT ck_project_resources_valid_rights_status CHECK (rights_status IN ('unconfirmed', 'permission_confirmed', 'open_license'));

ALTER TABLE project_resources ADD CONSTRAINT ck_project_resources_nonnegative_size CHECK (file_size_bytes IS NULL OR file_size_bytes >= 0);

ALTER TABLE project_resources ADD CONSTRAINT ck_project_resources_positive_width CHECK (width IS NULL OR width > 0);

ALTER TABLE project_resources ADD CONSTRAINT ck_project_resources_positive_height CHECK (height IS NULL OR height > 0);

ALTER TABLE project_resources ADD CONSTRAINT ck_project_resources_nonnegative_duration CHECK (duration_seconds IS NULL OR duration_seconds >= 0);

CREATE TABLE project_questions (
    id UUID NOT NULL,
    project_id UUID NOT NULL,
    topic TEXT,
    question TEXT NOT NULL,
    sort_order INTEGER DEFAULT '0' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_project_questions PRIMARY KEY (id),
    CONSTRAINT fk_project_questions_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE,
    CONSTRAINT ck_project_questions_question_not_blank CHECK (length(trim(question)) > 0),
    CONSTRAINT ck_project_questions_nonnegative_sort_order CHECK (sort_order >= 0)
);

CREATE INDEX ix_project_questions_display ON project_questions (project_id, sort_order, id);

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0001';

COMMIT;

