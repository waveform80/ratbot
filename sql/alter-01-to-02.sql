ALTER TABLE users
    RENAME COLUMN id TO user_id;

ALTER TABLE comics
    RENAME COLUMN id TO comic_id;

ALTER TABLE issues
    RENAME COLUMN number TO issue_number;

ALTER TABLE pages
    RENAME COLUMN number TO page_number;

ALTER TABLE comics
    RENAME TO comics_data;

ALTER TABLE issues
    RENAME TO issues_data;

ALTER TABLE pages
    RENAME TO pages_data;

CREATE VIEW pages AS
WITH page_ordering AS (
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
)
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
    pages_data p
    LEFT JOIN page_ordering o
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
            NEW.created,
            NEW.published,
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

CREATE VIEW issues AS
WITH published_issues AS (
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
),
issue_ordering AS (
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
    FROM
        published_issues
)
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
    issues_data i
    LEFT JOIN issue_ordering o
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
            NEW.created,
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

CREATE VIEW comics AS
SELECT
    c.comic_id,
    c.title,
    c.author_id,
    c.markup,
    c.description,
    c.created,
    MIN(p.issue_number) AS first_issue_number,
    MAX(p.issue_number) AS last_issue_number,
    COUNT(DISTINCT p.issue_number) AS issue_count
FROM
    comics_data c
    LEFT JOIN pages_data p
        ON c.comic_id = p.comic_id
WHERE
    p.published IS NOT NULL
    AND p.published <= current_timestamp
GROUP BY
    c.comic_id,
    c.title,
    c.author_id,
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
            markup,
            description,
            created
        )
        VALUES (
            NEW.comic_id,
            NEW.title,
            NEW.author_id,
            NEW.markup,
            NEW.description,
            NEW.created
        );
        RETURN NEW;
    ELSIF (TG_OP = 'UPDATE') THEN
        UPDATE comics_data SET
            comic_id = NEW.comic_id,
            title = NEW.title,
            author_id = NEW.author_id,
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

