BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE TABLE cohorts (
    name TEXT NOT NULL,
    year SMALLINT NOT NULL,
    description TEXT,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    CONSTRAINT pk_cohorts PRIMARY KEY (id),
    CONSTRAINT ck_cohorts_name_not_blank CHECK (length(trim(name)) > 0),
    CONSTRAINT ck_cohorts_positive_year CHECK (year >= 1),
    CONSTRAINT uq_cohorts_name UNIQUE (name)
);

CREATE TABLE resource_types (
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    CONSTRAINT pk_resource_types PRIMARY KEY (id),
    CONSTRAINT ck_resource_types_code_not_blank CHECK (length(trim(code)) > 0),
    CONSTRAINT ck_resource_types_name_not_blank CHECK (length(trim(name)) > 0),
    CONSTRAINT uq_resource_types_code UNIQUE (code)
);

CREATE TABLE themes (
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    description TEXT,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    CONSTRAINT pk_themes PRIMARY KEY (id),
    CONSTRAINT ck_themes_name_not_blank CHECK (length(trim(name)) > 0),
    CONSTRAINT ck_themes_slug_not_blank CHECK (length(trim(slug)) > 0),
    CONSTRAINT uq_themes_name UNIQUE (name),
    CONSTRAINT uq_themes_slug UNIQUE (slug)
);

CREATE TABLE projects (
    cohort_id UUID NOT NULL,
    title TEXT NOT NULL,
    slug TEXT NOT NULL,
    summary TEXT NOT NULL,
    location TEXT,
    team_name TEXT,
    cover_url TEXT,
    research_question TEXT NOT NULL,
    research_methods TEXT DEFAULT '' NOT NULL,
    learning_outcomes TEXT DEFAULT '' NOT NULL,
    practical_tips TEXT DEFAULT '' NOT NULL,
    status TEXT DEFAULT 'draft' NOT NULL,
    published_at TIMESTAMP WITH TIME ZONE,
    is_demo BOOLEAN DEFAULT true NOT NULL,
    is_featured BOOLEAN DEFAULT false NOT NULL,
    featured_reason TEXT,
    featured_rank INTEGER DEFAULT '0' NOT NULL,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    CONSTRAINT pk_projects PRIMARY KEY (id),
    CONSTRAINT ck_projects_published_at_required CHECK (status != 'published' OR published_at IS NOT NULL),
    CONSTRAINT ck_projects_valid_status CHECK (status IN ('draft', 'published', 'archived')),
    CONSTRAINT ck_projects_nonnegative_featured_rank CHECK (featured_rank >= 0),
    CONSTRAINT ck_projects_slug_not_blank CHECK (length(trim(slug)) > 0),
    CONSTRAINT ck_projects_title_not_blank CHECK (length(trim(title)) > 0),
    CONSTRAINT fk_projects_cohort_id_cohorts FOREIGN KEY(cohort_id) REFERENCES cohorts (id) ON DELETE RESTRICT,
    CONSTRAINT uq_projects_slug UNIQUE (slug)
);

CREATE INDEX ix_projects_featured ON projects (featured_rank DESC, published_at DESC, id DESC) WHERE status = 'published' AND is_featured = true;

CREATE INDEX ix_projects_public_cohort ON projects (cohort_id, published_at DESC, id DESC) WHERE status = 'published';

CREATE INDEX ix_projects_public_published ON projects (published_at DESC, id DESC) WHERE status = 'published';

CREATE TABLE journey_entries (
    project_id UUID NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    challenges TEXT,
    responses TEXT,
    reflection TEXT,
    occurred_on DATE,
    sort_order INTEGER DEFAULT '0' NOT NULL,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    CONSTRAINT pk_journey_entries PRIMARY KEY (id),
    CONSTRAINT ck_journey_entries_title_not_blank CHECK (length(trim(title)) > 0),
    CONSTRAINT ck_journey_entries_nonnegative_sort_order CHECK (sort_order >= 0),
    CONSTRAINT fk_journey_entries_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE,
    CONSTRAINT uq_journey_entries_project_id UNIQUE (project_id, id)
);

CREATE INDEX ix_journey_entries_display ON journey_entries (project_id, sort_order, id);

CREATE TABLE project_impacts (
    project_id UUID NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    evidence_reference TEXT,
    evidence_url TEXT,
    metric_name TEXT,
    metric_value NUMERIC,
    metric_unit TEXT,
    metric_scope TEXT,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    CONSTRAINT pk_project_impacts PRIMARY KEY (id),
    CONSTRAINT ck_project_impacts_valid_category CHECK (category IN ('educational', 'social')),
    CONSTRAINT ck_project_impacts_complete_metric CHECK ((metric_name IS NULL AND metric_value IS NULL AND metric_unit IS NULL AND metric_scope IS NULL) OR (metric_name IS NOT NULL AND metric_value IS NOT NULL AND metric_unit IS NOT NULL AND metric_scope IS NOT NULL AND length(trim(metric_name)) > 0 AND length(trim(metric_unit)) > 0 AND length(trim(metric_scope)) > 0)),
    CONSTRAINT ck_project_impacts_title_not_blank CHECK (length(trim(title)) > 0),
    CONSTRAINT fk_project_impacts_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE INDEX ix_project_impacts_project_id ON project_impacts (project_id);

CREATE TABLE project_members (
    project_id UUID NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    school_name TEXT,
    sort_order INTEGER DEFAULT '0' NOT NULL,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    CONSTRAINT pk_project_members PRIMARY KEY (id),
    CONSTRAINT ck_project_members_display_name_not_blank CHECK (length(trim(display_name)) > 0),
    CONSTRAINT ck_project_members_role_not_blank CHECK (length(trim(role)) > 0),
    CONSTRAINT ck_project_members_nonnegative_sort_order CHECK (sort_order >= 0),
    CONSTRAINT fk_project_members_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE INDEX ix_project_members_display ON project_members (project_id, sort_order, id);

CREATE TABLE project_themes (
    project_id UUID NOT NULL,
    theme_id UUID NOT NULL,
    CONSTRAINT pk_project_themes PRIMARY KEY (project_id, theme_id),
    CONSTRAINT fk_project_themes_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE,
    CONSTRAINT fk_project_themes_theme_id_themes FOREIGN KEY(theme_id) REFERENCES themes (id) ON DELETE RESTRICT
);

CREATE INDEX ix_project_themes_theme_id ON project_themes (theme_id, project_id);

CREATE TABLE project_resources (
    project_id UUID NOT NULL,
    journey_entry_id UUID,
    resource_type_id UUID NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    resource_url TEXT NOT NULL,
    preview_url TEXT,
    mime_type TEXT,
    sort_order INTEGER DEFAULT '0' NOT NULL,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    CONSTRAINT pk_project_resources PRIMARY KEY (id),
    CONSTRAINT ck_project_resources_url_not_blank CHECK (length(trim(resource_url)) > 0),
    CONSTRAINT ck_project_resources_title_not_blank CHECK (length(trim(title)) > 0),
    CONSTRAINT ck_project_resources_nonnegative_sort_order CHECK (sort_order >= 0),
    CONSTRAINT fk_project_resources_same_project_journey FOREIGN KEY(project_id, journey_entry_id) REFERENCES journey_entries (project_id, id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_project_resources_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE,
    CONSTRAINT fk_project_resources_resource_type_id_resource_types FOREIGN KEY(resource_type_id) REFERENCES resource_types (id) ON DELETE RESTRICT
);

CREATE INDEX ix_project_resources_display ON project_resources (project_id, sort_order, id);

CREATE INDEX ix_project_resources_journey ON project_resources (project_id, journey_entry_id);

CREATE INDEX ix_project_resources_resource_type_id ON project_resources (resource_type_id);

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

COMMIT;

