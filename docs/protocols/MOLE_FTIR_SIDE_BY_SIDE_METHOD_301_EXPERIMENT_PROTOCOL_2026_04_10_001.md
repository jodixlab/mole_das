# MOLE and FTIR Side-by-Side Experimental Protocol

Document ID: `MOLE_FTIR_SIDE_BY_SIDE_METHOD_301_2026_04_10_001`  
Revision: `0`  
Effective date: `2026-04-10`  
Prepared by: `Codex draft for technical review`  
Purpose: `Field comparison protocol for evaluating MOLE hardware performance against FTIR using the comparison framework in EPA Method 301`

## Document Control

| Item | Value |
| --- | --- |
| Candidate method | MOLE hardware |
| Comparator method | FTIR |
| Governing validation framework | EPA Method 301 |
| Intended outcome | Determine source-specific acceptability of MOLE measurements relative to FTIR |
| Source applicability | Single tested source unless broader validation is separately demonstrated |

## Important Technical Note

This protocol is structured to follow the comparison framework in EPA Method 301 for a candidate method versus a validated method. A formal Method 301 comparison requires six quadruplicate, collocated sample sets when comparing a candidate method to a validated method. If the field arrangement does not produce that structure, the study should be described as a side-by-side performance comparison informed by Method 301 rather than a full Method 301 validation.

## 1. Scope and Objectives

<!-- HELP_ID: wizard.validation.mode -->
### 1.1 Scope

This experiment evaluates the performance of the MOLE hardware against an FTIR operated at the same source, at the same sampling location, and over the same operating period. The comparison is limited to analytes measured by both systems on the same reporting basis and unit system.

The experiment is intended to determine:

- whether the MOLE hardware exhibits statistically significant bias relative to FTIR;
- the magnitude of any relative bias;
- whether MOLE precision is acceptable relative to the FTIR comparator; and
- whether MOLE data are acceptable without correction, acceptable only with a source-specific correction factor, or unacceptable under the tested conditions.

### 1.2 Objectives

The objectives of the experiment are to:

- collect collocated side-by-side MOLE and FTIR measurements under representative operating conditions;
- align the data into comparison windows that are technically defensible and reproducible;
- calculate Method 301 comparison statistics for each target analyte;
- document all exclusions, deviations, and adjustments applied during analysis; and
- produce a final field validation package suitable for technical review.

### 1.3 Measurement Basis

The following conditions apply to all comparison calculations:

- only analytes measured by both instruments will be included;
- both systems must be compared on the same unit basis;
- wet/dry basis and oxygen-correction basis must be normalized before comparison;
- purge periods will not be included in the comparison dataset; and
- only valid comparison windows will be admitted to the final calculation set.

## 2. Roles and Responsibilities

### 2.1 Emissions Technician

The Emissions Technician shall:

- install and operate the MOLE and FTIR sampling systems in the field;
- perform and document all instrument readiness checks, leak checks, calibrations, and operational checks;
- execute the field sampling schedule exactly as written;
- record all run start and stop times, purge periods, interruptions, calibration actions, and field observations; and
- preserve all raw field data and notes without unauthorized modification.

### 2.2 Lead Scientist

The Lead Scientist shall:

- define the field procedure, analyte list, reporting basis, and timestamp alignment method;
- confirm that the FTIR configuration is an appropriate validated comparator for the analytes and source conditions under study;
- oversee field execution, technical deviations, and data acceptance decisions;
- direct the statistical analysis and determine the acceptability of the candidate method; and
- approve the final technical conclusion.

### 2.3 Peer Scientist

The Peer Scientist shall:

- independently review the experimental design, field package, processed dataset, and final calculations;
- verify that data exclusions and adjustments are technically justified and documented;
- verify that Method 301 calculations were performed correctly; and
- issue an independent technical review statement on the data package.

## 3. Terms and Definitions

| Term | Definition |
| --- | --- |
| Candidate test method | The method being evaluated. In this protocol, the candidate method is the MOLE hardware. |
| Validated method | The comparison method already accepted for the analytes and application. In this protocol, the comparator is the FTIR configuration. |
| Collocated | Collected at essentially the same sampling location and as close as possible in time. |
| Comparison window | The exact time interval used to average and compare MOLE and FTIR results. |
| Purge interval | A non-comparison period during which the MOLE sample path is cleared and comparison data are not collected. |
| Quadruplicate sampling set | A set of four replicate measurements collected as close as possible in time and location when comparing a candidate method to a validated method. |
| Bias | The mean difference between the candidate method and the validated method. |
| Relative bias | Bias expressed relative to the mean validated-method result. |
| Precision | Variability of repeated measurements. |
| F-test | The statistical comparison used to determine whether candidate-method precision differs significantly from validated-method precision. |
| t-test | The statistical comparison used to determine whether the mean difference between methods is significant. |
| Correction factor | A source-specific factor used to correct future candidate-method data when relative bias is greater than 10 percent but less than or equal to 30 percent. |
| Valid data window | A comparison interval meeting timing, analyzer status, and data-completeness requirements. |
<!-- HELP_ID: wizard.validation.master_clock -->
| Timestamp master clock | The authoritative time reference used to align MOLE and FTIR data streams. |
| Rejected data | Data excluded from the Method 301 comparison set for documented technical reasons. |

## 4. Procedure

### 4.1 Pre-Test Preparation

Before testing begins:

- confirm target analytes, units, wet/dry basis, and oxygen-correction basis;
- synchronize MOLE, FTIR, and field log clocks to one timestamp master clock;
- confirm the collocated sampling arrangement;
- document sample path configuration, conditioners, filters, dryers, and any other hardware that could affect equivalence;
- perform all required pre-test calibrations and readiness checks; and
- record source operating status prior to the first comparison window.

### 4.2 Run Structure

The FTIR will perform one continuous three-hour test run. During that same three-hour interval, the MOLE hardware will operate at repeated 20-minute comparison windows separated by 5-minute purge intervals.

For one three-hour FTIR run, the planned schedule is:

| Sequence | Time Block | Activity |
| --- | --- | --- |
| 1 | `0-15 min` | Stabilization, timestamp confirmation, final readiness check |
| 2 | `15-35 min` | Comparison window 1 |
| 3 | `35-40 min` | MOLE purge |
| 4 | `40-60 min` | Comparison window 2 |
| 5 | `60-65 min` | MOLE purge |
| 6 | `65-85 min` | Comparison window 3 |
| 7 | `85-90 min` | MOLE purge |
| 8 | `90-110 min` | Comparison window 4 |
| 9 | `110-115 min` | MOLE purge |
| 10 | `115-135 min` | Comparison window 5 |
| 11 | `135-140 min` | MOLE purge |
| 12 | `140-160 min` | Comparison window 6 |
| 13 | `160-180 min` | Post-run checks and closeout |

### 4.3 Field Data Collection Requirements

During field acquisition:

- FTIR may collect continuously throughout the full three-hour run;
- only the defined MOLE comparison windows will be used for side-by-side statistical comparison;
- purge periods shall be excluded from both systems in the comparison dataset;
- field notes shall document any analyzer interruption, source upset, or quality issue affecting a comparison window; and
- any invalid comparison window shall be marked immediately with the technical reason for exclusion.

### 4.4 Method 301 Comparison Structure

EPA Method 301 requires six quadruplicate sets when comparing a candidate method to a validated method. Therefore, the field design should support six valid comparison sets, each consisting of properly paired and collocated measurements from the candidate and validated methods.

If the deployed field configuration does not create six quadruplicate sets, the study may still provide strong side-by-side evidence, but the final report shall clearly distinguish that study from a full Method 301 validation.

<!-- HELP_ID: runner.ftir.apply_selected_sweep -->
### 4.5 Data Normalization and Timestamp Alignment

Post-processing shall be performed as follows:

- preserve native raw MOLE and FTIR files without modification;
- convert all timestamps to a common timezone and timestamp format;
- define one comparison ledger with window start, window end, purge intervals, analyte basis, and validity flag;
- average FTIR data only over the exact comparison windows matched to MOLE sampling periods;
- exclude purge periods from all comparison averages;
- normalize all analytes to a common reporting basis before comparison;
- separate raw, filtered, and averaged datasets as distinct deliverables; and
- document all exclusions, replacements, and adjustments in an auditable log.

<!-- HELP_ID: runner.ftir.exclude_selected -->
### 4.6 Data Management Deliverables

The test package shall include:

- field log;
- clock synchronization record;
- calibration and readiness records;
- raw MOLE data;
- raw FTIR data;
- comparison-window ledger;
- processed comparison dataset;
- calculation workbook or equivalent statistical record;
- rejected-data log; and
- peer review record.

### 4.7 Recommended Comparison Data Table

| Set No. | Window Start | Window End | MOLE Average | FTIR Average | Basis / Units | Valid? | Exclusion Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 |  |  |  |  |  |  |  |
| 2 |  |  |  |  |  |  |  |
| 3 |  |  |  |  |  |  |  |
| 4 |  |  |  |  |  |  |  |
| 5 |  |  |  |  |  |  |  |
| 6 |  |  |  |  |  |  |  |

<!-- HELP_ID: runner.ftir.accept_selected_set -->
## 5. Acceptance Criteria

Acceptance criteria shall follow EPA Method 301 for comparison of a candidate method to a validated method.

### 5.1 Bias

- compute the t-statistic for the mean difference between MOLE and FTIR;
- for six quadruplicate sets, use a two-sided critical t-value of `2.571` at the 95 percent confidence level;
- if calculated `t <= 2.571`, bias is not statistically significant and the bias criterion is acceptable;
- if calculated `t > 2.571`, compute relative bias;
- if relative bias is `<= 10 percent`, the candidate method is acceptable;
- if relative bias is `> 10 percent` and `<= 30 percent`, the candidate method is acceptable only on a source-specific basis with a correction factor;
- if relative bias is `> 30 percent`, the candidate method is unacceptable; and
- if the source-specific correction factor falls outside `0.70 to 1.30`, the candidate method is unacceptable.

### 5.2 Precision

- compare candidate-method variance to validated-method variance using the Method 301 F-test;
- for six quadruplicate sets, use the 95 percent upper critical F-value of `4.28` for `F(6,6)`;
- if calculated `F <= 4.28`, precision is acceptable; and
- if calculated `F > 4.28`, the candidate method is unacceptable due to significant precision difference.

### 5.3 General Data Acceptance Conditions

- all accepted sets must be collocated and time-aligned;
- all accepted sets must be compared on the same reporting basis and units;
- all excluded data must have a documented technical reason; and
- each analyte shall be evaluated independently if method performance differs by analyte.

## 6. Conclusion

This experiment is intended to determine whether the MOLE hardware performs comparably to an FTIR under representative source operating conditions using the comparison framework in EPA Method 301.

The final conclusion shall be stated analyte-by-analyte and shall follow this logic:

- if bias is not statistically significant, or relative bias is `<= 10 percent`, and the precision criterion is met, conclude that the MOLE hardware is acceptable for the tested analyte under the tested source conditions;
- if relative bias is `> 10 percent` and `<= 30 percent`, and the precision criterion is met, conclude that the MOLE hardware is acceptable only on a source-specific basis with the documented correction factor; and
- if relative bias is `> 30 percent`, if the correction factor is outside `0.70 to 1.30`, or if the precision criterion fails, conclude that the MOLE hardware is not validated by this experiment for the tested analyte and conditions.

If the field setup does not satisfy the Method 301 requirement for six quadruplicate, collocated sets, the final report shall explicitly state that the exercise was a side-by-side comparative performance study informed by Method 301 rather than a full Method 301 validation.

## Signatures

| Role | Name | Signature | Date |
| --- | --- | --- | --- |
| Lead Scientist |  |  |  |
| Emissions Technician |  |  |  |
| Peer Scientist |  |  |  |

## Appendices

| Appendix | Title | Description |
| --- | --- | --- |
| A | Field Sampling Schedule | Final run schedule, timing map, and comparison-window ledger |
| B | Calibration and Readiness Records | Pre-test and post-test checks for both systems |
| C | Raw Data Inventory | Native MOLE and FTIR output files |
| D | Processed Comparison Dataset | Time-aligned and basis-normalized data used in calculations |
| E | Method 301 Calculation Package | Bias, relative bias, correction factor, and F-test calculations |
| F | Rejected Data Log | Technical basis for excluded windows or analytes |
| G | Peer Review Record | Reviewer comments and final disposition |

## References

1. EPA Method 301, *Field Validation of Pollutant Measurement Methods from Various Waste Media*, October 7, 2020.
2. Official EPA PDF: `https://www.epa.gov/sites/default/files/2020-12/documents/method_301_0.pdf`
