param(
    [string]$VisioPath = "D:\codex_environ\2026_03_24_002\2026_03_24_002\figures\mole_das_architecture_and_data_mapping_2026_04_02.vsdx"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Set-ShapeCell {
    param(
        $Shape,
        [string]$Cell,
        [string]$Formula
    )
    try {
        $Shape.CellsU($Cell).FormulaU = $Formula
    } catch {
    }
}

function New-TextBox {
    param(
        $Page,
        [double]$X,
        [double]$Top,
        [double]$Width,
        [double]$Height,
        [string]$Text,
        [string]$Fill = "RGB(255,255,255)",
        [string]$Line = "RGB(60,72,88)",
        [string]$TextColor = "RGB(20,26,32)",
        [double]$FontSize = 10,
        [switch]$Bold,
        [int]$Align = 1,
        [double]$Round = 0.08
    )

    $shape = $Page.DrawRectangle($X, $Top - $Height, $X + $Width, $Top)
    $shape.Text = $Text
    Set-ShapeCell $shape "FillPattern" "1"
    Set-ShapeCell $shape "FillForegnd" $Fill
    Set-ShapeCell $shape "LineColor" $Line
    Set-ShapeCell $shape "LineWeight" "1.2 pt"
    Set-ShapeCell $shape "Rounding" ("{0} in" -f $Round)
    Set-ShapeCell $shape "Char.Color" $TextColor
    Set-ShapeCell $shape "Char.Size" ("{0} pt" -f $FontSize)
    Set-ShapeCell $shape "Para.HorzAlign" ([string]$Align)
    Set-ShapeCell $shape "VerticalAlign" "1"
    Set-ShapeCell $shape "TextBlockLeftMargin" "0.06 in"
    Set-ShapeCell $shape "TextBlockRightMargin" "0.06 in"
    Set-ShapeCell $shape "TextBlockTopMargin" "0.04 in"
    Set-ShapeCell $shape "TextBlockBottomMargin" "0.04 in"
    if ($Bold) {
        Set-ShapeCell $shape "Char.Style" "1"
    }
    return $shape
}

function New-HeaderBox {
    param(
        $Page,
        [double]$X,
        [double]$Top,
        [double]$Width,
        [double]$Height,
        [string]$Text
    )
    return New-TextBox -Page $Page -X $X -Top $Top -Width $Width -Height $Height -Text $Text `
        -Fill "RGB(17,34,46)" -Line "RGB(40,186,93)" -TextColor "RGB(255,255,255)" -FontSize 15 -Bold -Align 1 -Round 0.05
}

function New-SectionBox {
    param(
        $Page,
        [double]$X,
        [double]$Top,
        [double]$Width,
        [double]$Height,
        [string]$Title,
        [string]$Body,
        [string]$Accent = "RGB(40,186,93)",
        [string]$Fill = "RGB(247,250,252)"
    )

    $panel = New-TextBox -Page $Page -X $X -Top $Top -Width $Width -Height $Height -Text "" `
        -Fill $Fill -Line $Accent -TextColor "RGB(20,26,32)" -FontSize 10 -Align 0 -Round 0.06
    New-TextBox -Page $Page -X ($X + 0.06) -Top ($Top - 0.06) -Width ($Width - 0.12) -Height 0.35 -Text $Title `
        -Fill $Accent -Line $Accent -TextColor "RGB(255,255,255)" -FontSize 11 -Bold -Align 1 -Round 0.04 | Out-Null
    New-TextBox -Page $Page -X ($X + 0.08) -Top ($Top - 0.48) -Width ($Width - 0.16) -Height ($Height - 0.56) -Text $Body `
        -Fill $Fill -Line $Fill -TextColor "RGB(20,26,32)" -FontSize 9 -Align 0 -Round 0.01 | Out-Null
    return $panel
}

function New-DecisionBox {
    param(
        $Page,
        [double]$CenterX,
        [double]$CenterY,
        [double]$Size,
        [string]$Text,
        [string]$Fill = "RGB(255,247,234)",
        [string]$Line = "RGB(214,137,16)"
    )

    $half = $Size / 2
    $shape = $Page.DrawRectangle($CenterX - $half, $CenterY - $half, $CenterX + $half, $CenterY + $half)
    $shape.Text = $Text
    Set-ShapeCell $shape "FillPattern" "1"
    Set-ShapeCell $shape "FillForegnd" $Fill
    Set-ShapeCell $shape "LineColor" $Line
    Set-ShapeCell $shape "LineWeight" "1.2 pt"
    Set-ShapeCell $shape "Angle" "45 deg"
    Set-ShapeCell $shape "Rounding" "0 in"
    Set-ShapeCell $shape "Char.Color" "RGB(20,26,32)"
    Set-ShapeCell $shape "Char.Size" "9 pt"
    Set-ShapeCell $shape "Para.HorzAlign" "1"
    Set-ShapeCell $shape "VerticalAlign" "1"
    return $shape
}

function New-Line {
    param(
        $Page,
        [double]$X1,
        [double]$Y1,
        [double]$X2,
        [double]$Y2,
        [string]$Color = "RGB(95,108,122)",
        [double]$Weight = 1.2,
        [switch]$Arrow,
        [switch]$Dashed
    )
    $line = $Page.DrawLine($X1, $Y1, $X2, $Y2)
    Set-ShapeCell $line "LineColor" $Color
    Set-ShapeCell $line "LineWeight" ("{0} pt" -f $Weight)
    if ($Arrow) {
        Set-ShapeCell $line "EndArrow" "13"
    }
    if ($Dashed) {
        Set-ShapeCell $line "LinePattern" "2"
    }
    return $line
}

function New-OrthoFlow {
    param(
        $Page,
        [double]$X1,
        [double]$Y1,
        [double]$X2,
        [double]$Y2,
        [string]$Color = "RGB(95,108,122)",
        [double]$Weight = 1.2,
        [ValidateSet("HV","VH")] [string]$Mode = "HV",
        [switch]$Dashed
    )
    if ($Mode -eq "HV") {
        New-Line -Page $Page -X1 $X1 -Y1 $Y1 -X2 $X2 -Y2 $Y1 -Color $Color -Weight $Weight -Dashed:$Dashed | Out-Null
        return (New-Line -Page $Page -X1 $X2 -Y1 $Y1 -X2 $X2 -Y2 $Y2 -Color $Color -Weight $Weight -Arrow -Dashed:$Dashed)
    }
    New-Line -Page $Page -X1 $X1 -Y1 $Y1 -X2 $X1 -Y2 $Y2 -Color $Color -Weight $Weight -Dashed:$Dashed | Out-Null
    return (New-Line -Page $Page -X1 $X1 -Y1 $Y2 -X2 $X2 -Y2 $Y2 -Color $Color -Weight $Weight -Arrow -Dashed:$Dashed)
}

function New-LineLabel {
    param(
        $Page,
        [double]$X,
        [double]$Top,
        [double]$Width,
        [double]$Height,
        [string]$Text,
        [string]$Fill = "RGB(255,255,255)",
        [string]$Line = "RGB(255,255,255)",
        [string]$TextColor = "RGB(72,84,96)"
    )
    return New-TextBox -Page $Page -X $X -Top $Top -Width $Width -Height $Height -Text $Text `
        -Fill $Fill -Line $Line -TextColor $TextColor -FontSize 8.5 -Align 1 -Round 0.02
}

function Configure-Page {
    param(
        $Page,
        [string]$Name
    )
    $Page.Name = $Name
    Set-ShapeCell $Page.PageSheet "PageWidth" "17 in"
    Set-ShapeCell $Page.PageSheet "PageHeight" "11 in"
    Set-ShapeCell $Page.PageSheet "PrintPageOrientation" "2"
    Set-ShapeCell $Page.PageSheet "UIVisibility" "0"
}

function Build-SystemOverview {
    param($Page)

    New-HeaderBox -Page $Page -X 0.35 -Top 10.65 -Width 16.3 -Height 0.45 -Text "MOLE-DAS Architecture Overview" | Out-Null
    New-TextBox -Page $Page -X 0.35 -Top 10.05 -Width 16.3 -Height 0.30 -Text "Deployment basis: 2026_03_24_002 | Runtime: MOLE DAS v10.0.25A - SIM Training Foundations | Wizard is the authoritative entrypoint" `
        -Fill "RGB(241,245,249)" -Line "RGB(203,213,225)" -TextColor "RGB(51,65,85)" -FontSize 9 -Align 1 | Out-Null

    $wizardBody = @"
Create/load session
Config tabs:
- Source Details
- Pollutants / QA-QC
- Site / Fuel / Regulatory
- FTIR / Sample System
- Hardware / DB Paths
- Documents Library

Intent gate:
- Diagnostic-only
- May Support Compliance

Launch buttons:
- DAQ Runner (Test)
- DAQ Runner (SIM)
"@
    $runtimeBody = @"
Formal DAQ Runner
- Full operator UI
- Live tables + graphs
- QA/QC worksteps
- FTIR side-by-side
- Formal evidence + report pack

Diagnostics Runner
- Same buttons, different shell
- Method 19 only
- Diagnostics verification
- Diagnostics print + trim
- Non-compliance path
"@
    $enginesBody = @"
Shared engines / services
- Modbus acquisition + codecs
- Weather / NOAA site conditions
- Fuel basis + Method 19 crosswalk
- Empirical conditions / mass rates
- FTIR ingest / offsets / worksteps
- Master DB + package inbox
- Method spec engine
- Training scenario simulator
"@
    $dataBody = @"
Workspace roots
- MOLE_code\
- mole_das_data\
- docs\
- config\
- figures\ / mole_assets\

mole_das_data\
- configs / db / sessions
- training / logs / exports
- daq_runs / rule_packs
- inbox_packages / inbox_archive
"@
    $outputsBody = @"
Primary outputs / artifacts
- Session configs and package state
- Raw evidence and QA/QC captures
- FTIR evidence + audit alignment
- Report pack outputs (formal only)
- Diagnostics snapshots / trim advisories
- CSV exports / packaged artifacts
- Logs, smoketest, release gate results
"@
    $externalBody = @"
External boundaries
- Operator / technician
- Sensors + gas cells
- Modbus RTU/TCP hardware
- FTIR PRN / table files
- NOAA/NWS weather services
- Packaged document companions
"@

    New-SectionBox -Page $Page -X 0.45 -Top 9.45 -Width 3.0 -Height 3.1 -Title "Package Entry" -Body @"
Installer / launchers
- INSTALL_MOLE_DAS.bat
- run_wizard_console.bat
- run_wizard_training.bat

Hotfix entrypoint
- run_wizard_hotfix.py

Primary operator start:
Wizard, not runner
"@ -Accent "RGB(40,186,93)" -Fill "RGB(245,253,247)" | Out-Null
    New-SectionBox -Page $Page -X 3.75 -Top 9.45 -Width 3.9 -Height 3.1 -Title "Wizard Control Plane" -Body $wizardBody -Accent "RGB(37,99,235)" -Fill "RGB(239,246,255)" | Out-Null
    New-SectionBox -Page $Page -X 8.0 -Top 9.45 -Width 3.9 -Height 3.1 -Title "Runtime Modes" -Body $runtimeBody -Accent "RGB(214,137,16)" -Fill "RGB(255,247,234)" | Out-Null
    New-SectionBox -Page $Page -X 12.25 -Top 9.45 -Width 4.0 -Height 3.1 -Title "Shared Engines + Integrations" -Body $enginesBody -Accent "RGB(124,58,237)" -Fill "RGB(245,243,255)" | Out-Null
    New-SectionBox -Page $Page -X 0.45 -Top 5.75 -Width 7.8 -Height 3.0 -Title "Data Roots and Package Layout" -Body $dataBody -Accent "RGB(8,145,178)" -Fill "RGB(236,254,255)" | Out-Null
    New-SectionBox -Page $Page -X 8.55 -Top 5.75 -Width 4.95 -Height 3.0 -Title "Artifacts and Evidence" -Body $outputsBody -Accent "RGB(234,88,12)" -Fill "RGB(255,247,237)" | Out-Null
    New-SectionBox -Page $Page -X 13.8 -Top 5.75 -Width 2.45 -Height 3.0 -Title "External Boundaries" -Body $externalBody -Accent "RGB(220,38,38)" -Fill "RGB(254,242,242)" | Out-Null

    New-Line -Page $Page -X1 3.45 -Y1 7.95 -X2 3.75 -Y2 7.95 -Arrow -Color "RGB(40,186,93)" | Out-Null
    New-Line -Page $Page -X1 7.65 -Y1 7.95 -X2 8.0 -Y2 7.95 -Arrow -Color "RGB(37,99,235)" | Out-Null
    New-Line -Page $Page -X1 11.9 -Y1 7.95 -X2 12.25 -Y2 7.95 -Arrow -Color "RGB(214,137,16)" | Out-Null
    New-Line -Page $Page -X1 5.7 -Y1 6.35 -X2 5.7 -Y2 5.75 -Arrow -Color "RGB(8,145,178)" | Out-Null
    New-Line -Page $Page -X1 9.95 -Y1 6.35 -X2 10.95 -Y2 5.75 -Arrow -Color "RGB(234,88,12)" | Out-Null
    New-Line -Page $Page -X1 14.25 -Y1 6.35 -X2 14.95 -Y2 5.75 -Arrow -Color "RGB(220,38,38)" | Out-Null

    New-LineLabel -Page $Page -X 4.65 -Top 7.65 -Width 1.25 -Height 0.2 -Text "session config" -TextColor "RGB(37,99,235)" | Out-Null
    New-LineLabel -Page $Page -X 8.95 -Top 7.65 -Width 1.05 -Height 0.2 -Text "launch mode" -TextColor "RGB(214,137,16)" | Out-Null
    New-LineLabel -Page $Page -X 13.15 -Top 7.65 -Width 1.15 -Height 0.2 -Text "shared services" -TextColor "RGB(124,58,237)" | Out-Null
}

function Build-OperatorProcessTree {
    param($Page)

    New-HeaderBox -Page $Page -X 0.35 -Top 10.65 -Width 16.3 -Height 0.45 -Text "MOLE-DAS Operator Process Tree" | Out-Null
    New-TextBox -Page $Page -X 0.35 -Top 10.05 -Width 16.3 -Height 0.30 -Text "The Wizard owns setup. The same two launch buttons branch into formal or diagnostics runtime based on session intent." `
        -Fill "RGB(241,245,249)" -Line "RGB(203,213,225)" -TextColor "RGB(51,65,85)" -FontSize 9 -Align 1 | Out-Null

    $b1 = New-TextBox -Page $Page -X 0.65 -Top 8.95 -Width 1.9 -Height 0.70 -Text "Install / Repair`nINSTALL_MOLE_DAS.bat" -Fill "RGB(245,253,247)" -Line "RGB(40,186,93)" -FontSize 9 -Bold
    $b2 = New-TextBox -Page $Page -X 2.95 -Top 8.95 -Width 2.15 -Height 0.70 -Text "Launch Wizard`nconsole or training" -Fill "RGB(239,246,255)" -Line "RGB(37,99,235)" -FontSize 9 -Bold
    $b3 = New-TextBox -Page $Page -X 5.5 -Top 8.95 -Width 2.2 -Height 0.70 -Text "Create / Load Session" -Fill "RGB(239,246,255)" -Line "RGB(37,99,235)" -FontSize 9 -Bold
    $b4 = New-TextBox -Page $Page -X 8.1 -Top 8.95 -Width 3.25 -Height 0.70 -Text "Configure tabs`nSource / Pollutants / QA-QC / Site / Fuel / FTIR / Sample System / Hardware / Docs" -Fill "RGB(239,246,255)" -Line "RGB(37,99,235)" -FontSize 8.5 -Bold
    $b5 = New-TextBox -Page $Page -X 11.75 -Top 8.95 -Width 1.95 -Height 0.70 -Text "Save + Apply`nConfig" -Fill "RGB(239,246,255)" -Line "RGB(37,99,235)" -FontSize 9 -Bold
    $b6 = New-TextBox -Page $Page -X 14.05 -Top 8.95 -Width 1.9 -Height 0.70 -Text "Launch`nTest or SIM" -Fill "RGB(255,247,234)" -Line "RGB(214,137,16)" -FontSize 9 -Bold

    New-Line -Page $Page -X1 2.55 -Y1 8.25 -X2 2.95 -Y2 8.25 -Arrow -Color "RGB(95,108,122)" | Out-Null
    New-Line -Page $Page -X1 5.1 -Y1 8.25 -X2 5.5 -Y2 8.25 -Arrow -Color "RGB(95,108,122)" | Out-Null
    New-Line -Page $Page -X1 7.7 -Y1 8.25 -X2 8.1 -Y2 8.25 -Arrow -Color "RGB(95,108,122)" | Out-Null
    New-Line -Page $Page -X1 11.35 -Y1 8.25 -X2 11.75 -Y2 8.25 -Arrow -Color "RGB(95,108,122)" | Out-Null
    New-Line -Page $Page -X1 13.7 -Y1 8.25 -X2 14.05 -Y2 8.25 -Arrow -Color "RGB(95,108,122)" | Out-Null

    New-DecisionBox -Page $Page -CenterX 8.5 -CenterY 6.85 -Size 1.2 -Text "Diagnostic-only?" | Out-Null
    New-OrthoFlow -Page $Page -X1 15.0 -Y1 8.25 -X2 8.5 -Y2 7.15 -Color "RGB(95,108,122)" -Mode "VH" | Out-Null

    New-Line -Page $Page -X1 7.9 -Y1 6.85 -X2 4.0 -Y2 6.85 -Arrow -Color "RGB(37,99,235)" | Out-Null
    New-LineLabel -Page $Page -X 5.55 -Top 7.1 -Width 0.5 -Height 0.2 -Text "NO" -TextColor "RGB(37,99,235)" | Out-Null
    New-Line -Page $Page -X1 9.1 -Y1 6.85 -X2 13.0 -Y2 6.85 -Arrow -Color "RGB(214,137,16)" | Out-Null
    New-LineLabel -Page $Page -X 10.95 -Top 7.1 -Width 0.45 -Height 0.2 -Text "YES" -TextColor "RGB(214,137,16)" | Out-Null

    New-SectionBox -Page $Page -X 0.85 -Top 6.0 -Width 5.7 -Height 3.7 -Title "Formal Path (Diagnostic-only OFF)" -Body @"
1. Same two launch buttons open the full DAQ Runner.
2. Test = live acquisition path.
3. SIM = training / simulation path.
4. Full operator panels stay available:
   - live pollutant + mass tables
   - live graphs
   - QA/QC worksteps
   - FTIR side-by-side / audit
   - report-pack generation
5. Artifacts land in the formal evidence path.
"@ -Accent "RGB(37,99,235)" -Fill "RGB(239,246,255)" | Out-Null

    New-SectionBox -Page $Page -X 10.4 -Top 6.0 -Width 5.7 -Height 3.7 -Title "Diagnostics Path (Diagnostic-only ON)" -Body @"
1. The same Test / SIM buttons open the diagnostics shell.
2. Startup responsibility notice must be confirmed.
3. Diagnostics is Method 19 only.
4. Diagnostics keeps:
   - live tables + graphs
   - weather / fuel basis
   - Method 19 inputs / outputs
   - trim panel
   - diagnostics print panel
5. Diagnostics excludes formal record / report-pack use.
6. If project limits exist:
   - pre-test verification required before acquisition
   - post-test verification required before export
"@ -Accent "RGB(214,137,16)" -Fill "RGB(255,247,234)" | Out-Null

    New-TextBox -Page $Page -X 6.95 -Top 4.35 -Width 3.1 -Height 0.70 -Text "Shared runner buttons`nDAQ Runner (Test) | DAQ Runner (SIM)" `
        -Fill "RGB(245,243,255)" -Line "RGB(124,58,237)" -TextColor "RGB(76,29,149)" -FontSize 9 -Bold | Out-Null

    New-Line -Page $Page -X1 6.55 -Y1 4.0 -X2 6.95 -Y2 4.0 -Arrow -Color "RGB(37,99,235)" | Out-Null
    New-Line -Page $Page -X1 10.05 -Y1 4.0 -X2 10.4 -Y2 4.0 -Arrow -Color "RGB(214,137,16)" | Out-Null

    New-TextBox -Page $Page -X 1.15 -Top 1.95 -Width 5.1 -Height 1.05 -Text "Formal evidence outputs`nraw evidence | QA/QC captures | FTIR evidence | report pack | deterministic session artifacts" `
        -Fill "RGB(236,254,255)" -Line "RGB(8,145,178)" -TextColor "RGB(21,94,117)" -FontSize 9 -Bold | Out-Null
    New-TextBox -Page $Page -X 10.75 -Top 1.95 -Width 5.0 -Height 1.05 -Text "Diagnostics outputs`nverification metadata | diagnostics snapshots | trim advisories | non-compliance artifacts only" `
        -Fill "RGB(254,242,242)" -Line "RGB(220,38,38)" -TextColor "RGB(127,29,29)" -FontSize 9 -Bold | Out-Null

    New-Line -Page $Page -X1 6.55 -Y1 4.0 -X2 3.95 -Y2 4.0 -Arrow -Color "RGB(37,99,235)" | Out-Null
    New-Line -Page $Page -X1 10.05 -Y1 4.0 -X2 12.95 -Y2 4.0 -Arrow -Color "RGB(214,137,16)" | Out-Null
}

function Build-RuntimeDataMapping {
    param($Page)

    New-HeaderBox -Page $Page -X 0.35 -Top 10.65 -Width 16.3 -Height 0.45 -Text "MOLE-DAS Runtime Data Mapping" | Out-Null
    New-TextBox -Page $Page -X 0.35 -Top 10.05 -Width 16.3 -Height 0.30 -Text "Inputs are normalized and evaluated in shared runtime services; the formal and diagnostics shells consume the same session core with different policy gates." `
        -Fill "RGB(241,245,249)" -Line "RGB(203,213,225)" -TextColor "RGB(51,65,85)" -FontSize 9 -Align 1 | Out-Null

    New-SectionBox -Page $Page -X 0.45 -Top 9.45 -Width 4.4 -Height 7.4 -Title "Input Sources" -Body @"
Hardware / live channels
- Modbus RTU / TCP boards
- Gas cells / mapped channels
- Sample system indicators

Reference / ambient
- FTIR PRN / table ingest (formal)
- NOAA / NWS weather pull

Operator / Wizard data
- source details / geometry
- pollutant roster + limits
- QA/QC setup
- site conditions and fuel basis
- regulatory / FTIR settings

Training / SIM
- training_scenario envelopes
- source + fuel aware exhaust values
"@ -Accent "RGB(40,186,93)" -Fill "RGB(245,253,247)" | Out-Null

    New-SectionBox -Page $Page -X 5.35 -Top 9.45 -Width 5.15 -Height 7.4 -Title "Processing and Evaluation" -Body @"
Acquisition / simulation layer
- live poll loop or SIM driver
- channel mapping and comm state

Normalization / transforms
- wet -> dry handling
- O2 correction
- pollutant correction tables
- flow / heat input crosswalks

Method and evaluation engines
- Method 19 basis and mass rates
- empirical conditions
- spike recovery logic
- regulatory_eval / step_eval
- analyzer validity / evidence schemas

Mode-specific policy gates
- formal path: QA/QC + FTIR + report-pack
- diagnostics: notice + verification + diagnostics export
"@ -Accent "RGB(37,99,235)" -Fill "RGB(239,246,255)" | Out-Null

    New-SectionBox -Page $Page -X 11.0 -Top 9.45 -Width 5.65 -Height 7.4 -Title "Outputs and Views" -Body @"
Live operator views
- pollutant table
- mass-rate table
- graphs
- weather / fuel basis
- trim panel

Formal-only views / artifacts
- QA/QC worksteps
- FTIR reference / audit
- report pack
- institutional evidence path

Diagnostics-only views / artifacts
- diagnostics verification
- diagnostics print panel
- non-compliance snapshot exports

Persistent outputs
- session data under mole_das_data\
- exports / logs / packaged artifacts
"@ -Accent "RGB(214,137,16)" -Fill "RGB(255,247,234)" | Out-Null

    New-Line -Page $Page -X1 4.85 -Y1 5.7 -X2 5.35 -Y2 5.7 -Arrow -Color "RGB(95,108,122)" | Out-Null
    New-Line -Page $Page -X1 10.5 -Y1 5.7 -X2 11.0 -Y2 5.7 -Arrow -Color "RGB(95,108,122)" | Out-Null

    New-LineLabel -Page $Page -X 4.55 -Top 6.1 -Width 1.2 -Height 0.22 -Text "acquire / simulate" -TextColor "RGB(37,99,235)" | Out-Null
    New-LineLabel -Page $Page -X 10.65 -Top 6.1 -Width 1.0 -Height 0.22 -Text "render / persist" -TextColor "RGB(214,137,16)" | Out-Null

    New-TextBox -Page $Page -X 5.95 -Top 2.05 -Width 4.0 -Height 1.0 -Text "Mode boundary`nFormal runner and diagnostics runner share the same session core, but diagnostics enforces Method 19 only and excludes the formal record path." `
        -Fill "RGB(254,242,242)" -Line "RGB(220,38,38)" -TextColor "RGB(127,29,29)" -FontSize 9 -Bold | Out-Null
}

function Build-DataEvidenceSchema {
    param($Page)

    New-HeaderBox -Page $Page -X 0.35 -Top 10.65 -Width 16.3 -Height 0.45 -Text "MOLE-DAS Data and Evidence Schema" | Out-Null
    New-TextBox -Page $Page -X 0.35 -Top 10.05 -Width 16.3 -Height 0.30 -Text "Package roots, data stores, and evidence segregation in the active portable runtime." `
        -Fill "RGB(241,245,249)" -Line "RGB(203,213,225)" -TextColor "RGB(51,65,85)" -FontSize 9 -Align 1 | Out-Null

    New-SectionBox -Page $Page -X 0.55 -Top 9.35 -Width 3.0 -Height 3.0 -Title "Workspace Root" -Body @"
2026_03_24_002\

Top-level families
- MOLE_code\
- mole_das_data\
- docs\
- config\
- figures\
- mole_assets\
- build manifest
"@ -Accent "RGB(17,34,46)" -Fill "RGB(248,250,252)" | Out-Null

    New-SectionBox -Page $Page -X 3.95 -Top 9.35 -Width 3.45 -Height 3.0 -Title "MOLE_code\" -Body @"
Entrypoints
- wizard main
- runner main
- launch .bat files

Shared modules
- report pack
- session package
- FTIR helpers
- empirical / spike recovery
- modbus drivers
- master DB repo / init / import
"@ -Accent "RGB(37,99,235)" -Fill "RGB(239,246,255)" | Out-Null

    New-SectionBox -Page $Page -X 7.8 -Top 9.35 -Width 3.65 -Height 3.0 -Title "mole_das_data\" -Body @"
Persistent runtime data
- configs\
- db\
- sessions\
- training\
- logs\
- exports\
- daq_runs\
- rule_packs\
- inbox_packages\
"@ -Accent "RGB(8,145,178)" -Fill "RGB(236,254,255)" | Out-Null

    New-SectionBox -Page $Page -X 11.85 -Top 9.35 -Width 2.1 -Height 3.0 -Title "docs\" -Body @"
Operator references
- technical manual
- calculations appendix
- terms / references
- FTIR companions
- release bulletin
"@ -Accent "RGB(40,186,93)" -Fill "RGB(245,253,247)" | Out-Null

    New-SectionBox -Page $Page -X 14.35 -Top 9.35 -Width 2.0 -Height 3.0 -Title "config / figures / assets" -Body @"
Package metadata
- mole_config.json
- training config
- figures / Visio
- logos / imagery
"@ -Accent "RGB(124,58,237)" -Fill "RGB(245,243,255)" | Out-Null

    New-Line -Page $Page -X1 3.55 -Y1 8.0 -X2 3.95 -Y2 8.0 -Arrow -Color "RGB(95,108,122)" | Out-Null
    New-Line -Page $Page -X1 7.4 -Y1 8.0 -X2 7.8 -Y2 8.0 -Arrow -Color "RGB(95,108,122)" | Out-Null
    New-Line -Page $Page -X1 11.45 -Y1 8.0 -X2 11.85 -Y2 8.0 -Arrow -Color "RGB(95,108,122)" | Out-Null
    New-Line -Page $Page -X1 13.95 -Y1 8.0 -X2 14.35 -Y2 8.0 -Arrow -Color "RGB(95,108,122)" | Out-Null

    New-SectionBox -Page $Page -X 0.55 -Top 5.75 -Width 4.85 -Height 3.1 -Title "DB and Catalog Layer" -Body @"
mole_das_data\db\
- mole_master.sqlite
- package inbox DB
- training\db\ mirrors training state

Schema / tooling
- mole_db_schema_v1.sql
- mole_master_db_repo_v1.py
- init / seed / import tools

Purpose
- source catalog + inventory
- attr persistence
- package inbox records
"@ -Accent "RGB(8,145,178)" -Fill "RGB(236,254,255)" | Out-Null

    New-SectionBox -Page $Page -X 5.7 -Top 5.75 -Width 5.15 -Height 3.1 -Title "Session Roots" -Body @"
Formal sessions
- mole_das_data\sessions\YYYY-MM-DD\...

Training sessions
- mole_das_data\training\sessions\YYYY-MM-DD\...

Stored content
- raw / meta / configs
- exports / snapshots
- QA/QC captures
- FTIR evidence references
"@ -Accent "RGB(37,99,235)" -Fill "RGB(239,246,255)" | Out-Null

    New-SectionBox -Page $Page -X 11.15 -Top 5.75 -Width 5.2 -Height 3.1 -Title "Evidence Segregation" -Body @"
Formal path
- institutional evidence
- report-pack generation
- full QA/QC / FTIR retention

Diagnostics path
- diagnostics verification metadata
- diagnostics TXT / PDF / PNG snapshots
- trim advisories
- excluded from formal record path
"@ -Accent "RGB(220,38,38)" -Fill "RGB(254,242,242)" | Out-Null

    New-SectionBox -Page $Page -X 3.95 -Top 2.1 -Width 8.2 -Height 1.1 -Title "Build / release verification" -Body "Compile -> smoketest -> release gate | logs under mole_das_data\logs | Documents Library surfaces the current doc family in-app" -Accent "RGB(234,88,12)" -Fill "RGB(255,247,237)" | Out-Null
}

function Build-CodeModuleMap {
    param($Page)

    New-HeaderBox -Page $Page -X 0.35 -Top 10.65 -Width 16.3 -Height 0.45 -Text "MOLE-DAS Code and Service Module Map" | Out-Null
    New-TextBox -Page $Page -X 0.35 -Top 10.05 -Width 16.3 -Height 0.30 -Text "Primary files and shared services in the active build." `
        -Fill "RGB(241,245,249)" -Line "RGB(203,213,225)" -TextColor "RGB(51,65,85)" -FontSize 9 -Align 1 | Out-Null

    New-SectionBox -Page $Page -X 0.45 -Top 9.45 -Width 3.35 -Height 3.35 -Title "UI + Launchers" -Body @"
Wizard
- mole_code_das_...ARCADE_RELEASE.py
- run_wizard*.bat
- run_wizard_hotfix.py

Runner
- mole_daq_runner_...ARCADE_RELEASE.py
- run_daq_runner*.bat
"@ -Accent "RGB(40,186,93)" -Fill "RGB(245,253,247)" | Out-Null

    New-SectionBox -Page $Page -X 4.1 -Top 9.45 -Width 3.6 -Height 3.35 -Title "Acquisition + Hardware" -Body @"
- mole_modbus_acq_driver_v1.py
- mole_modbus_poll_v1.py
- mole_modbus_codec_v1.py
- sample-system / gas-cell mapping UI

Purpose:
live channels, comm state, polling, simulator wiring
"@ -Accent "RGB(37,99,235)" -Fill "RGB(239,246,255)" | Out-Null

    New-SectionBox -Page $Page -X 8.0 -Top 9.45 -Width 4.0 -Height 3.35 -Title "Method + Evaluation Engine" -Body @"
mole_method_spec_engine\
- schemas.py
- method_profiles.py
- step_eval.py
- regulatory_eval.py
- analyzer_validity.py
- evidence.py
- training_scenario.py

Purpose:
rules, limits, evidence, SIM envelopes
"@ -Accent "RGB(124,58,237)" -Fill "RGB(245,243,255)" | Out-Null

    New-SectionBox -Page $Page -X 12.3 -Top 9.45 -Width 4.0 -Height 3.35 -Title "Domain Helpers" -Body @"
- mole_empirical_conditions_v1.py
- mole_spike_recovery_v1.py
- mole_ftir_reference_v1.py
- mole_ftir_offset_recommendations_v1.py
- mole_ftir_method_worksteps_v1.py
- mole_report_pack_v1.py
"@ -Accent "RGB(214,137,16)" -Fill "RGB(255,247,234)" | Out-Null

    New-SectionBox -Page $Page -X 0.45 -Top 5.6 -Width 4.1 -Height 3.1 -Title "Session + Packaging" -Body @"
- mole_session_package_...py
- mole_packager.py
- mole_csv_export_v1.py
- mole_package_inbox_db_v1.py

Purpose:
session persistence, deterministic packaging,
CSV/export surfaces, inbox packages
"@ -Accent "RGB(8,145,178)" -Fill "RGB(236,254,255)" | Out-Null

    New-SectionBox -Page $Page -X 4.85 -Top 5.6 -Width 4.2 -Height 3.1 -Title "Catalog + DB Tooling" -Body @"
- mole_db_schema_v1.sql
- mole_master_db_repo_v1.py
- mole_master_db_init_v1.py
- mole_master_db_seed_default_v1.py
- mole_master_db_import_csv_v1.py

Purpose:
catalog, inventory, attrs, import/seed
"@ -Accent "RGB(8,145,178)" -Fill "RGB(236,254,255)" | Out-Null

    New-SectionBox -Page $Page -X 9.35 -Top 5.6 -Width 3.25 -Height 3.1 -Title "Quality + Release" -Body @"
- mole_preflight.py
- mole_smoketest.py
- mole_release_gate.py
- RELEASE_GATE_README.txt

Purpose:
sanity checks, packaging verification,
release readiness
"@ -Accent "RGB(220,38,38)" -Fill "RGB(254,242,242)" | Out-Null

    New-SectionBox -Page $Page -X 12.9 -Top 5.6 -Width 3.4 -Height 3.1 -Title "Reference Data" -Body @"
- mole_methods_db.json
- mole_instruments_db.json
- mole_cylinders_db.json
- docs + figures

Purpose:
runtime defaults, references,
operator companion docs
"@ -Accent "RGB(234,88,12)" -Fill "RGB(255,247,237)" | Out-Null

    New-Line -Page $Page -X1 3.8 -Y1 7.7 -X2 4.1 -Y2 7.7 -Arrow -Color "RGB(95,108,122)" | Out-Null
    New-Line -Page $Page -X1 7.7 -Y1 7.7 -X2 8.0 -Y2 7.7 -Arrow -Color "RGB(95,108,122)" | Out-Null
    New-Line -Page $Page -X1 12.0 -Y1 7.7 -X2 12.3 -Y2 7.7 -Arrow -Color "RGB(95,108,122)" | Out-Null

    New-OrthoFlow -Page $Page -X1 1.65 -Y1 6.15 -X2 1.65 -Y2 5.6 -Color "RGB(40,186,93)" -Mode "HV" | Out-Null
    New-OrthoFlow -Page $Page -X1 6.0 -Y1 6.15 -X2 6.0 -Y2 5.6 -Color "RGB(37,99,235)" -Mode "HV" | Out-Null
    New-OrthoFlow -Page $Page -X1 10.95 -Y1 6.15 -X2 10.95 -Y2 5.6 -Color "RGB(124,58,237)" -Mode "HV" | Out-Null
    New-OrthoFlow -Page $Page -X1 14.6 -Y1 6.15 -X2 14.6 -Y2 5.6 -Color "RGB(214,137,16)" -Mode "HV" | Out-Null

    New-TextBox -Page $Page -X 4.5 -Top 2.2 -Width 7.0 -Height 1.0 -Text "Core dependency pattern`nWizard and Runner orchestrate most user-facing behavior. Shared helper modules hold acquisition, evaluation, persistence, FTIR, packaging, and build verification logic." `
        -Fill "RGB(248,250,252)" -Line "RGB(148,163,184)" -TextColor "RGB(51,65,85)" -FontSize 9 -Bold | Out-Null
}

function Build-SessionSchema {
    param($Page)

    New-HeaderBox -Page $Page -X 0.35 -Top 10.65 -Width 16.3 -Height 0.45 -Text "MOLE-DAS Session Config and SQLite Schema" | Out-Null
    New-TextBox -Page $Page -X 0.35 -Top 10.05 -Width 16.3 -Height 0.30 -Text "High-value persisted entities in the Wizard/session package layer and the catalog SQLite layer." `
        -Fill "RGB(241,245,249)" -Line "RGB(203,213,225)" -TextColor "RGB(51,65,85)" -FontSize 9 -Align 1 | Out-Null

    New-SectionBox -Page $Page -X 0.45 -Top 9.45 -Width 3.45 -Height 6.8 -Title "Session Config JSON" -Body @"
Wizard-owned session state
- job_id / project identity
- session_mode
- source details / geometry
- pollutant roster + limits
- QA/QC setup
- fuel analysis / defaults
- regulatory / FTIR config
- sample-system mapping
- runner UI / mode flags

Saved under:
mole_das_data\configs\
and packaged session roots
"@ -Accent "RGB(37,99,235)" -Fill "RGB(239,246,255)" | Out-Null

    New-SectionBox -Page $Page -X 4.35 -Top 9.45 -Width 3.65 -Height 6.8 -Title "Session Package / Artifact Layer" -Body @"
Session package content
- raw\
- meta\
- exports\
- config snapshots
- diagnostics snapshots
- CSV / artifact exports

Formal additions
- QA/QC captures
- FTIR evidence
- report-pack outputs

Training mirrors
- training\sessions\
"@ -Accent "RGB(8,145,178)" -Fill "RGB(236,254,255)" | Out-Null

    New-SectionBox -Page $Page -X 8.45 -Top 9.45 -Width 3.75 -Height 6.8 -Title "Catalog SQLite" -Body @"
mole_master.sqlite

Core entity families
- manufacturers
- models
- inventory instances
- instance attrs
- package inbox records

Tooling
- schema v1 SQL
- repo / init / seed / import

Purpose
- source selection defaults
- inventory binding
- attr-backed enrichment
"@ -Accent "RGB(40,186,93)" -Fill "RGB(245,253,247)" | Out-Null

    New-SectionBox -Page $Page -X 12.6 -Top 9.45 -Width 3.65 -Height 6.8 -Title "Runtime / Evaluation State" -Body @"
Transient + persisted state
- live channels / comm state
- SIM envelopes
- weather snapshots
- Method 19 inputs / outputs
- diagnostics verification
- trim / advisory outputs

Policy boundary
- formal evidence path
- diagnostics non-compliance path
"@ -Accent "RGB(214,137,16)" -Fill "RGB(255,247,234)" | Out-Null

    New-Line -Page $Page -X1 3.9 -Y1 6.2 -X2 4.35 -Y2 6.2 -Arrow -Color "RGB(95,108,122)" | Out-Null
    New-Line -Page $Page -X1 8.0 -Y1 6.2 -X2 8.45 -Y2 6.2 -Arrow -Color "RGB(95,108,122)" | Out-Null
    New-Line -Page $Page -X1 12.2 -Y1 6.2 -X2 12.6 -Y2 6.2 -Arrow -Color "RGB(95,108,122)" | Out-Null

    New-LineLabel -Page $Page -X 3.98 -Top 6.48 -Width 0.95 -Height 0.22 -Text "package build" -TextColor "RGB(8,145,178)" | Out-Null
    New-LineLabel -Page $Page -X 8.05 -Top 6.48 -Width 0.9 -Height 0.22 -Text "catalog lookup" -TextColor "RGB(40,186,93)" | Out-Null
    New-LineLabel -Page $Page -X 12.22 -Top 6.48 -Width 0.95 -Height 0.22 -Text "runtime consume" -TextColor "RGB(214,137,16)" | Out-Null

    New-TextBox -Page $Page -X 1.25 -Top 2.35 -Width 5.2 -Height 1.2 -Text "Representative session package flow`nWizard session config -> Save + Apply -> session package / config snapshot -> Runner consumes same session core -> artifacts land in formal or diagnostics branch" `
        -Fill "RGB(248,250,252)" -Line "RGB(148,163,184)" -TextColor "RGB(51,65,85)" -FontSize 9 -Bold | Out-Null
    New-TextBox -Page $Page -X 8.9 -Top 2.35 -Width 5.9 -Height 1.2 -Text "Representative SQLite flow`nCatalog governance -> import / seed -> inventory + attrs -> Wizard source binding / fuel hints / defaults -> runtime enrichment and source-aware SIM behavior" `
        -Fill "RGB(248,250,252)" -Line "RGB(148,163,184)" -TextColor "RGB(51,65,85)" -FontSize 9 -Bold | Out-Null
}

function Build-HardwareSampleSystem {
    param($Page)

    New-HeaderBox -Page $Page -X 0.35 -Top 10.65 -Width 16.3 -Height 0.45 -Text "MOLE-DAS Hardware, Sample System, and Gas Cell Mapping" | Out-Null
    New-TextBox -Page $Page -X 0.35 -Top 10.05 -Width 16.3 -Height 0.30 -Text "Physical sample path, hardware interfaces, channel mapping, and DAQ consumption path." `
        -Fill "RGB(241,245,249)" -Line "RGB(203,213,225)" -TextColor "RGB(51,65,85)" -FontSize 9 -Align 1 | Out-Null

    New-SectionBox -Page $Page -X 0.5 -Top 8.95 -Width 1.75 -Height 1.2 -Title "Source" -Body "Stack / engine exhaust" -Accent "RGB(220,38,38)" -Fill "RGB(254,242,242)" | Out-Null
    New-SectionBox -Page $Page -X 2.55 -Top 8.95 -Width 1.65 -Height 1.2 -Title "Probe" -Body "sample takeoff" -Accent "RGB(220,38,38)" -Fill "RGB(254,242,242)" | Out-Null
    New-SectionBox -Page $Page -X 4.55 -Top 8.95 -Width 1.95 -Height 1.2 -Title "Water Knockout" -Body "condensate removal" -Accent "RGB(8,145,178)" -Fill "RGB(236,254,255)" | Out-Null
    New-SectionBox -Page $Page -X 6.85 -Top 8.95 -Width 1.95 -Height 1.2 -Title "Particulate Filter" -Body "sample cleanup" -Accent "RGB(40,186,93)" -Fill "RGB(245,253,247)" | Out-Null
    New-SectionBox -Page $Page -X 9.2 -Top 8.95 -Width 1.8 -Height 1.2 -Title "3-Way Bias Valve" -Body "switch / inject" -Accent "RGB(148,163,184)" -Fill "RGB(248,250,252)" | Out-Null
    New-SectionBox -Page $Page -X 11.35 -Top 8.95 -Width 1.8 -Height 1.2 -Title "Sample Pump" -Body "pull sample" -Accent "RGB(40,186,93)" -Fill "RGB(245,253,247)" | Out-Null
    New-SectionBox -Page $Page -X 13.55 -Top 8.95 -Width 2.1 -Height 1.2 -Title "Gas Cells" -Body "cell 1..4 | P1 / P2" -Accent "RGB(214,137,16)" -Fill "RGB(255,247,234)" | Out-Null

    New-Line -Page $Page -X1 2.25 -Y1 7.9 -X2 2.55 -Y2 7.9 -Arrow -Color "RGB(220,38,38)" -Weight 2.0 | Out-Null
    New-Line -Page $Page -X1 4.2 -Y1 7.9 -X2 4.55 -Y2 7.9 -Arrow -Color "RGB(220,38,38)" -Weight 2.0 | Out-Null
    New-Line -Page $Page -X1 6.5 -Y1 7.9 -X2 6.85 -Y2 7.9 -Arrow -Color "RGB(220,38,38)" -Weight 2.0 | Out-Null
    New-Line -Page $Page -X1 8.8 -Y1 7.9 -X2 9.2 -Y2 7.9 -Arrow -Color "RGB(220,38,38)" -Weight 2.0 | Out-Null
    New-Line -Page $Page -X1 11.0 -Y1 7.9 -X2 11.35 -Y2 7.9 -Arrow -Color "RGB(220,38,38)" -Weight 2.0 | Out-Null
    New-Line -Page $Page -X1 13.15 -Y1 7.9 -X2 13.55 -Y2 7.9 -Arrow -Color "RGB(220,38,38)" -Weight 2.0 | Out-Null

    New-SectionBox -Page $Page -X 4.15 -Top 6.95 -Width 1.9 -Height 1.1 -Title "RATA Gas" -Body "reference line" -Accent "RGB(214,137,16)" -Fill "RGB(255,247,234)" | Out-Null
    New-SectionBox -Page $Page -X 6.55 -Top 6.95 -Width 2.05 -Height 1.1 -Title "Calibration Gas" -Body "inject via valve" -Accent "RGB(40,186,93)" -Fill "RGB(245,253,247)" | Out-Null
    New-Line -Page $Page -X1 5.10 -Y1 5.85 -X2 5.10 -Y2 5.35 -Color "RGB(214,137,16)" -Weight 1.6 | Out-Null
    New-Line -Page $Page -X1 5.10 -Y1 5.35 -X2 9.05 -Y2 5.35 -Arrow -Color "RGB(214,137,16)" -Weight 1.6 | Out-Null
    New-OrthoFlow -Page $Page -X1 8.60 -Y1 6.40 -X2 10.10 -Y2 7.75 -Color "RGB(40,186,93)" -Weight 1.6 -Mode "HV" | Out-Null
    New-LineLabel -Page $Page -X 6.05 -Top 5.62 -Width 1.55 -Height 0.22 -Text "reference spike line" -TextColor "RGB(214,137,16)" | Out-Null
    New-LineLabel -Page $Page -X 8.72 -Top 6.70 -Width 0.72 -Height 0.22 -Text "cal inject" -TextColor "RGB(40,186,93)" | Out-Null

    New-SectionBox -Page $Page -X 0.65 -Top 4.7 -Width 3.35 -Height 2.0 -Title "Hardware / Comms Layer" -Body @"
Profiles / boards
- active hardware profile
- Modbus RTU / TCP
- channel address map
- comm verification

P-port lights follow mapped-channel comm state
"@ -Accent "RGB(37,99,235)" -Fill "RGB(239,246,255)" | Out-Null

    New-SectionBox -Page $Page -X 4.35 -Top 4.7 -Width 3.8 -Height 2.0 -Title "Gas Cell Mapping UI" -Body @"
4 gas cells x 2 ports
- P1 / P2 assign to sensor channel
- gas / range / sensitivity metadata
- Apply Gas Cell Mapping

Stored with session package
"@ -Accent "RGB(124,58,237)" -Fill "RGB(245,243,255)" | Out-Null

    New-SectionBox -Page $Page -X 8.55 -Top 4.7 -Width 3.9 -Height 2.0 -Title "Runner Consumption" -Body @"
Formal / diagnostics runner consume:
- live channel values
- comm state
- weather / fuel basis
- Method 19 and mass-rate logic
- graphs / tables / trim / print
"@ -Accent "RGB(214,137,16)" -Fill "RGB(255,247,234)" | Out-Null

    New-SectionBox -Page $Page -X 12.85 -Top 4.7 -Width 3.35 -Height 2.0 -Title "Artifacts and Views" -Body @"
- Sample System tab
- PNG preview / export
- diagnostics print artifacts
- session snapshots
- operator-facing digital twin
"@ -Accent "RGB(220,38,38)" -Fill "RGB(254,242,242)" | Out-Null

    New-Line -Page $Page -X1 3.95 -Y1 3.7 -X2 4.35 -Y2 3.7 -Arrow -Color "RGB(37,99,235)" | Out-Null
    New-Line -Page $Page -X1 8.15 -Y1 3.7 -X2 8.55 -Y2 3.7 -Arrow -Color "RGB(124,58,237)" | Out-Null
    New-Line -Page $Page -X1 12.45 -Y1 3.7 -X2 12.85 -Y2 3.7 -Arrow -Color "RGB(214,137,16)" | Out-Null
}

function Ensure-PageCount {
    param(
        $Document,
        [string[]]$Names
    )
    while ($Document.Pages.Count -lt $Names.Count) {
        [void]$Document.Pages.Add()
    }
    while ($Document.Pages.Count -gt $Names.Count) {
        $Document.Pages.Item($Document.Pages.Count).Delete()
    }
    for ($i = 1; $i -le $Names.Count; $i++) {
        $page = $Document.Pages.Item($i)
        Configure-Page -Page $page -Name $Names[$i - 1]
        for ($s = $page.Shapes.Count; $s -ge 1; $s--) {
            $page.Shapes.Item($s).Delete()
        }
    }
}

$visio = $null
$doc = $null
try {
    if (-not (Test-Path -LiteralPath $VisioPath)) {
        throw "Visio file not found: $VisioPath"
    }

    $visio = New-Object -ComObject Visio.Application
    $visio.Visible = $false
    $visio.AlertResponse = 7
    $doc = $visio.Documents.Open($VisioPath)

    $pageNames = @(
        "01 System Overview",
        "02 Operator Process Tree",
        "03 Runtime Data Mapping",
        "04 Data and Evidence Schema",
        "05 Code Module Map",
        "06 Session Config Schema",
        "07 Hardware and Sample System"
    )
    Ensure-PageCount -Document $doc -Names $pageNames

    Build-SystemOverview -Page $doc.Pages.Item(1)
    Build-OperatorProcessTree -Page $doc.Pages.Item(2)
    Build-RuntimeDataMapping -Page $doc.Pages.Item(3)
    Build-DataEvidenceSchema -Page $doc.Pages.Item(4)
    Build-CodeModuleMap -Page $doc.Pages.Item(5)
    Build-SessionSchema -Page $doc.Pages.Item(6)
    Build-HardwareSampleSystem -Page $doc.Pages.Item(7)

    $doc.Save()
    Write-Output "UPDATED_VSDX $VisioPath"
    $doc.Pages | ForEach-Object {
        Write-Output ("PAGE`t{0}`tShapes={1}" -f $_.Name, $_.Shapes.Count)
    }
} finally {
    if ($doc -ne $null) {
        try { $doc.Close() } catch {}
    }
    if ($visio -ne $null) {
        try { $visio.Quit() } catch {}
    }
}
