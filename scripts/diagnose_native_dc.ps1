param([Parameter(Mandatory=$true)][string]$CircuitPath,
      [Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$app = $null
$circuit = $null
$data = @{}
try {
    if ([Environment]::Is64BitProcess) { throw 'Use the 32-bit STA host.' }
    $path = (Get-Item -LiteralPath $CircuitPath).FullName
    $directory = [IO.Path]::GetFullPath($OutputDirectory)
    [void][IO.Directory]::CreateDirectory($directory)
    $commands = Join-Path $directory 'listing.commands'
    $log = Join-Path $directory 'listing.log'
    if ((Test-Path -LiteralPath $commands) -or (Test-Path -LiteralPath $log)) { throw 'Choose a fresh output directory.' }
    [IO.File]::WriteAllText($commands, "listing`nshow all`nprint all`n")
    $app = New-Object -ComObject MultisimInterface.MultisimApp
    $app.Connect()
    $circuit = $app.OpenFile($path)
    $data.variant = [string]$circuit.ActiveVariant
    $data.variants = @($circuit.EnumVariants())
    $names = @($circuit.EnumOutputs(1))
    $data.before = $names
    $circuit.DoDCOperatingPoint([string[]]$names)
    $timedOut = $false
    $data.wait_result = $circuit.WaitForNextOutput([ref]$timedOut, 10000)
    $data.timed_out = $timedOut
    $data.after = @($circuit.EnumOutputs(1))
    $data.state = $circuit.SimulationState
    $data.samples = @{}
    foreach ($name in $names) {
        try {
            $values = $null
            $method = 0
            $circuit.GetOutputData([string]$name, [ref]$values, [ref]$method)
            $data.samples[[string]$name] = @($values)
        } catch { $data.samples[[string]$name] = [string]$circuit.LastErrorMessage }
    }
    try { $circuit.DoCommandLine($commands, $log) } catch { $data.listing_error = $_.Exception.Message }
    $data.log_file = $log
} catch { $data.error = $_.Exception.Message }
finally {
    if ($null -ne $circuit) { try { $circuit.StopSimulation() } catch { }; [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($circuit) }
    if ($null -ne $app) { try { $app.Disconnect() } catch { }; [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($app) }
}
[Console]::Out.WriteLine(($data | ConvertTo-Json -Depth 12 -Compress))
