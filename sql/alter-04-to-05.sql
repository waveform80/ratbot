CREATE OR REPLACE FUNCTION comics_redirect()
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

CREATE OR REPLACE FUNCTION issues_redirect()
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

CREATE OR REPLACE FUNCTION pages_redirect()
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


