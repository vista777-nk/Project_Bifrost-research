param(
    [Parameter(Mandatory = $true)][string]$InputNetlist,
    [Parameter(Mandatory = $true)][string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$app = $null
$circuit = $null
$stage = 'paths'

function Set-ProbeStage([string]$Name) {
    $script:stage = $Name
    [Console]::Error.WriteLine($Name)
    if ($script:directory) {
        Add-Content -LiteralPath (Join-Path $script:directory 'probe-stage.txt') -Value $Name -Encoding UTF8
    }
}

function Assert-ComSuccess($Object) {
    if (-not [string]::IsNullOrWhiteSpace([string]$Object.LastErrorMessage)) {
        throw [string]$Object.LastErrorMessage
    }
}

function Disconnect-Probe {
    if ($null -ne $script:circuit) {
        try { $script:circuit.StopSimulation() } catch { }
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($script:circuit)
        $script:circuit = $null
    }
    if ($null -ne $script:app) {
        try { $script:app.Disconnect() } catch { }
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($script:app)
        $script:app = $null
    }
}

try {
    if ([Environment]::Is64BitProcess) { throw 'Run this probe with 32-bit Windows PowerShell.' }
    $inputPath = (Get-Item -LiteralPath $InputNetlist).FullName
    [void][IO.Directory]::CreateDirectory([IO.Path]::GetFullPath($OutputDirectory))
    $directory = (Get-Item -LiteralPath $OutputDirectory).FullName
    $initial = Join-Path $directory 'divider-initial.ms14'
    $edited = Join-Path $directory 'divider-edited.ms14'
    $image = Join-Path $directory 'divider.png'
    foreach ($path in @($initial, $edited, $image)) {
        if (Test-Path -LiteralPath $path) { throw "Probe never overwrites an existing file: $path" }
    }
    Set-ProbeStage 'connect'
    $app = New-Object -ComObject MultisimInterface.MultisimApp
    $app.Connect()
    Assert-ComSuccess $app
    Set-ProbeStage 'import_cir'
    $circuit = $app.OpenFile($inputPath)
    Assert-ComSuccess $app
    if ($null -eq $circuit) { throw 'OpenFile returned no circuit.' }
    Set-ProbeStage 'enumerate_native_components'
    $components = @($circuit.EnumComponents(0))
    Assert-ComSuccess $circuit
    if ('R1' -notin $components -or 'R2' -notin $components) {
        throw "Import did not create the requested native components: $components"
    }
    $before = [double]$circuit.RLCValue('R2')
    Assert-ComSuccess $circuit
    $report = [string]$circuit.ReportNetlist($true, 1, [Type]::Missing)
    Assert-ComSuccess $circuit
    Set-ProbeStage 'save_native_initial'
    [void]$circuit.SaveAs($initial)
    Assert-ComSuccess $circuit
    if (-not (Test-Path -LiteralPath $initial)) { throw 'SaveAs did not create the native file.' }
    Set-ProbeStage 'export_image'
    [void]$circuit.GetCircuitImage(0, $image)
    Assert-ComSuccess $circuit
    Set-ProbeStage 'edit_rlc'
    $circuit.StopSimulation()
    [void]$circuit.GetType().InvokeMember('RLCValue', [Reflection.BindingFlags]::SetProperty,
        $null, $circuit, @([string]'R2', [double]20000))
    Assert-ComSuccess $circuit
    [void]$circuit.SaveAs($edited)
    Assert-ComSuccess $circuit
    Disconnect-Probe
    Set-ProbeStage 'reopen_saved_revision'
    $app = New-Object -ComObject MultisimInterface.MultisimApp
    $app.Connect()
    $circuit = $app.OpenFile($edited)
    Assert-ComSuccess $app
    $after = [double]$circuit.RLCValue('R2')
    Assert-ComSuccess $circuit
    if ([Math]::Abs($after - 20000) -gt 0.01) { throw "Saved resistor value is incorrect: $after" }
    @{ success = $true; components = $components; report = $report; before = $before;
       after_reopen = $after; initial = $initial; edited = $edited; image = $image } |
        ConvertTo-Json -Depth 10 -Compress
} catch {
    @{ success = $false; stage = $stage; message = $_.Exception.Message } |
        ConvertTo-Json -Depth 5 -Compress
    exit 1
} finally {
    Disconnect-Probe
}
