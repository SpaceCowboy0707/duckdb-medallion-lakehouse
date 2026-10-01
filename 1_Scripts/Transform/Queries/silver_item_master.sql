-- =============================================================================
-- Silver Layer: Item Master
-- =============================================================================
-- One row per SKU from bronze.m3_item_master (one company, see
-- 1_Scripts/Extract/Queries/m3_item_master.sql).
--
-- Bronze holds every column as text, exactly as M3 sent it -- M3 pads CHAR
-- columns with trailing spaces and the source query only trims some of them.
-- Everything is trimmed here, blanks become NULL, and the three numeric
-- columns are cast with a plain CAST: a value that isn't a number fails the
-- run instead of quietly turning into NULL.
--
-- Grain: if a SKU ever comes back more than once (the CSYTAB / MITAUN
-- lookups can in theory return several rows), the first row is kept --
-- preferring rows where those lookups actually found something. The pipeline
-- prints how many SKUs this affected.
-- YEAR/SEASON is taken as-is from MMCFI1, which holds the SKU's latest
-- season code.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS silver;

CREATE OR REPLACE TABLE silver.item_master AS

WITH trimmed AS (
    SELECT
        NULLIF(TRIM(sku), '') AS sku,
        NULLIF(TRIM(style), '') AS style,
        NULLIF(TRIM(style_name), '') AS style_name,
        NULLIF(TRIM(brand), '') AS brand,
        NULLIF(TRIM(brand_name), '') AS brand_name,
        NULLIF(TRIM(color_name), '') AS color_name,
        NULLIF(TRIM(year_season), '') AS year_season,
        NULLIF(TRIM(size), '') AS size,
        NULLIF(TRIM(width), '') AS width,
        NULLIF(TRIM(category), '') AS category,
        NULLIF(TRIM(sub_category), '') AS sub_category,
        CAST(NULLIF(TRIM(pair_per_unit), '') AS DECIMAL(18,4)) AS pair_per_unit,
        NULLIF(TRIM(package), '') AS package,
        -- kept as text so leading zeros survive
        NULLIF(TRIM(upc), '') AS upc,
        CAST(NULLIF(TRIM(sales_price), '') AS DECIMAL(17,2)) AS sales_price,
        CAST(NULLIF(TRIM(purchase_price), '') AS DECIMAL(17,2)) AS purchase_price,
        NULLIF(TRIM(unit_of_measure), '') AS unit_of_measure,
        _bronze_insert_ts,
        _source_file_name
    FROM bronze.m3_item_master
)

SELECT *
FROM trimmed
WHERE sku IS NOT NULL
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY sku
    ORDER BY
        brand_name NULLS LAST,
        pair_per_unit NULLS LAST,
        upc NULLS LAST
) = 1
ORDER BY sku;
