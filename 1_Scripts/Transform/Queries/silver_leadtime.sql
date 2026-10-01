-- =============================================================================
-- Silver Layer: Unified Lead Time Data
-- =============================================================================
-- Normalizes 7 quarterly bronze tables into one canonical table.
--
-- Table selection per period:
--   2023        shipment_lead_time_2023_data       (ETD < 2023-11-01)
--   2024 Q1     shipment_lead_time_2024_q1_data    (2023-11-01 to 2024-03-31)
--   2024 Q2     shipment_lead_time_2024_q2_data    (2024-04-01 to 2024-05-31)
--   2024 Q3     shipment_lead_time_2024_q3_data    (2024-06-01 to 2024-08-31)
--   2024 Q4     shipment_lead_time_2024_q4_data    (2024-09-01 to 2024-11-30)
--   2025 Q1     shipment_lead_time_2025_q1_data    (2024-12-01 to 2025-02-28)
--   2025 Q2     shipment_lead_time_2025_q2_data    (ETD >= 2025-03-01)
--
-- Cutoff logic: for overlapping months, the table with more rows was chosen
-- (higher row count = more complete data for that month).
--
-- Column changes handled:
--   continer_size / container_size     -> container_size  (typo fixed in Q2 2024, dropped Q4+)
--   min_max_xfty / max_min_xfty        -> xfty_range      (same metric, name flipped in Q3)
--   whr                                -> wh              (renamed in Q2 2025)
--   min/max_of_po_head_req_deliv_date  -> min/max_req_delivery_date (renamed in Q2 2025)
--   customer, asn_qty                  -> NULL from Q2 2024 onward  (dropped from template)
--   div, vessel, container_size        -> NULL from Q4 2024 onward  (dropped from template)
-- =============================================================================


-- Step 1: Run this SELECT to validate before writing to Silver.
-- Step 2: Uncomment CREATE OR REPLACE TABLE ... AS to persist.

-- CREATE OR REPLACE TABLE silver.leadtime_data AS

SELECT
    wh                                          AS wh,
    asn,
    folio,
    div,
    continer_size                               AS container_size,
    vessel,
    b_l,
    port,
    container,
    min_of_po_head_req_delivery_date::DATE      AS min_req_delivery_date,
    max_of_po_head_req_delivery_date::DATE      AS max_req_delivery_date,
    min_max_xfty                                AS xfty_range,
    xfty_to_container_consolidation,
    pos_consolidation_to_gate_in,
    gate_in::DATE,
    gate_in_to_etd,
    etd::DATE                                   AS etd,
    etd_to_eta,
    current_eta_port::DATE,
    eta_to_delivery,
    COALESCE(TRY_STRPTIME(TRIM(p_u), '%Y-%m-%d %H:%M:%S'), TRY_STRPTIME(TRIM(p_u), '%m/%d/%y'))::DATE AS p_u,
    delivery_to_received,
    asn_receive::DATE,
    max_xft_to_received,
    min_xft_to_received,
    avg_xfty_to_received,
    customer,
    region,
    asn_qty,
    '2023'                                      AS _source_period,
    _bronze_insert_ts,
    _source_file_name
FROM bronze.shipment_lead_time_2023_data
WHERE etd < '2023-11-01'

UNION ALL

SELECT
    wh,
    asn,
    folio,
    div,
    continer_size                               AS container_size,
    vessel,
    b_l,
    port,
    container,
    min_of_po_head_req_delivery_date::DATE      AS min_req_delivery_date,
    max_of_po_head_req_delivery_date::DATE      AS max_req_delivery_date,
    min_max_xfty                                AS xfty_range,
    xfty_to_container_consolidation,
    pos_consolidation_to_gate_in,
    gate_in::DATE,
    gate_in_to_etd,
    etd::DATE                                   AS etd,
    etd_to_eta,
    current_eta_port::DATE,
    eta_to_delivery,
    p_u::DATE,
    delivery_to_received,
    asn_receive::DATE,
    max_xft_to_received,
    min_xft_to_received,
    avg_xfty_to_received,
    customer,
    region,
    asn_qty,
    '2024_Q1'                                   AS _source_period,
    _bronze_insert_ts,
    _source_file_name
FROM bronze.shipment_lead_time_2024_q1_data
WHERE etd >= '2023-11-01' AND etd < '2024-04-01'

UNION ALL

SELECT
    wh,
    asn,
    folio,
    div,
    container_size,
    vessel,
    b_l,
    port,
    container,
    min_of_po_head_req_delivery_date::DATE      AS min_req_delivery_date,
    max_of_po_head_req_delivery_date::DATE      AS max_req_delivery_date,
    max_min_xfty                                AS xfty_range,
    xfty_to_container_consolidation,
    pos_consolidation_to_gate_in,
    gate_in::DATE,
    gate_in_to_etd,
    etd::DATE                                   AS etd,
    etd_to_eta,
    current_eta_port::DATE,
    eta_to_delivery,
    p_u::DATE,
    delivery_to_received,
    asn_receive::DATE,
    max_xft_to_received,
    min_xft_to_received,
    avg_xfty_to_received,
    NULL                                        AS customer,
    region,
    NULL                                        AS asn_qty,
    '2024_Q2'                                   AS _source_period,
    _bronze_insert_ts,
    _source_file_name
FROM bronze.shipment_lead_time_2024_q2_data
WHERE etd >= '2024-04-01' AND etd < '2024-06-01'

UNION ALL

SELECT
    wh,
    asn,
    folio,
    div,
    container_size,
    vessel,
    b_l,
    port,
    container,
    min_of_po_head_req_delivery_date::DATE      AS min_req_delivery_date,
    max_of_po_head_req_delivery_date::DATE      AS max_req_delivery_date,
    max_min_xfty                                AS xfty_range,
    xfty_to_container_consolidation,
    pos_consolidation_to_gate_in,
    gate_in::DATE,
    gate_in_to_etd,
    etd::DATE                                   AS etd,
    etd_to_eta,
    current_eta_port::DATE,
    eta_to_delivery,
    p_u::DATE,
    delivery_to_received,
    asn_receive::DATE,
    max_xft_to_received,
    min_xft_to_received,
    avg_xfty_to_received,
    NULL                                        AS customer,
    region,
    NULL                                        AS asn_qty,
    '2024_Q3'                                   AS _source_period,
    _bronze_insert_ts,
    _source_file_name
FROM bronze.shipment_lead_time_2024_q3_data
WHERE etd >= '2024-06-01' AND etd < '2024-09-01'

UNION ALL

SELECT
    wh,
    asn,
    folio,
    NULL                                        AS div,
    NULL                                        AS container_size,
    NULL                                        AS vessel,
    b_l,
    port,
    container,
    min_of_po_head_req_delivery_date::DATE      AS min_req_delivery_date,
    max_of_po_head_req_delivery_date::DATE      AS max_req_delivery_date,
    max_min_xfty                                AS xfty_range,
    xfty_to_container_consolidation,
    pos_consolidation_to_gate_in,
    gate_in::DATE,
    gate_in_to_etd,
    etd::DATE                                   AS etd,
    etd_to_eta,
    current_eta_port::DATE,
    eta_to_delivery,
    p_u::DATE,
    delivery_to_received,
    asn_receive::DATE,
    max_xft_to_received,
    min_xft_to_received,
    avg_xfty_to_received,
    NULL                                        AS customer,
    region,
    NULL                                        AS asn_qty,
    '2024_Q4'                                   AS _source_period,
    _bronze_insert_ts,
    _source_file_name
FROM bronze.shipment_lead_time_2024_q4_data
WHERE etd >= '2024-09-01' AND etd < '2024-12-01'

UNION ALL

SELECT
    wh,
    asn,
    folio,
    NULL                                        AS div,
    NULL                                        AS container_size,
    NULL                                        AS vessel,
    b_l,
    port,
    container,
    min_of_po_head_req_delivery_date::DATE      AS min_req_delivery_date,
    max_of_po_head_req_delivery_date::DATE      AS max_req_delivery_date,
    max_min_xfty                                AS xfty_range,
    xfty_to_container_consolidation,
    pos_consolidation_to_gate_in,
    gate_in::DATE,
    gate_in_to_etd,
    etd::DATE                                   AS etd,
    etd_to_eta,
    current_eta_port::DATE,
    eta_to_delivery,
    p_u::DATE,
    delivery_to_received,
    asn_receive::DATE,
    max_xft_to_received,
    min_xft_to_received,
    avg_xfty_to_received,
    NULL                                        AS customer,
    region,
    NULL                                        AS asn_qty,
    '2025_Q1'                                   AS _source_period,
    _bronze_insert_ts,
    _source_file_name
FROM bronze.shipment_lead_time_2025_q1_data
WHERE etd >= '2024-12-01' AND etd < '2025-03-01'

UNION ALL

SELECT
    whr                                         AS wh,
    asn,
    folio,
    NULL                                        AS div,
    NULL                                        AS container_size,
    NULL                                        AS vessel,
    b_l,
    port,
    container,
    COALESCE(TRY_STRPTIME(min_header_delivery_date, '%m-%d-%Y'), TRY_STRPTIME(min_header_delivery_date, '%Y-%m-%d %H:%M:%S'))::DATE AS min_req_delivery_date,
    COALESCE(TRY_STRPTIME(max_header_delivery_date, '%m-%d-%Y'), TRY_STRPTIME(max_header_delivery_date, '%Y-%m-%d %H:%M:%S'))::DATE AS max_req_delivery_date,
    max_min_xfty                                AS xfty_range,
    xfty_to_container_consolidation,
    pos_consolidation_to_gate_in,
    gate_in::DATE,
    gate_in_to_etd,
    etd::DATE                                   AS etd,
    etd_to_eta,
    current_eta_port::DATE,
    eta_to_delivery,
    p_u::DATE,
    delivery_to_received,
    COALESCE(TRY_STRPTIME(asn_receive, '%m-%d-%Y'), TRY_STRPTIME(asn_receive, '%Y-%m-%d %H:%M:%S'))::DATE AS asn_receive,
    max_xft_to_received,
    min_xft_to_received,
    avg_xfty_to_received,
    NULL                                        AS customer,
    region,
    NULL                                        AS asn_qty,
    '2025_Q2'                                   AS _source_period,
    _bronze_insert_ts,
    _source_file_name
FROM bronze.shipment_lead_time_2025_q2_data
WHERE etd >= '2025-03-01'

ORDER BY etd;
