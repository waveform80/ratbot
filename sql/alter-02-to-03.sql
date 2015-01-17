DROP VIEW comics;
DROP FUNCTION comics_redirect();

ALTER TABLE comics_data
    ADD COLUMN license_id varchar(50) DEFAULT 'notspecified' NOT NULL;

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
    p.published IS NOT NULL
    AND p.published <= current_timestamp
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
            NEW.created
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

