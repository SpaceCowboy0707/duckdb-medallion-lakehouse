CREATE SCHEMA IF NOT EXISTS gold;

CREATE OR REPLACE TABLE gold.dim_date AS
WITH date_series AS (
    SELECT CAST(date_value AS DATE) AS date_key
    FROM generate_series(
        '2020-01-01'::TIMESTAMP,
        '2030-12-31'::TIMESTAMP,
        INTERVAL 1 DAY
    ) AS dates(date_value)
)

SELECT
    date_key,
    EXTRACT(YEAR FROM date_key)::INTEGER AS year,
    EXTRACT(QUARTER FROM date_key)::INTEGER AS quarter_number,
    'Q' || EXTRACT(QUARTER FROM date_key)::INTEGER AS quarter,
    EXTRACT(MONTH FROM date_key)::INTEGER AS month_number,
    STRFTIME(date_key, '%B') AS month_name,
    STRFTIME(date_key, '%b') AS month_short_name,
    EXTRACT(DAY FROM date_key)::INTEGER AS day,
    EXTRACT(DAYOFWEEK FROM date_key)::INTEGER AS day_of_week_number,
    STRFTIME(date_key, '%A') AS day_name,
    EXTRACT(WEEK FROM date_key)::INTEGER AS week_number,
    STRFTIME(date_key, '%Y-%m') AS year_month,
    CASE
        WHEN EXTRACT(DAYOFWEEK FROM date_key) IN (0, 6) THEN TRUE
        ELSE FALSE
    END AS is_weekend
FROM date_series
ORDER BY date_key;