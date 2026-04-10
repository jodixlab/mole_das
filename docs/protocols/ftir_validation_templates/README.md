# FTIR Validation Templates

These templates support the `FTIR Side-by-Side Validation` block in the full DAQ Runner `Report Builder`.

Files:
- `FTIR_VALIDATION_IMPORT_TEMPLATE_2026_04_10_001.csv`
  - Normalized FTIR import layout for direct runner ingestion.
  - Required field: `timestamp`
  - Use ISO-8601 timestamps with timezone when possible.
- `FTIR_VALIDATION_MANUAL_WINDOWS_TEMPLATE_2026_04_10_001.csv`
  - Manual comparison windows in the exact format accepted by the runner:
  - `run_no,start_ts_iso,end_ts_iso,label`
- `FTIR_VALIDATION_COLUMN_MAP_TEMPLATE_2026_04_10_001.csv`
  - Optional analyte-to-column lookup if the FTIR export headers do not match analyte codes.
- `FTIR_VALIDATION_ALIGNMENT_WORKSHEET_2026_04_10_001.xlsx`
  - Field-facing workbook for timestamp alignment, comparison-window curation, and manual-window preparation.

Operator use:
1. Normalize the FTIR export into the import template columns, or use the column map if the raw FTIR file already contains the needed fields.
2. Record comparison windows and purge boundaries in the alignment worksheet.
3. If manual windows are needed, use the workbook `Runner_Manual_Windows` sheet or the companion manual windows CSV.
4. In the full DAQ Runner `Report Builder`, enable `FTIR validation`, browse to the FTIR file, and populate any manual windows or column-map entries as needed.

Common analytes included in the templates:
- `O2`
- `CO2`
- `CO`
- `NO`
- `NO2`
- `NOX`
- `SO2`
- `VOC`
- `NH3`
- `CH4`

Notes:
- The FTIR validation package degrades explicitly when evidence is missing. It does not fabricate a formal Method 301 outcome.
- Formal `METHOD_301_FORMAL` use still depends on the required paired-window design being satisfied by the session evidence.
