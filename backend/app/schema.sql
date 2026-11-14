-- Relational model for the harvested OpenAlex works.
--
-- Normalised tables (authors, institutions, authorships, concepts, topics) support the
-- analysis queries and keep entities de-duplicated across works. The complete API
-- response is kept in works.raw (JSONB) so nothing is lost and the search index can be
-- rebuilt from the database without calling OpenAlex again.
--
-- Every statement is idempotent so the schema can be applied on each start-up.

CREATE TABLE IF NOT EXISTS works (
    id               text PRIMARY KEY,            -- OpenAlex short id, e.g. W4414950448
    doi              text,                        -- bare DOI, e.g. 10.1101/2025.10.06.25337235
    title            text,
    abstract         text,                        -- reconstructed from abstract_inverted_index
    publication_date date,
    publication_year integer,
    type             text,
    language         text,
    cited_by_count   integer NOT NULL DEFAULT 0,
    fwci             double precision,
    is_oa            boolean,
    oa_status        text,
    oa_url           text,
    source_name      text,
    landing_page_url text,
    harvest_rank     integer,                     -- position in the OpenAlex relevance ordering
    raw              jsonb NOT NULL,
    harvested_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS authors (
    id           text PRIMARY KEY,                -- e.g. A5034675830
    display_name text NOT NULL,
    orcid        text
);

CREATE TABLE IF NOT EXISTS institutions (
    id           text PRIMARY KEY,                -- e.g. I40120149
    display_name text NOT NULL,
    ror          text,
    country_code text,
    type         text
);

-- One row per author slot on a work (the same person can in rare cases appear twice).
CREATE TABLE IF NOT EXISTS authorships (
    work_id          text    NOT NULL REFERENCES works (id) ON DELETE CASCADE,
    author_position  integer NOT NULL,            -- 0-based order in the author list
    author_id        text REFERENCES authors (id),
    author_role      text,                        -- first / middle / last
    raw_author_name  text,
    is_corresponding boolean NOT NULL DEFAULT false,
    raw_affiliations text[]  NOT NULL DEFAULT '{}',
    PRIMARY KEY (work_id, author_position)
);
CREATE INDEX IF NOT EXISTS authorships_author_idx ON authorships (author_id);

CREATE TABLE IF NOT EXISTS authorship_institutions (
    work_id         text    NOT NULL,
    author_position integer NOT NULL,
    institution_id  text    NOT NULL REFERENCES institutions (id),
    PRIMARY KEY (work_id, author_position, institution_id),
    FOREIGN KEY (work_id, author_position)
        REFERENCES authorships (work_id, author_position) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS authorship_institutions_inst_idx
    ON authorship_institutions (institution_id);

-- OpenAlex "countries" per authorship: derived from institutions and raw affiliation strings.
CREATE TABLE IF NOT EXISTS authorship_countries (
    work_id         text    NOT NULL,
    author_position integer NOT NULL,
    country_code    text    NOT NULL,
    PRIMARY KEY (work_id, author_position, country_code),
    FOREIGN KEY (work_id, author_position)
        REFERENCES authorships (work_id, author_position) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS concepts (
    id           text PRIMARY KEY,                -- e.g. C132651083
    display_name text NOT NULL,
    level        integer,
    wikidata     text
);

CREATE TABLE IF NOT EXISTS work_concepts (
    work_id    text NOT NULL REFERENCES works (id) ON DELETE CASCADE,
    concept_id text NOT NULL REFERENCES concepts (id),
    score      real,
    PRIMARY KEY (work_id, concept_id)
);

CREATE TABLE IF NOT EXISTS topics (
    id           text PRIMARY KEY,                -- e.g. T10166
    display_name text NOT NULL,
    subfield     text,
    field        text,
    domain       text
);

CREATE TABLE IF NOT EXISTS work_topics (
    work_id    text    NOT NULL REFERENCES works (id) ON DELETE CASCADE,
    topic_id   text    NOT NULL REFERENCES topics (id),
    score      real,
    is_primary boolean NOT NULL DEFAULT false,
    PRIMARY KEY (work_id, topic_id)
);

CREATE TABLE IF NOT EXISTS harvest_runs (
    id             serial PRIMARY KEY,
    source         text        NOT NULL,          -- 'api' or 'snapshot'
    query          text,
    openalex_total integer,                       -- size of the full OpenAlex result set
    works_stored   integer     NOT NULL,
    started_at     timestamptz NOT NULL,
    finished_at    timestamptz NOT NULL DEFAULT now()
);
