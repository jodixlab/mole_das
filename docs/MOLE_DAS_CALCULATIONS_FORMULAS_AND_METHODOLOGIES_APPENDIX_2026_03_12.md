# MOLE DAS Calculations, Formulas, and Methodologies Appendix

Document revised: 2026-04-01  
Deployment basis: `2026_03_24_002`  
Runtime identity: `MOLE DAS v10.0.25A - SIM Training Foundations`

## 1. Scope

This appendix summarizes the principal calculations and methodology boundaries implemented in the current build.

It documents software behavior. It does not convert a convenience calculation into a governing-method substitute.

## 2. Core Display Variables

- `C_raw`: observed value from the active frame
- `C_dry`: dry-adjusted value when wet-to-dry logic is valid
- `C_corr`: oxygen-corrected value when correction is enabled and meaningful
- `y_H2O`: wet water fraction
- `Qd`: dry standard exhaust flow
- `R`: heat input
- `Fd`: dry F-factor
- `BHP`: brake horsepower or current power basis

## 3. Wet-to-Dry Normalization

When the raw value is treated as wet and moisture is available:

```text
DF_wd = 1 / (1 - y_H2O)
C_dry = C_raw * DF_wd
```

Current implementation notes:

- if moisture is not available, dry display may remain unavailable
- if the value is already treated as dry, the factor is not applied again
- very high/invalid moisture fractions are suppressed

## 4. Oxygen Correction

When oxygen correction is enabled and the context is stack-like:

```text
C_corr = C_dry * ((20.9 - O2_ref) / (20.9 - O2_meas))
```

Current implementation notes:

- O2 correction is suppressed when the runner determines the context is not appropriate
- O2 itself is not oxygen-corrected

## 5. Fuel Basis and Mixture Properties

The Wizard fuel-analysis page supports either operator-entered data or source-backed defaults.

Current derived mixture behavior includes:

```text
MW_mix  = sum(x_i * MW_i)
HHV_mix = sum(x_i * HHV_i)
LHV_mix = sum(x_i * LHV_i)
Relative_density_air = MW_mix / 28.9625
```

Current traceability behavior:

- the fuel basis profile is named
- the fuel basis source is named
- traceability text is preserved in the fuel-analysis display

## 6. Theoretical Combustion and F-Factors

The build computes theoretical products of combustion and F-factors from the active fuel model.

Representative relationship:

```text
Fd = Dry theoretical flue gas volume / Heat input basis
```

The current runner and diagnostics-only shell use these persisted fuel/combustion outputs to support:

- Method 19 reference display
- heat-input crosswalk logic
- mass-rate calculations

## 7. Method 19 Crosswalk

The current build uses a Method 19-based crosswalk between fuel/heat input and dry standard exhaust flow.

Representative implemented relation:

```text
Qd = R * Fd * (20.9 / (20.9 - O2_dry))
```

Where:

- `Qd` is dry standard exhaust flow
- `R` is heat input
- `Fd` is the active dry F-factor

Current crosswalk outputs may include:

- heat input
- dry standard exhaust flow
- wet-to-dry bookkeeping
- horsepower or utilization references
- back-calculated operational metrics when applicable

## 8. Diagnostics-Specific Boundary

Current diagnostics rule:

- diagnostics mode excludes the Method 2 / `STACK_MEASURED` operator workflow
- diagnostics mode uses Method 19 only

This is a build policy, not just a UI preference.

## 9. Mass-Rate Conversions

The current build supports derived emission-rate outputs such as:

- `lb/hr`
- `g/bhp-hr`
- `tpy`

Those outputs depend on the currently available:

- pollutant concentration basis
- Method 19 crosswalk
- load / heat input basis
- selected units and regulatory view

## 10. Diagnostics Artifact Logic

Diagnostics snapshots and print output are built from live runner state plus:

- weather/site conditions
- fuel basis
- Method 19 inputs / outputs
- diagnostics verification state

Current artifact standard:

- diagnostics output is non-compliance only
- diagnostics output is contingent on technician-performed verification before and after testing
- diagnostics `FAIL` language is reserved for calibration-limit or limit-related conditions

## 11. Trim Panel

The Trim Panel is advisory only.

Current build behavior:

- unavailable windows are blanked
- diagnostics-only unavailable channels remain blank
- trim rendering uses the same live runner state and crosswalk context
- What-If remains reserved for a future build

## 12. Build Verification Standard

Current minimum verification:

```powershell
python -m py_compile MOLE_code\mole_code_das_2026_01_21_v10_0_22_ARCADE_RELEASE.py
python -m py_compile MOLE_code\mole_daq_runner_2026_02_03_v10_0_24_ARCADE_RELEASE.py
python MOLE_code\mole_smoketest.py --root .
MOLE_code\run_release_gate.bat
```

This verification standard should be treated as part of the current build methodology, because packaging defects have repeatedly surfaced as runtime workflow defects.
