-- =============================================================================
-- M3 Item Master (T-SQL, runs on the M3 SQL Server -- NOT DuckDB)
-- =============================================================================
-- Pulled by extract_m3_item_master.py into bronze.m3_item_master.
-- The database comes from the connection string, so there is no USE line
-- here -- the extract script rejects anything that isn't a single SELECT,
-- in case the login it runs under is not read-only.
--
-- One company only: the parameter marker in the WHERE clause is bound to
-- M3_COMPANY from config.py.
-- MITMAS is keyed on (MMCONO, MMITNO), so without the company filter the
-- same SKU would come back once per company.
--
-- Deliberately left out: facility-level fields (facility, tariff codes,
-- cost). Those live at item x facility level in MITFAC, and joining it
-- would repeat every SKU once per facility.
--
-- The lookups below can still return more than one row per SKU in theory
-- (CSYTAB is also keyed on division / language). Silver keeps the first row
-- per SKU and the pipeline prints how many SKUs that affected.
-- =============================================================================

SELECT

LTRIM(RTRIM(CTTX15)) AS 'Brand Name',

MMITCL AS 'Brand',

CASE
WHEN CHARINDEX('/', MMITDS) > 0 THEN SUBSTRING(MMITDS, 0, CHARINDEX('/', MMITDS))
ELSE MMITDS END AS 'STYLE NAME',

LTRIM(RTRIM(HMSTYN)) AS 'STYLE',

LTRIM(RTRIM(MMITNO)) AS 'SKU',

MMSPE4 AS 'Color Name',

LTRIM(RTRIM(MMCFI1)) AS 'YEAR/SEASON',

RTRIM(CASE WHEN MMUNMS = 'CA' THEN MMSPAC ELSE HMOPTX END) AS 'Size',

LTRIM(RTRIM(HMOPTY)) AS 'WIDTH',

RTRIM(SG1.SGTX40) AS 'Category',

RTRIM(SG3.SGTX40) AS 'Sub Category',

CASE WHEN MMUNMS = 'CA' THEN MUCOFA ELSE '1' END AS 'Pair per Unit',

MMSPAC 'Package',

MPPOPN AS 'UPC',

CAST(ROUND(MMSAPR, 2) AS NUMERIC(17,2)) AS 'SALES PRICE',

CAST(ROUND(MMPUPR, 2) AS NUMERIC(17,2)) AS 'PURCHASE PRICE',

MMUNMS AS 'Unit of Measure'


FROM MVXJDTA.MITMAS WITH (NOLOCK)

LEFT JOIN MVXJDTA.MITAUN WITH (NOLOCK) ON MMCONO = MUCONO AND MMITNO = MUITNO AND MUAUS9 = 1 AND MUAUTP = 2

LEFT JOIN MVXJDTA.MITMAH WITH (NOLOCK) ON MMCONO = HMCONO AND MMITNO = HMITNO

LEFT JOIN MVXJDTA.MITPOP WITH (NOLOCK) ON MMCONO = MPCONO AND MMITNE = MPITNO AND MPALWT = 2 AND MPALWQ = 'UPC'

LEFT JOIN MVXJDTA.CSYTAB WITH (NOLOCK) ON CTCONO = MMCONO AND CTSTCO = 'ITCL' AND CTSTKY = MMITCL

LEFT JOIN MVXJDTA.MITSCH AS SG1 WITH (NOLOCK) ON SG1.SGCONO = MMCONO AND SG1.SGGLVL = 1 AND SG1.SGSGP0 = MMGRP1

LEFT JOIN MVXJDTA.MITSCH AS SG3 WITH (NOLOCK) ON SG3.SGCONO = MMCONO AND SG3.SGGLVL = 3 AND SG3.SGSGP0 = MMGRP3


WHERE MMCONO = ?
