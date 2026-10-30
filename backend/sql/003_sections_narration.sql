BEGIN;

-- Running upgrade 0002 -> 0003

ALTER TABLE projects ADD COLUMN opening_question TEXT;

ALTER TABLE projects ADD COLUMN dataset_key TEXT;

ALTER TABLE projects ADD COLUMN dataset_version INTEGER;

ALTER TABLE projects ADD COLUMN dataset_digest TEXT;

ALTER TABLE projects ADD COLUMN dataset_imported_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE journey_entries ADD COLUMN import_key TEXT;

ALTER TABLE journey_entries ADD CONSTRAINT uq_journey_entries_project_import_key UNIQUE (project_id, import_key);

ALTER TABLE project_resources ADD COLUMN import_key TEXT;

ALTER TABLE project_resources ADD COLUMN transcript TEXT;

ALTER TABLE project_resources ADD COLUMN is_ai_generated BOOLEAN DEFAULT false NOT NULL;

ALTER TABLE project_resources ADD COLUMN generation_note TEXT;

ALTER TABLE project_resources ADD COLUMN sha256 TEXT;

ALTER TABLE project_resources ADD CONSTRAINT uq_project_resources_project_identity UNIQUE (project_id, id);

ALTER TABLE project_resources ADD CONSTRAINT uq_project_resources_project_import_key UNIQUE (project_id, import_key);

CREATE TABLE project_sections (
    id UUID NOT NULL,
    project_id UUID NOT NULL,
    key TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    sort_order INTEGER DEFAULT '0' NOT NULL,
    journey_entry_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_project_sections PRIMARY KEY (id),
    CONSTRAINT uq_project_sections_project_identity UNIQUE (project_id, id),
    CONSTRAINT uq_project_sections_project_key UNIQUE (project_id, key),
    CONSTRAINT fk_project_sections_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE,
    CONSTRAINT fk_project_sections_same_project_journey FOREIGN KEY(project_id, journey_entry_id) REFERENCES journey_entries (project_id, id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT ck_project_sections_valid_kind CHECK (kind IN ('opening', 'journey', 'output', 'learning', 'other')),
    CONSTRAINT ck_project_sections_journey_required CHECK (kind != 'journey' OR journey_entry_id IS NOT NULL),
    CONSTRAINT ck_project_sections_key_not_blank CHECK (length(trim(key)) > 0),
    CONSTRAINT ck_project_sections_title_not_blank CHECK (length(trim(title)) > 0),
    CONSTRAINT ck_project_sections_nonnegative_sort_order CHECK (sort_order >= 0)
);

CREATE INDEX ix_project_sections_display ON project_sections (project_id, sort_order, id);

CREATE TABLE section_resources (
    section_id UUID NOT NULL,
    resource_id UUID NOT NULL,
    project_id UUID NOT NULL,
    role TEXT NOT NULL,
    is_optional BOOLEAN DEFAULT false NOT NULL,
    sort_order INTEGER DEFAULT '0' NOT NULL,
    CONSTRAINT pk_section_resources PRIMARY KEY (section_id, resource_id),
    CONSTRAINT fk_section_resources_same_project_section FOREIGN KEY(project_id, section_id) REFERENCES project_sections (project_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_section_resources_same_project_resource FOREIGN KEY(project_id, resource_id) REFERENCES project_resources (project_id, id) ON DELETE CASCADE,
    CONSTRAINT ck_section_resources_valid_role CHECK (role IN ('illustration', 'narration', 'attachment')),
    CONSTRAINT ck_section_resources_nonnegative_sort_order CHECK (sort_order >= 0)
);

CREATE INDEX ix_section_resources_resource ON section_resources (project_id, resource_id);

UPDATE alembic_version SET version_num='0003' WHERE alembic_version.version_num = '0002';

COMMIT;

