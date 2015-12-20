SET search_path = public, pg_catalog;

-- users
-------------------------------------------------------------------------------
-- Defines all authors and readers that have authenticated with the system.
-- No passwords are stored as all authentication activities are handled by
-- third party systems. The "admin" field indicates whether the user is an
-- administrator or not.
-------------------------------------------------------------------------------

CREATE TABLE users (
    user_id     varchar(200) NOT NULL,
    name        varchar(200) NOT NULL,
    admin       boolean DEFAULT false NOT NULL,
    markup      varchar(8) DEFAULT 'html' NOT NULL,
    description text DEFAULT '' NOT NULL,
    bitmap      varchar(200) DEFAULT NULL
);

ALTER TABLE users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON users TO ratbot;

-- comics_data
-------------------------------------------------------------------------------
-- Defines all comics available from the site. All comics must be associated
-- with a single author (this relationship distinguishes reader users from
-- author users).
-------------------------------------------------------------------------------

CREATE TABLE comics_data (
    comic_id     varchar(20) NOT NULL,
    title        varchar(200) NOT NULL,
    author_id    varchar(200) NOT NULL,
    license_id   varchar(50) NOT NULL,
    markup       varchar(8) DEFAULT 'html' NOT NULL,
    description  text DEFAULT '' NOT NULL,
    created      timestamp DEFAULT current_timestamp NOT NULL
);

ALTER TABLE comics_data
    ADD CONSTRAINT comics_pkey PRIMARY KEY (comic_id),
    ADD CONSTRAINT comics_title_key UNIQUE (title),
    ADD CONSTRAINT comics_author_id_fkey FOREIGN KEY (author_id)
        REFERENCES users(user_id) ON UPDATE CASCADE ON DELETE RESTRICT;

GRANT SELECT, INSERT, UPDATE, DELETE ON comics_data TO ratbot;

-- issues_data
-------------------------------------------------------------------------------
-- Defines issues of comics. Has a cascading delete relationship with the
-- comics table to ensure that if a comic is deleted, all issues belonging to
-- it are deleted too. The archive and pdf fields contain filenames for the
-- generated files which collect all pages of the issue.
-------------------------------------------------------------------------------

CREATE TABLE issues_data (
    comic_id      varchar(20) NOT NULL,
    issue_number  integer NOT NULL,
    title         varchar(500) NOT NULL,
    markup        varchar(8) DEFAULT 'html' NOT NULL,
    description   varchar DEFAULT '' NOT NULL,
    created       timestamp DEFAULT current_timestamp NOT NULL,
    archive       varchar(200) DEFAULT NULL,
    pdf           varchar(200) DEFAULT NULL
);

ALTER TABLE issues_data
    ADD CONSTRAINT issues_pkey PRIMARY KEY (comic_id, issue_number),
    ADD CONSTRAINT issues_comic_id_fkey FOREIGN KEY (comic_id)
        REFERENCES comics_data(comic_id) ON UPDATE CASCADE ON DELETE CASCADE,
    ADD CONSTRAINT issues_number_check CHECK (issue_number >= 1);

GRANT SELECT, INSERT, UPDATE, DELETE ON issues_data TO ratbot;

-- pages_data
-------------------------------------------------------------------------------
-- Defines all comic pages. Has a cascading delete relationship with issues
-- to ensure pages are deleted when an issue is deleted. The thumbnail, bitmap,
-- and vector fields hold filenames of the actual images associated with the
-- page. Pages with a NULL or future published date are considered unpublished.
-------------------------------------------------------------------------------

CREATE TABLE pages_data (
    comic_id     varchar(20) NOT NULL,
    issue_number integer NOT NULL,
    page_number  integer NOT NULL,
    created      timestamp DEFAULT current_timestamp NOT NULL,
    published    timestamp DEFAULT NULL,
    markup       varchar(8) DEFAULT 'html' NOT NULL,
    description  text DEFAULT '' NOT NULL,
    thumbnail    varchar(200) DEFAULT NULL,
    bitmap       varchar(200) DEFAULT NULL,
    vector       varchar(200) DEFAULT NULL
);

ALTER TABLE pages_data
    ADD CONSTRAINT pages_pkey PRIMARY KEY (comic_id, issue_number, page_number),
    ADD CONSTRAINT pages_comic_id_fkey FOREIGN KEY (comic_id, issue_number)
        REFERENCES issues_data(comic_id, issue_number) ON UPDATE CASCADE ON DELETE CASCADE,
    ADD CONSTRAINT pages_number_check CHECK (page_number >= 1);

GRANT SELECT, INSERT, UPDATE, DELETE ON pages_data TO ratbot;

-- pages
-------------------------------------------------------------------------------
-- Provides a view of the pages table which includes additional columns for
-- the next and prior page numbers.
-------------------------------------------------------------------------------

CREATE VIEW pages AS
SELECT
    p.comic_id,
    p.issue_number,
    p.page_number,
    p.created,
    p.published,
    p.markup,
    p.description,
    p.thumbnail,
    p.bitmap,
    p.vector,
    o.prior_page_number,
    o.next_page_number
FROM
    pages_data AS p
    LEFT JOIN (
        SELECT
            comic_id,
            issue_number,
            page_number,
            LAG(page_number) OVER (
                PARTITION BY comic_id, issue_number
                ORDER BY page_number
            ) AS prior_page_number,
            LEAD(page_number) OVER (
                PARTITION BY comic_id, issue_number
                ORDER BY page_number
            ) AS next_page_number
        FROM
            pages_data
        WHERE
            published IS NOT NULL
            AND published <= current_timestamp
    ) AS o
        ON p.comic_id = o.comic_id
        AND p.issue_number = o.issue_number
        AND p.page_number = o.page_number;

CREATE FUNCTION pages_redirect()
    RETURNS trigger
    LANGUAGE plpgsql
    VOLATILE
AS $$
BEGIN
    IF (TG_OP = 'INSERT') THEN
        INSERT INTO pages_data (
            comic_id,
            issue_number,
            page_number,
            created,
            published,
            markup,
            description,
            thumbnail,
            bitmap,
            vector
        )
        VALUES (
            NEW.comic_id,
            NEW.issue_number,
            NEW.page_number,
            COALESCE(NEW.created, CURRENT_TIMESTAMP),
            COALESCE(NEW.published, CURRENT_TIMESTAMP),
            NEW.markup,
            NEW.description,
            NEW.thumbnail,
            NEW.bitmap,
            NEW.vector
        );
        RETURN NEW;
    ELSIF (TG_OP = 'UPDATE') THEN
        UPDATE pages_data SET
            comic_id = NEW.comic_id,
            issue_number = NEW.issue_number,
            page_number = NEW.page_number,
            created = NEW.created,
            published = NEW.published,
            markup = NEW.markup,
            description = NEW.description,
            thumbnail = NEW.thumbnail,
            bitmap = NEW.bitmap,
            vector = NEW.vector
        WHERE
            comic_id = OLD.comic_id
            AND issue_number = OLD.issue_number
            AND page_number = OLD.page_number;
        IF NOT FOUND THEN
            RETURN NULL;
        ELSE
            RETURN NEW;
        END IF;
    ELSIF (TG_OP = 'DELETE') THEN
        DELETE FROM pages_data
        WHERE
            comic_id = OLD.comic_id
            AND issue_number = OLD.issue_number
            AND page_number = OLD.page_number;
        IF NOT FOUND THEN
            RETURN NULL;
        ELSE
            RETURN OLD;
        END IF;
    END IF;
END;
$$;

CREATE TRIGGER pages_redirect
    INSTEAD OF INSERT OR UPDATE OR DELETE ON pages
    FOR EACH ROW
    EXECUTE PROCEDURE pages_redirect();

GRANT SELECT, INSERT, UPDATE, DELETE ON pages TO ratbot;

-- issues
-------------------------------------------------------------------------------
-- Provides a view of the issues_data table with some extra columns detailing
-- the latest publication date of each issue, or NULL if no pages have been
-- published yet. Also calculates the first and last published page numbers,
-- along with the number of published pages in the issue.
-------------------------------------------------------------------------------

CREATE VIEW issues AS
SELECT
    i.comic_id,
    i.issue_number,
    i.title,
    i.markup,
    i.description,
    i.created,
    i.archive,
    i.pdf,
    o.published,
    o.prior_issue_number,
    o.next_issue_number,
    o.first_page_number,
    o.last_page_number,
    o.page_count
FROM
    issues_data AS i
    LEFT JOIN (
        SELECT
            comic_id,
            issue_number,
            published,
            first_page_number,
            last_page_number,
            page_count,
            LAG(issue_number) OVER (
                PARTITION BY comic_id
                ORDER BY issue_number
            ) AS prior_issue_number,
            LEAD(issue_number) OVER (
                PARTITION BY comic_id
                ORDER BY issue_number
            ) AS next_issue_number
        FROM (
            SELECT
                comic_id,
                issue_number,
                MAX(published) AS published,
                MIN(page_number) AS first_page_number,
                MAX(page_number) AS last_page_number,
                COUNT(page_number) AS page_count
            FROM
                pages_data
            WHERE
                published IS NOT NULL
                AND published <= current_timestamp
            GROUP BY
                comic_id,
                issue_number
        ) AS p
    ) AS o
        ON i.comic_id = o.comic_id
        AND i.issue_number = o.issue_number;

CREATE FUNCTION issues_redirect()
    RETURNS trigger
    LANGUAGE plpgsql
    VOLATILE
AS $$
BEGIN
    IF (TG_OP = 'INSERT') THEN
        INSERT INTO issues_data (
            comic_id,
            issue_number,
            title,
            markup,
            description,
            created,
            archive,
            pdf
        )
        VALUES (
            NEW.comic_id,
            NEW.issue_number,
            NEW.title,
            NEW.markup,
            NEW.description,
            COALESCE(NEW.created, CURRENT_TIMESTAMP),
            NEW.archive,
            NEW.pdf
        );
        RETURN NEW;
    ELSIF (TG_OP = 'UPDATE') THEN
        UPDATE issues_data SET
            comic_id = NEW.comic_id,
            issue_number = NEW.issue_number,
            title = NEW.title,
            markup = NEW.markup,
            description = NEW.description,
            created = NEW.created,
            archive = NEW.archive,
            pdf = NEW.pdf
        WHERE
            comic_id = OLD.comic_id
            AND issue_number = OLD.issue_number;
        IF NOT FOUND THEN
            RETURN NULL;
        ELSE
            RETURN NEW;
        END IF;
    ELSIF (TG_OP = 'DELETE') THEN
        DELETE FROM issues_data
        WHERE
            comic_id = OLD.comic_id
            AND issue_number = OLD.issue_number;
        IF NOT FOUND THEN
            RETURN NULL;
        ELSE
            RETURN OLD;
        END IF;
    END IF;
END;
$$;

CREATE TRIGGER issues_redirect
    INSTEAD OF INSERT OR UPDATE OR DELETE ON issues
    FOR EACH ROW
    EXECUTE PROCEDURE issues_redirect();

GRANT SELECT, INSERT, UPDATE, DELETE ON issues TO ratbot;

-- comics
-------------------------------------------------------------------------------
-- Provides a filtered view of the comics_data table with extra columns
-- detailing the latest published issue number, and the first page of that
-- issue. This view does NOT exclude comics with no published issues;
-- latest_issue will simply be NULL for such entries.
-------------------------------------------------------------------------------

CREATE VIEW comics AS
SELECT
    c.comic_id,
    c.title,
    c.author_id,
    c.license_id,
    c.markup,
    c.description,
    c.created,
    MIN(p.issue_number)            AS first_issue_number,
    MAX(p.issue_number)            AS last_issue_number,
    COUNT(DISTINCT p.issue_number) AS issue_count
FROM
    comics_data c
    LEFT JOIN pages_data p
        ON c.comic_id = p.comic_id
WHERE
    p.published IS NULL
    OR p.published <= current_timestamp
GROUP BY
    c.comic_id,
    c.title,
    c.author_id,
    c.license_id,
    c.markup,
    c.description,
    c.created;

CREATE FUNCTION comics_redirect()
    RETURNS trigger
    LANGUAGE plpgsql
    VOLATILE
AS $$
BEGIN
    IF (TG_OP = 'INSERT') THEN
        INSERT INTO comics_data (
            comic_id,
            title,
            author_id,
            license_id,
            markup,
            description,
            created
        )
        VALUES (
            NEW.comic_id,
            NEW.title,
            NEW.author_id,
            NEW.license_id,
            NEW.markup,
            NEW.description,
            COALESCE(NEW.created, CURRENT_TIMESTAMP)
        );
        RETURN NEW;
    ELSIF (TG_OP = 'UPDATE') THEN
        UPDATE comics_data SET
            comic_id = NEW.comic_id,
            title = NEW.title,
            author_id = NEW.author_id,
            license_id = NEW.license_id,
            markup = NEW.markup,
            description = NEW.description,
            created = NEW.created
        WHERE
            comic_id = OLD.comic_id;
        IF NOT FOUND THEN
            RETURN NULL;
        ELSE
            RETURN NEW;
        END IF;
    ELSIF (TG_OP = 'DELETE') THEN
        DELETE FROM comics_data
        WHERE
            comic_id = OLD.comic_id;
        IF NOT FOUND THEN
            RETURN NULL;
        ELSE
            RETURN OLD;
        END IF;
    END IF;
END;
$$;

CREATE TRIGGER comics_redirect
    INSTEAD OF INSERT OR UPDATE OR DELETE ON comics
    FOR EACH ROW
    EXECUTE PROCEDURE comics_redirect();

GRANT SELECT, INSERT, UPDATE, DELETE ON comics TO ratbot;

-- front_pages
-------------------------------------------------------------------------------
-- Defines the set of pages that will appear on the front page of the site.
-- This consists of the most recently published pages from the blog and
-- non-blog comics, except that for non-blog comics, the first page of the last
-- published issue is returned.
-------------------------------------------------------------------------------

CREATE VIEW front_pages AS
WITH latest_issues AS (
    SELECT
        comic_id,
        issue_number,
        MIN(page_number) AS first_page,
        MAX(published) AS last_published
    FROM
        pages_data
    WHERE
        published IS NOT NULL
        AND published <= current_timestamp
    GROUP BY
        comic_id,
        issue_number
),
blog_pages AS (
    SELECT
        p.comic_id,
        p.issue_number,
        p.page_number,
        p.published
    FROM
        latest_issues l
        JOIN pages_data p
            ON l.comic_id = p.comic_id
            AND l.issue_number = p.issue_number
            AND l.last_published = p.published
    WHERE
        p.comic_id = 'blog'
),
non_blog_pages AS (
    SELECT
        p.comic_id,
        p.issue_number,
        l.first_page AS page_number,
        l.last_published AS published
    FROM
        latest_issues l
        JOIN pages_data p
            ON l.comic_id = p.comic_id
            AND l.issue_number = p.issue_number
            AND l.first_page = p.page_number
    WHERE
        p.comic_id <> 'blog'
)
SELECT * FROM blog_pages
UNION ALL
SELECT * FROM non_blog_pages;

GRANT SELECT ON front_pages TO ratbot;

