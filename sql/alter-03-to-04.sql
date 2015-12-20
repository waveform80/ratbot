CREATE OR REPLACE VIEW pages AS
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

CREATE OR REPLACE VIEW issues AS
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
