CREATE OR REPLACE VIEW comics AS
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


