# MOLE DAS Master Test Report Template

This template is intended to become the master structure for MOLE-generated emissions performance test reports. It follows the GD-043 style sections summarized in [epa_emissions_performance_test_structural_assessment.md](C:\Users\Joe Etheridge\OneDrive\mole_das_development_shared\2026_04_09_001\docs\epa_emissions_performance_test_structural_assessment.md) and is written so each heading can be filled from structured MOLE session data where available.

Use `{{...}}` placeholders as data tokens for future automated report generation. Keep optional sections and mark them `N/A` when not applicable.

## Cover / Certification

- Report title: `{{REPORT.TITLE}}`
- Facility / site: `{{PROJECT.SITE_FACILITY}}`
- Unit / asset: `{{SOURCE.MANUFACTURER}} {{SOURCE.MODEL_NUMBER}} / {{PROJECT.ASSET_UNIT_ID}}`
- Job ID: `{{PROJECT.JOB_ID}}`
- Test dates: `{{TEST.DATES}}`
- Prepared for: `{{REPORT.CLIENT_NAME}}`
- Prepared by: `{{REPORT.TEST_COMPANY_NAME}}`
- Report revision / date: `{{REPORT.REVISION}} / {{REPORT.ISSUE_DATE}}`
- Responsible official / signature block

## Table of Contents

- Auto-generated section list
- Auto-generated appendix list
- Auto-generated figure and table list

## 1. Introduction

### 1.1 Purpose and objective

- Regulatory purpose: `{{PROJECT.INTAKE.REGULATORY_PURPOSE}}`
- Test objective narrative
- Compliance or engineering basis

### 1.2 Responsible groups

- Facility owner / operator
- Test company
- Laboratory
- Agency / observer contacts

### 1.3 Facility and source identification

- Facility name and location
- Coordinates / elevation
- Emission unit ID
- Source category / application / service class

### 1.4 Pollutants and methods summary

| Pollutant | Method | Analyzer / Instrument | Units | Compliance basis |
|---|---|---|---|---|
| `{{POLLUTANT.CODE}}` | `{{POLLUTANT.METHOD}}` | `{{POLLUTANT.INSTRUMENT}}` | `{{POLLUTANT.UNITS}}` | `{{LIMIT.BASIS}}` |

### 1.5 Test dates and schedule

- Planned test dates
- Actual test dates
- Run schedule summary
- Delays, interruptions, or schedule deviations

## 2. Plant and Sampling Location Description

### 2.1 Process and source description

- Process narrative
- Unit description
- Fuel description
- Normal operating mode during the test

### 2.2 Control equipment description

- Control device(s)
- Control operating parameters
- Control-system narrative

### 2.3 Stack / duct and sampling location description

| Item | Value |
|---|---|
| Stack shape | `{{SOURCE.STACK.SHAPE}}` |
| Diameter / width / height | `{{SOURCE.STACK.SIZE}}` |
| Port count / angles | `{{SOURCE.STACK.PORTS}}` |
| Port height AGL | `{{SOURCE.STACK.PORT_HEIGHT_FT_AGL}}` |
| Upstream disturbance distance | `{{SOURCE.STACK.UPSTREAM_DIAMETERS}}` |
| Downstream disturbance distance | `{{SOURCE.STACK.DOWNSTREAM_DIAMETERS}}` |
| Traverse basis | `{{SOURCE.STACK.TRAVERSE_SCHEME}}` |

### 2.4 Sampling-location adequacy narrative

- Method 1 / method-specific location adequacy statement
- Cyclonic flow or stratification discussion if applicable
- Sampling-location figure reference

## 3. Summary and Discussion of Results

### 3.1 Test matrix

| Run | Date | Start | Stop | Pollutants / Methods | Operating level | Status |
|---|---|---|---|---|---|---|
| `{{RUN.NO}}` | `{{RUN.DATE}}` | `{{RUN.START}}` | `{{RUN.STOP}}` | `{{RUN.METHODS}}` | `{{RUN.OPERATING_LEVEL}}` | `{{RUN.STATUS}}` |

### 3.2 Operating conditions summary

| Parameter | Run 1 | Run 2 | Run 3 | Average | Units |
|---|---|---|---|---|---|
| Load / duty | `{{RUN1.LOAD}}` | `{{RUN2.LOAD}}` | `{{RUN3.LOAD}}` | `{{RUNAVG.LOAD}}` | `{{LOAD.UNITS}}` |
| Fuel flow | `{{RUN1.FUEL_FLOW}}` | `{{RUN2.FUEL_FLOW}}` | `{{RUN3.FUEL_FLOW}}` | `{{RUNAVG.FUEL_FLOW}}` | `{{FUEL_FLOW.UNITS}}` |
| Exhaust flow | `{{RUN1.EXH_FLOW}}` | `{{RUN2.EXH_FLOW}}` | `{{RUN3.EXH_FLOW}}` | `{{RUNAVG.EXH_FLOW}}` | `{{EXH_FLOW.UNITS}}` |
| O2 dry | `{{RUN1.O2_DRY}}` | `{{RUN2.O2_DRY}}` | `{{RUN3.O2_DRY}}` | `{{RUNAVG.O2_DRY}}` | `%` |
| Moisture | `{{RUN1.MOISTURE}}` | `{{RUN2.MOISTURE}}` | `{{RUN3.MOISTURE}}` | `{{RUNAVG.MOISTURE}}` | `%` |

### 3.3 Results summary

| Pollutant | Run 1 | Run 2 | Run 3 | Average | Units | Limit | Pass / Fail |
|---|---|---|---|---|---|---|---|
| `{{RESULT.POLLUTANT}}` | `{{RESULT.RUN1}}` | `{{RESULT.RUN2}}` | `{{RESULT.RUN3}}` | `{{RESULT.AVG}}` | `{{RESULT.UNITS}}` | `{{RESULT.LIMIT}}` | `{{RESULT.STATUS}}` |

### 3.4 Discussion of results

- Compliance discussion
- Any observed anomalies or field changes
- Explanation of excluded or invalid data
- Summary of pollutant adjustments, if applied

## 4. Sampling and Analytical Procedures

### 4.1 Test methods used

| Pollutant / Parameter | Method | Basis / Version | Deviations? | Reference appendix |
|---|---|---|---|---|
| `{{METHOD.POLLUTANT}}` | `{{METHOD.CODE}}` | `{{METHOD.VERSION}}` | `{{METHOD.DEVIATION_FLAG}}` | `{{APPENDIX.METHOD}}` |

### 4.2 Sampling system and analyzer configuration

- Analyzer list
- Instrument IDs / channels
- Sample system narrative
- Calibration gas summary

### 4.3 Analytical procedure details

- Normalization and correction basis
- Fuel analysis methodology
- Moisture / oxygen correction basis
- Emission-rate or power-normalized calculation basis

### 4.4 Deviations, alternatives, and approvals

- Planned deviations
- Field deviations
- Agency-approved alternatives
- Deviation impact assessment

## 5. QA/QC Activities

### 5.1 Pre-test checks

- Calibration summary
- Linearity summary
- Leak checks
- Warmup / stability confirmation

### 5.2 During-test QA/QC

- Analyzer health / validity
- Side-by-side / reference audit summary
- Weather or site-condition traceability
- Corrective actions taken during the test

### 5.3 Post-test checks

- Post-run zero / span results
- Drift evaluation
- Post-cal decision review
- Bias / drift carry-forward or suspension summary

### 5.4 QA/QC exceptions

- Failures
- Invalidations
- Retests
- Impact on final data validity

## 6. Appendices

### Appendix A - Regulatory and administrative support

- Notice letters / agency correspondence
- Permit excerpts
- Test plan references

### Appendix B - Source and sampling location support

- Site map
- Stack / duct sketch
- Sampling-location figure
- Source photos

### Appendix C - Method and instrument support

- Analyzer configuration sheets
- Cylinder certificates
- Instrument communications / setup snapshots

### Appendix D - QA/QC support

- Calibration tables
- Linearity tables
- Drift records
- Spike recovery records
- Side-by-side / FTIR reference records

### Appendix E - Field and raw data

- Raw sample files
- Workstep logs
- Weather logs
- Field notes
- Uploaded field documents

### Appendix F - Calculations and report outputs

- Calculation summary tables
- Fuel analysis summary
- Pollutant adjustment snapshot and history
- Regulatory comparison tables

## Recommended Automation Notes

- Treat Sections 1 to 5 as generated narrative + tables.
- Treat Appendices as an indexed evidence manifest.
- Generate a final appendix table with document title, source path, hash, and appendix assignment.
- Keep report generation separate from report-pack evidence export, but reuse the same normalized session summary objects.
