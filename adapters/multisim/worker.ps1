# JSON-in/JSON-out COM worker. Invoke with 32-bit Windows PowerShell in STA mode.
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$app = $null
$circuit = $null
$response = $null
$stage = 'request'

function Assert-ComSuccess($Object) {
    $message = [string]$Object.LastErrorMessage
    if (-not [string]::IsNullOrWhiteSpace($message)) { throw $message }
}

function Get-Names($Items) {
    return ,@($Items | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

function Convert-Samples($Data) {
    if ($Data -is [Array] -and $Data.Rank -eq 2) {
        $rows = New-Object 'System.Collections.Generic.List[object]'
        for ($i = $Data.GetLowerBound(0); $i -le $Data.GetUpperBound(0); $i++) {
            $row = @()
            for ($j = $Data.GetLowerBound(1); $j -le $Data.GetUpperBound(1); $j++) {
                $row += [double]$Data.GetValue($i, $j)
            }
            $rows.Add($row)
        }
        return ,$rows.ToArray()
    }
    return ,@($Data)
}

try {
    if ([Environment]::Is64BitProcess) { throw 'Multisim requires a 32-bit COM host.' }
    $request = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $name = [string]$request.action_name
    if ($name -notin @('probe', 'read_circuit', 'list_components', 'export_netlist', 'run_simulation', 'new_blank', 'verify_schematic', 'canonicalize_schematic')) {
        throw "Unsupported worker action: $name"
    }
    $parameters = $request.parameters
    $stage = 'connect'
    $app = New-Object -ComObject MultisimInterface.MultisimApp
    if ($request.executable) { $app.Path = [string]$request.executable }
    $app.Connect()
    if (-not $app.IsConnected) { throw "Multisim connection failed: $($app.LastErrorMessage)" }
    $data = @{ connected = $true; software_version = [string]$app.VersionInfo }

    if ($name -eq 'new_blank') {
        $target = [IO.Path]::GetFullPath([string]$parameters.output_file)
        if (Test-Path -LiteralPath $target) { throw 'Refusing to overwrite a blank-document target.' }
        $circuit = $app.NewFile()
        [void]$circuit.SaveAs($target)
        Assert-ComSuccess $circuit
        $data.file = $target
    } elseif ($name -ne 'probe') {
        $stage = 'open_file'
        $circuit = $app.OpenFile([string]$parameters.file_path)
        if ($null -eq $circuit) { throw "Cannot open circuit: $($app.LastErrorMessage)" }
        Assert-ComSuccess $app
        $data.circuit_name = [string]$circuit.CircuitName
        if ($name -eq 'canonicalize_schematic') {
            $stage = 'set_native_values'
            if ($circuit.SimulationState -ne 0) { $circuit.StopSimulation() }
            foreach ($property in $parameters.values.PSObject.Properties) {
                [void]$circuit.GetType().InvokeMember('RLCValue', [Reflection.BindingFlags]::SetProperty,
                    $null, $circuit, @([string]$property.Name, [double]$property.Value))
                Assert-ComSuccess $circuit
            }
            $target = [IO.Path]::GetFullPath([string]$parameters.output_file)
            if (Test-Path -LiteralPath $target) { throw 'Refusing to overwrite a canonicalization target.' }
            [void]$circuit.SaveAs($target)
            Assert-ComSuccess $circuit
            $data.file = $target
        } elseif ($name -in @('read_circuit', 'list_components', 'verify_schematic')) {
            $stage = 'enum_components'
            $data.components = Get-Names ($circuit.EnumComponents(0))
            Assert-ComSuccess $circuit
            $data.outputs = Get-Names ($circuit.EnumOutputs(0))
            Assert-ComSuccess $circuit
            $data.component_count = $data.components.Count
            if ($name -eq 'verify_schematic') {
                $data.report = [string]$circuit.ReportNetlist($true, 1, [Type]::Missing)
                Assert-ComSuccess $circuit
                $data.values = @{}
                foreach ($reference in @($parameters.value_references)) {
                    $data.values[[string]$reference] = [double]$circuit.RLCValue([string]$reference)
                    Assert-ComSuccess $circuit
                }
            }
        } elseif ($name -eq 'export_netlist') {
            $stage = 'report_netlist'
            $format = if ($parameters.format -eq 'csv') { 1 } else { 0 }
            $data.report = [string]$circuit.ReportNetlist($true, $format, [Type]::Missing)
            Assert-ComSuccess $circuit
        } elseif ($name -eq 'run_simulation') {
            $stage = 'enum_outputs'
            $available = Get-Names ($circuit.EnumOutputs(0))
            Assert-ComSuccess $circuit
            $names = @($parameters.output_names)
            if ($names.Count -eq 0) { $names = Get-Names ($circuit.EnumOutputs(1)) }
            Assert-ComSuccess $circuit
            if ($names.Count -eq 0 -or $names.Count -gt 16) { throw 'Select between 1 and 16 enumerated outputs.' }
            foreach ($output in $names) {
                if ($output -notin $available) { throw "Unknown simulation output: $output" }
            }
            $stage = 'analysis_' + [string]$parameters.analysis_type
            switch ([string]$parameters.analysis_type) {
                'dc' { $circuit.DoDCOperatingPoint([string[]]$names) }
                'ac' {
                    $sweeps = @{ decade = 0; octave = 1; linear = 2 }
                    $circuit.DoACSweep($sweeps[[string]$parameters.sweep_type], [int]$parameters.sample_count,
                        [double]$parameters.start_frequency, [double]$parameters.stop_frequency, [string[]]$names)
                }
                'transient' {
                    foreach ($output in $names) {
                        $rate = [int]$parameters.sample_count / [double]$parameters.stop_time
                        $circuit.SetOutputRequest([string]$output, 2, $rate, [int]$parameters.sample_count, $false)
                    }
                    $circuit.RunSimulation([double]$parameters.stop_time, $true)
                }
                default { throw 'Unsupported analysis type.' }
            }
            Assert-ComSuccess $circuit
            $clock = [Diagnostics.Stopwatch]::StartNew()
            $limit = [Math]::Max(1, [int]$request.timeout_seconds - 10)
            $outputs = @{}
            $stage = 'wait_for_analysis_output'
            $timedOut = $true
            while ($timedOut) {
                [void]$circuit.WaitForNextOutput([ref]$timedOut, 100)
                if ($clock.Elapsed.TotalSeconds -ge $limit) { throw 'Timed out waiting for analysis output.' }
            }
            foreach ($output in $names) {
                $stage = 'output_ready:' + [string]$output
                $ready = $false
                while (-not $ready) {
                    try { $ready = [bool]$circuit.OutputReady([string]$output) } catch { }
                    if ($ready) { break }
                    if ($clock.Elapsed.TotalSeconds -ge $limit) { throw "Timed out waiting for output: $output" }
                    Start-Sleep -Milliseconds 50
                }
                $samples = $null
                $interpolation = 0
                $stage = 'get_output_data:' + [string]$output
                $circuit.GetOutputData([string]$output, [ref]$samples, [ref]$interpolation)
                Assert-ComSuccess $circuit
                $series = @{ data = (Convert-Samples $samples); interpolation = $interpolation;
                    analysis_type = [string]$parameters.analysis_type }
                if ($parameters.analysis_type -eq 'transient') { $series.sample_rate_hz = $rate }
                $outputs[[string]$output] = $series
            }
            $data.outputs = $outputs
        }
    }
    $response = @{ success = $true; worker_bits = 32; data = $data }
} catch {
    $detail = $_.Exception.Message
    foreach ($object in @($circuit, $app)) {
        if ($null -ne $object) {
            try {
                $nativeMessage = [string]$object.LastErrorMessage
                if (-not [string]::IsNullOrWhiteSpace($nativeMessage)) { $detail += ' | ' + $nativeMessage }
            } catch { }
        }
    }
    $response = @{ success = $false; worker_bits = $(if ([Environment]::Is64BitProcess) { 64 } else { 32 });
        error = @{ code = 'ERR_MULTISIM_COM';
            message = "$stage`: $detail" } }
} finally {
    if ($null -ne $circuit) {
        try { $circuit.StopSimulation() } catch { }
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($circuit)
    }
    if ($null -ne $app) {
        try { $app.Disconnect() } catch { }
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($app)
    }
}
[Console]::Out.WriteLine(($response | ConvertTo-Json -Depth 20 -Compress))
if (-not $response.success) { exit 1 }
