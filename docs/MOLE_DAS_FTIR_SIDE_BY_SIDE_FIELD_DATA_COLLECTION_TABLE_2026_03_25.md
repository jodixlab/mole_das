# MOLE DAS FTIR Side-by-Side Field Data Collection Table

Document date: 2026-03-25  
Deployment basis: `2026_03_24_002`  
Companion procedure: `MOLE_DAS_FTIR_SIDE_BY_SIDE_SIMPLE_WORKFLOW_2026_03_25.md`

Companion field assets:
- `MOLE_DAS_FTIR_SIDE_BY_SIDE_FIELD_DATA_TEMPLATE_2026_03_25.csv`
- `MOLE_DAS_FTIR_SIDE_BY_SIDE_FIELD_FORM_1PAGE_2026_03_25.md`

Use note:
- This table is intended for formal FTIR side-by-side work in the standard DAQ Runner path.
- Diagnostics mode is excluded from this workflow.

## 1. Project Header

| Field | Entry |
|---|---|
| Project ID | |
| Facility / Site | |
| Unit / Engine / Source | |
| Test Date | |
| Operator | |
| FTIR Operator | |
| MOLE Deployment Folder | |
| MOLE Package Version | |
| FTIR Project / File ID | |
| FTIR Computer Time Zone | |
| MOLE Computer Time Zone | |
| Known Clock Offset Between Systems | |
| Positive-Pressure Sample Confirmed | Yes / No |
| Tee Installed on FTIR Incoming Line | Yes / No |
| Block Valve Installed on MOLE Branch | Yes / No |
| MOLE Vent Routed to Safe Vent | Yes / No |
| Cal / Bias Gas Connected | Yes / No |
| Notes | |

## 2. Installation and Setup Check

| Check Item | Status | Notes |
|---|---|---|
| Tee installed upstream of FTIR measurement point | | |
| Block valve installed on MOLE sample branch | | |
| MOLE branch leak checked | | |
| Vent line clear and routed safely | | |
| Calibration gas connected | | |
| Ambient purge path confirmed | | |
| FTIR powered and stable | | |
| MOLE powered and stable | | |
| Time sync checked between MOLE and FTIR | | |

## 3. Warmup Record

| Item | Time | Notes |
|---|---|---|
| FTIR power on | | |
| FTIR ready / stable | | |
| MOLE power on | | |
| MOLE ready / stable | | |
| MOLE branch block valve opened | | |

## 4. Calibration and Gas Record

| Gas Role | Cylinder ID | Certified Value | Units | Balance Gas | Start Time | Stop Time | Notes |
|---|---|---:|---|---|---|---|---|
| Zero / purge basis | | | | | | | |
| Span gas | | | | | | | |
| Bias / cal gas | | | | | | | |
| Drift gas | | | | | | | |

## 5. Pre-Project Calibration Record

| Step | Start Time | Stop Time | Measured Response | Units | Pass / Fail | Notes |
|---|---|---|---:|---|---|---|
| Ambient purge before calibration | | | | | | |
| Pre-project zero | | | | | | |
| Pre-project span | | | | | | |
| Bias line verification | | | | | | |
| O2 ambient confirmation during purge | | | % | | |

## 6. Test Run Log

| Run No. | FTIR Start | MOLE Start | FTIR Stop | MOLE Stop | Block Valve Open Time | Block Valve Close Time | Notes |
|---:|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |
| 6 | | | | | | | |

## 7. Twenty-Minute Bias Valve Event Log

Use one line for every calibration bias valve opening event during the project.

| Event No. | Associated Run No. | Open Time | Close Time | Approx. Runtime Minute | Operator Initials | Notes |
|---:|---:|---|---|---:|---|---|
| 1 | | | | | | |
| 2 | | | | | | |
| 3 | | | | | | |
| 4 | | | | | | |
| 5 | | | | | | |
| 6 | | | | | | |
| 7 | | | | | | |
| 8 | | | | | | |
| 9 | | | | | | |
| 10 | | | | | | |
| 11 | | | | | | |
| 12 | | | | | | |

## 8. Ambient Purge Log After Each Run

| Run No. | Purge Start | Purge Stop | O2 During Purge | Units | Ambient O2 Expected | Pass / Fail | Notes |
|---:|---|---|---:|---|---:|---|---|
| 1 | | | | % | 20.9 | | |
| 2 | | | | % | 20.9 | | |
| 3 | | | | % | 20.9 | | |
| 4 | | | | % | 20.9 | | |
| 5 | | | | % | 20.9 | | |
| 6 | | | | % | 20.9 | | |

## 9. Timestamp Alignment Markers

Use this sheet to capture common event markers for later alignment of MOLE and FTIR outputs.

| Marker Type | FTIR Timestamp | MOLE Timestamp | Common Wall-Clock Time | Notes |
|---|---|---|---|---|
| Project acquisition start | | | | |
| First calibration step start | | | | |
| First bias valve opening | | | | |
| Mid-project bias valve opening | | | | |
| Purge start after run 1 | | | | |
| Purge start after run 2 | | | | |
| Post-project drift test start | | | | |

## 10. Post-Project Drift Test

This is required after the testing project, not after each individual run.

| Step | Start Time | Stop Time | Gas Used | Certified Value | Measured Response | Units | Pass / Fail | Notes |
|---|---|---|---|---:|---:|---|---|---|
| Ambient purge before drift | | | | | | | | |
| Post-project drift test | | | | | | | | |
| Final ambient purge | | | | | | | | |

## 11. Recommended MOLE/FTIR Artifact Capture

| Artifact | Collected | File Name / Location | Notes |
|---|---|---|---|
| MOLE session folder | | | |
| FTIR project / PRN export | | | |
| Screenshot of MOLE warmup ready state | | | |
| Screenshot of FTIR ready state | | | |
| Screenshot of pre-project calibration | | | |
| Screenshot of post-project drift test | | | |
| Operator handwritten or typed notes | | | |

## 12. Quick Field Notes

| Time | Observation / Action | Initials |
|---|---|---|
| | | |
| | | |
| | | |
| | | |
| | | |
| | | |
| | | |
| | | |
