# Data Catalog

## Silver Layer

### silver.leadtime_data

**Description:** Cleaned, deduplicated import/ocean-freight shipment lead-time detail. Unions the quarterly Bronze `shipment_lead_time_*` detail tables (one Excel workbook per quarter) into a single table, standardizing column names/types across quarters (source files renamed columns and date formats release to release).
**Grain:** One row per shipment leg — `wh, asn, folio, b_l, container, etd`. Duplicates across Bronze re-uploads are resolved by keeping the row with the latest `_bronze_insert_ts`.

| Field | Type | Description |
|---|---|---|
| `wh` | VARCHAR | Destination warehouse code. Resolves to a warehouse name via the Bronze `whr_code` reference tabs — that mapping is not yet joined into Silver. |
| `asn` | VARCHAR | Advance Shipping Notice number — the shipment identifier used to track the ASN through receipt at the warehouse. |
| `folio` | VARCHAR | Folio / PO reference number for the shipment. |
| `div` | VARCHAR | Internal division / customer-program code. Source data is inconsistently formatted — may contain multiple comma- or newline-separated codes. |
| `container_size` | VARCHAR | Container size or load type, as entered in source (e.g. `20`, `40`, `40H` = 40ft high-cube, `45`, `FCL`, or `LCL` with a carton count). Not normalized. |
| `vessel` | VARCHAR | Ocean vessel name and voyage number. |
| `b_l` | VARCHAR | Bill of Lading number — the carrier's shipping document reference. |
| `port` | VARCHAR | Origin (loading) port name. |
| `container` | VARCHAR | Container number. |
| `min_req_delivery_date` | DATE | Earliest requested delivery date across the PO(s)/line items on this shipment. |
| `max_req_delivery_date` | DATE | Latest requested delivery date across the PO(s)/line items on this shipment. |
| `xfty_range` | DOUBLE | Spread, in days, between the earliest and latest Ex-Factory (XFTY — goods-ready-at-factory) dates among consolidated POs on this shipment. `0` when there's nothing to consolidate. |
| `xfty_to_container_consolidation` | TIMESTAMP | **Note:** despite the "duration"-style name, this holds the container consolidation date itself (not a day count), unlike the similarly-named fields below. |
| `pos_consolidation_to_gate_in` | DOUBLE | Days from container consolidation date to `gate_in`. |
| `gate_in` | DATE | Date the container gated in at the origin port. |
| `gate_in_to_etd` | DOUBLE | Days from `gate_in` to `etd`. |
| `etd` | DATE | Estimated/actual time of departure from the origin port. |
| `etd_to_eta` | DOUBLE | Ocean transit days from `etd` to `current_eta_port`. |
| `current_eta_port` | DATE | Current estimated (or actual) time of arrival at the destination port. |
| `eta_to_delivery` | DOUBLE | Days from `current_eta_port` to delivery at the consignee/warehouse. |
| `p_u` | DATE | Pick-up date — when the container was picked up from port/rail ramp for drayage. |
| `delivery_to_received` | DOUBLE | Days from delivery to warehouse receipt (`asn_receive`). In source data this frequently matches `eta_to_delivery` exactly — likely a data-quality artifact in the original workbook rather than two independently-measured durations; treat with caution. |
| `asn_receive` | DATE | Date the ASN/shipment was received at the destination warehouse. |
| `max_xft_to_received` | DOUBLE | Maximum total days from Ex-Factory to warehouse receipt, across consolidated line items. |
| `min_xft_to_received` | DOUBLE | Minimum total days from Ex-Factory to warehouse receipt, across consolidated line items. |
| `avg_xfty_to_received` | DOUBLE | Average total days from Ex-Factory to warehouse receipt — the headline end-to-end lead time metric. |
| `customer` | VARCHAR | Retail customer name. Not standardized — the same customer appears under many spellings/abbreviations in source data. |
| `region` | VARCHAR | Origin region/country of the shipment. Casing and spelling are inconsistent across source quarters (e.g. `China` / `CHINA` / `China `); Silver upper-cases and trims it. |
| `asn_qty` | DOUBLE | Unit/carton quantity on the ASN. |
| `_source_period` | VARCHAR | Pipeline metadata — the quarter/year label of the Bronze source table this row came from (e.g. `2023`, `2024_Q1`). |
| `_bronze_insert_ts` | TIMESTAMP WITH TIME ZONE | Pipeline metadata — when the source row was inserted into Bronze; used as the tiebreaker for de-duplication. |
| `_source_file_name` | VARCHAR | Pipeline metadata — original source file name the row was loaded from. |

### silver.item_master

**Description:** Infor M3 item master for one company, one row per SKU. Pulled from the M3 SQL Server by `1_Scripts/Extract/Queries/m3_item_master.sql` into `bronze.m3_item_master` (every column as raw text), then trimmed and typed here. Facility-level fields (facility, tariff codes, cost) are deliberately left out -- they live in `MITFAC`. Full refresh every run; no history is kept.
**Grain:** One row per `sku`. If the lookups ever return a SKU more than once, the first row is kept (preferring rows where `brand_name`, `pair_per_unit` and `upc` were found) and `pipeline_item_master.py` prints how many SKUs were affected. The row count should equal the company's row count in `MITMAS`.
**Includes style-level items:** some rows have no `style`, `size` or `width` because they have no `MITMAH` row -- mostly `PR` items whose SKU is a style number (the parent of the size-level SKUs), and few of them carry a UPC. They are M3 item records, not sellable size-level SKUs. They are **kept on purpose**; filter on `style IS NOT NULL` if you only want the latter.
**Gold / Parquet:** `gold.dim_item` holds the same columns renamed to the original query's display names (`"SKU"`, `"Brand Name"`, `"YEAR/SEASON"`, ...) and is exported to `2_Data_Lakehouse/3_Gold/dim_item.parquet`. After each run the file is also copied to every folder in `ITEM_MASTER_EXPORT_FOLDERS` (config.py). The copy is row-count checked and swapped in whole.

| Field | Type | Description |
|---|---|---|
| `sku` | VARCHAR | M3 item number (`MITMAS.MMITNO`). Primary key. |
| `style` | VARCHAR | Style number from the style matrix (`MITMAH.HMSTYN`). One style has many SKUs (colors x sizes x widths). |
| `style_name` | VARCHAR | Item description (`MMITDS`) up to the first `/`. |
| `brand` | VARCHAR | Item class code used as the brand code (`MMITCL`). |
| `brand_name` | VARCHAR | Brand name for `brand`, from the M3 `ITCL` lookup table (`CSYTAB.CTTX15`). |
| `color_name` | VARCHAR | Color name (`MMSPE4`). |
| `year_season` | VARCHAR | The SKU's latest season code (`MMCFI1`), unchanged -- `<yy><season>`, e.g. `25SP`, `26FA`. Because only the latest code is kept, a carry-over SKU's season can change between runs. Season belongs to the SKU, not the style: one style can have SKUs in more than one season. |
| `size` | VARCHAR | Size from the style matrix (`HMOPTX`); for case items (`unit_of_measure = 'CA'`) the package code (`MMSPAC`) instead. |
| `width` | VARCHAR | Width from the style matrix (`HMOPTY`). |
| `category` | VARCHAR | Level-1 item group name (`MITSCH` via `MMGRP1`). |
| `sub_category` | VARCHAR | Level-3 item group name (`MITSCH` via `MMGRP3`). Often empty. |
| `pair_per_unit` | DECIMAL(18,4) | Pairs per selling unit: the case conversion factor (`MITAUN.MUCOFA`) for case items, otherwise `1`. NULL only where a `CA` item has no matching `MITAUN` row. |
| `package` | VARCHAR | Package code (`MMSPAC`). |
| `upc` | VARCHAR | UPC (`MITPOP.MPPOPN`, alias type 2 / qualifier `UPC`). At most one per SKU; missing on most style-level rows. Text, so leading zeros are kept. **Not unique the other way round:** a style-level item can share its child's UPC, so don't join on UPC as if it were a key. |
| `sales_price` | DECIMAL(17,2) | Sales price on the item (`MMSAPR`), rounded to 2 decimals. Can be `0.00`. |
| `purchase_price` | DECIMAL(17,2) | Purchase price on the item (`MMPUPR`), rounded to 2 decimals. Can be `0.00`. Not the facility cost (that is in `MITFAC`, not pulled). |
| `unit_of_measure` | VARCHAR | Basic unit of measure (`MMUNMS`), e.g. `PR` (pair), `CA` (case pack), `EA`. |
| `_bronze_insert_ts` | TIMESTAMP WITH TIME ZONE | Pipeline metadata -- when this extract was loaded into Bronze. |
| `_source_file_name` | VARCHAR | Pipeline metadata -- the extract query file (`m3_item_master.sql`). |
