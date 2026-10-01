CREATE SCHEMA IF NOT EXISTS gold;

-- item master, one row per SKU -- column names match the original M3 query
CREATE OR REPLACE TABLE gold.dim_item AS
SELECT
    sku AS "SKU",
    brand_name AS "Brand Name",
    brand AS "Brand",
    style_name AS "STYLE NAME",
    style AS "STYLE",
    color_name AS "Color Name",
    year_season AS "YEAR/SEASON",
    size AS "Size",
    width AS "WIDTH",
    category AS "Category",
    sub_category AS "Sub Category",
    pair_per_unit AS "Pair per Unit",
    package AS "Package",
    upc AS "UPC",
    sales_price AS "SALES PRICE",
    purchase_price AS "PURCHASE PRICE",
    unit_of_measure AS "Unit of Measure"
FROM silver.item_master
ORDER BY sku;
