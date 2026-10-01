CREATE SCHEMA IF NOT EXISTS gold;

CREATE OR REPLACE TABLE gold.fact_leadtime AS
WITH source_data AS (
    -- columns from silver
    SELECT s.wh AS "WH", s.asn AS "ASN#", s.folio AS "Folio", s.port AS "Port", s.asn_receive AS "ASN RECEIVE", s.region AS "COUNTRY", s.avg_xfty_to_received, s.min_xft_to_received, s.max_xft_to_received, s.delivery_to_received, s.eta_to_delivery, s.etd_to_eta, s.gate_in_to_etd, s.pos_consolidation_to_gate_in, s.xfty_range
    FROM silver.leadtime_data s
),

unpivoted AS (
    -- changing phase columns into rows
    SELECT s."WH", s."ASN#", s."Folio", s."Port", s."ASN RECEIVE", s."COUNTRY", p.phase AS "Phase", p.value AS "Value"
    FROM source_data s
    CROSS JOIN LATERAL (VALUES ('Avg XFTY to Received', s.avg_xfty_to_received), ('Min XFT to Received', s.min_xft_to_received), ('Max XFT to Received', s.max_xft_to_received), ('Delivery to Received', s.delivery_to_received), ('ETA to Delivery', s.eta_to_delivery), ('ETD to ETA', s.etd_to_eta), ('Gate In to ETD', s.gate_in_to_etd), ('POS Consolidation to Gate In', s.pos_consolidation_to_gate_in), ('Max-Min XFTY', s.xfty_range)) p(phase,value)
)

SELECT MD5(CONCAT_WS('|',COALESCE(CAST("ASN RECEIVE" AS VARCHAR),'<NULL>'),COALESCE(CAST("ASN#" AS VARCHAR),'<NULL>'),COALESCE(CAST("Folio" AS VARCHAR),'<NULL>'),COALESCE(CAST("COUNTRY" AS VARCHAR),'<NULL>'),COALESCE(CAST("Phase" AS VARCHAR),'<NULL>'),COALESCE(CAST("Port" AS VARCHAR),'<NULL>'),COALESCE(CAST("WH" AS VARCHAR),'<NULL>'))) AS fact_row_key, CAST("ASN RECEIVE" AS DATE) AS date_key, "WH", "ASN#", "Folio", "Port", "ASN RECEIVE", "COUNTRY", "Phase", "Value"
FROM unpivoted;

-- dimensions
CREATE OR REPLACE TABLE gold.dim_wh AS
SELECT DISTINCT "WH" FROM gold.fact_leadtime WHERE "WH" IS NOT NULL;

CREATE OR REPLACE TABLE gold.dim_port AS
SELECT DISTINCT "Port" FROM gold.fact_leadtime WHERE "Port" IS NOT NULL;

CREATE OR REPLACE TABLE gold.dim_country AS
SELECT DISTINCT "COUNTRY" AS "Country" FROM gold.fact_leadtime WHERE "COUNTRY" IS NOT NULL;

-- phase
CREATE OR REPLACE TABLE gold.dim_phase AS
-- cast the integers explicitly: read_csv_auto infers BIGINT, and letting that
-- through would widen the column types in gold and in the exported parquet.
SELECT Phase, phase_alias, CAST(phase_order AS INTEGER) AS phase_order, phase_group,
       CAST(benchmark_days AS INTEGER) AS benchmark_days, is_assumption
FROM read_csv_auto('2_Data_Lakehouse/Master/dim_phase.csv',header=true)
ORDER BY phase_order;