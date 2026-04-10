# MOLE DAS Test Report Data Elements Crosswalk

This crosswalk reviews the current MOLE session and report-pack structure against the final-report structure described in [epa_emissions_performance_test_structural_assessment.md](C:\Users\Joe Etheridge\OneDrive\mole_das_development_shared\2026_04_09_001\docs\epa_emissions_performance_test_structural_assessment.md).

Coverage legend:

- `Available`: already captured in structured MOLE data or report-pack outputs.
- `Partial`: some data exists, but it still needs narrative, normalization, or stronger structure for report generation.
- `Gap`: not captured in a reliable structured way today.

## Current MOLE sources reviewed

- Session configuration: `project`, `source`, `fuel`, `pollutants`, `test_matrix`, `regulatory`, `site_conditions`
- Session evidence: worksteps, raw samples, health states, weather logs, static artifacts
- Report pack outputs: `summary.json`, QA/QC CSVs, fuel-analysis summary, adjustment provenance, reference audit, evidence bundle

## Crosswalk

| Report section | Data element | Status | Current MOLE source | Notes |
|---|---|---|---|---|
| Introduction | Job ID, project name, facility/site label, operator | Available | `session.project` | Good starting admin block. |
| Introduction | Responsible groups: client, tester, laboratory, observers | Gap | Not normalized | Needs explicit report parties block. |
| Introduction | Regulatory purpose and applicable rules | Partial | `project.intake.regulatory_purpose`, `regulatory.selected_rule_ids`, `regulatory.limits` | Rules exist, but narrative purpose and permit framing need stronger structure. |
| Introduction | Test dates and schedule | Partial | `test_matrix`, run/session evidence | Planned schedule exists; actual report-ready schedule table should be normalized from run timestamps. |
| Plant/source description | Source category, application, engine/unit metadata | Available | `session.source` | Strong source/unit metadata already exists. |
| Plant/source description | Process narrative | Gap | Freeform notes only | Needs structured process description and operating narrative. |
| Plant/source description | Control equipment description | Gap | Not clearly structured | Required for many final reports. |
| Sampling location description | Stack/duct geometry and traverse inputs | Available | `source.stack` | Strong geometry block already exists. |
| Sampling location description | Sampling-location adequacy narrative | Partial | `source.stack` + method basis | Calculable, but no direct narrative / review statement yet. |
| Sampling location description | Figures, schematics, sampling-location drawings | Partial | Static artifacts / docs library | Supports attachment, but no appendix assignment model yet. |
| Summary/results | Pollutant-by-method mapping | Available | `pollutants.prescriptions`, `pollutants.selected` | Strong basis for automated tables. |
| Summary/results | Run matrix | Available | `test_matrix`, run/session evidence | Needs final report rendering model. |
| Summary/results | Run dates/times | Partial | raw/session evidence | Available in evidence but not yet normalized into one report object. |
| Summary/results | Operating conditions by run | Partial | raw samples, source/fuel/exhaust-flow settings | Some values exist; report-grade run summaries still need aggregation logic. |
| Summary/results | Final results and averages | Partial | report pack + DAQ/session outputs | Compact evidence exists, but not yet a full emissions results table template. |
| Summary/results | Compliance narrative | Gap | Not generated | Needs rule-aware narrative layer. |
| Procedures | Methods used and versions | Available | `pollutants.prescriptions`, `fuel.analysis`, method configs | Good structured base. |
| Procedures | Analyzer / sample system description | Partial | `pollutants.prescriptions.comm`, runner config | Technical fields exist; narrative and system diagram references need templating. |
| Procedures | Calibration gas IDs and metadata | Partial | `test_matrix`, pollutant prescription cylinders, cylinder cert artifacts | Needs unified report table and certificate linkage. |
| Procedures | Method deviations / alternatives / approvals | Gap | No dedicated structured field | High-priority narrative gap. |
| QA/QC | Calibration and linearity summaries | Available | `test_matrix`, QA/QC summary, worksteps | Strong current coverage. |
| QA/QC | Pre/post zero-span drift and post-cal review | Available | QA/QC summary, pollutant adjustments, decision review | Strong coverage after recent bias/drift work. |
| QA/QC | Analyzer validity / invalidations | Available | analyzer validity summary | Already exported. |
| QA/QC | Spike recovery / FTIR side-by-side / reference audit | Available | QA/QC summaries and report pack | Strong specialized coverage. |
| QA/QC | QA/QC problems and corrective actions narrative | Partial | Worksteps, review text, notes | Needs narrative collation layer. |
| Appendices | Raw data and supporting records | Available | evidence bundle, raw files, logs, CSV exports | Good evidence basis. |
| Appendices | Field notes, uploaded field documents, site photos | Available | static artifacts | Good evidence basis; needs appendix indexing. |
| Appendices | Chain of custody / lab data | Gap | Not structured for routine generation | Needed when wet chemistry or external lab data apply. |
| Appendices | Agency correspondence / notifications | Gap | Not normalized | Needed for 30/60-day notice workflows and approvals. |
| Appendices | Appendix manifest with titles, paths, hashes, and assignments | Gap | Not normalized | Important for repeatable report generation. |

## Minimum data gaps to close before full report generation

1. Report parties and certification metadata
- Client / facility owner
- Test company legal name
- Responsible official
- Signatory / certification language

2. Process and control description block
- Process narrative
- Control equipment narrative
- Relevant operating variables

3. Method deviation and approval tracking
- Planned deviations
- Field deviations
- Alternative-method approval references
- Impact statement

4. Notification and regulatory correspondence tracking
- Notice of intent date
- Agency contact / office
- Approval / comments dates
- CEDRI / ERT submission status

5. Appendix indexing model
- Appendix letter / section
- Artifact type
- Title
- Source path
- Hash
- Include / exclude flag

6. Run-summary aggregation model
- Actual start/stop timestamps by run
- Operating-condition averages by run
- Final pollutant result table by run and overall average
- Compliance comparison output

## Recommendation

Use the new master template as the report-generation contract, then build one normalized `report_context` object that merges:

- session configuration metadata,
- aggregated run results,
- QA/QC summaries,
- evidence / appendix manifest,
- and regulatory-comparison outputs.

That will let MOLE produce a true EPA-style final report instead of only a compact evidence bundle.
