param(
    [string]$CircuitPath,
    [string]$BlankOutput,
    [string]$ImageOutput,
    [string]$Reference = 'R2'
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$app = $null
$circuit = $null
$stage = 'paths'
$response = $null
function Assert-ComSuccess($Object) {
    $message = [string]$Object.LastErrorMessage
    if (-not [string]::IsNullOrWhiteSpace($message)) { throw $message }
}
try {
    if ([Environment]::Is64BitProcess) { throw 'A 32-bit STA host is required.' }
    if ($BlankOutput) {
        $path = [IO.Path]::GetFullPath($BlankOutput)
        if (Test-Path -LiteralPath $path) { throw 'Never overwrite a native file.' }
        [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path))
    } else {
        $path = (Get-Item -LiteralPath $CircuitPath).FullName
        $before = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    }
    $stage = 'connect'
    $app = New-Object -ComObject MultisimInterface.MultisimApp
    $app.Connect()
    Assert-ComSuccess $app
    $stage = 'open_native'
    if ($BlankOutput) {
        $circuit = $app.NewFile()
        [void]$circuit.SaveAs($path)
        Assert-ComSuccess $circuit
    } else {
        $circuit = $app.OpenFile($path)
        Assert-ComSuccess $app
    }
    $components = @($circuit.EnumComponents(0) | Where-Object { $_ })
    Assert-ComSuccess $circuit
    $values = @{}
    if ($Reference -in $components) {
        $values[$Reference] = [double]$circuit.RLCValue($Reference)
        Assert-ComSuccess $circuit
    }
    $report = [string]$circuit.ReportNetlist($true, 1, [Type]::Missing)
    Assert-ComSuccess $circuit
    if ($ImageOutput) {
        $image = [IO.Path]::GetFullPath($ImageOutput)
        if (Test-Path -LiteralPath $image) { throw 'Never overwrite an image.' }
        $stage = 'export_image'
        [void]$circuit.GetCircuitImage(0, $image)
        Assert-ComSuccess $circuit
    }
    if (-not $BlankOutput -and $before -ne (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash) {
        throw 'Native input changed during read-only verification.'
    }
    $response = @{ success = $true; file = $path; components = $components;
        values = $values; report = $report; version = [string]$app.VersionInfo }
} catch {
    $response = @{ success = $false; stage = $stage; message = $_.Exception.Message }
} finally {
    if ($null -ne $circuit) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($circuit) }
    if ($null -ne $app) {
        try { $app.Disconnect() } catch { }
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($app)
    }
}
[Console]::Out.WriteLine(($response | ConvertTo-Json -Depth 8 -Compress))
if (-not $response.success) { exit 1 }
