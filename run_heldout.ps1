param(
    [string]$HeldoutPath = 'C:\Users\ridha\jarvis_heldout\HELDOUT.md'
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$repo = $PSScriptRoot
$python = Join-Path $repo '.venv\Scripts\python.exe'
$entry = Join-Path $repo 'mission_crash_safe.py'
if (-not (Test-Path -LiteralPath $python)) { throw "Project interpreter not found: $python" }
if (-not (Test-Path -LiteralPath $entry)) { throw "Crash-safe mission entry point not found: $entry" }
if (-not (Test-Path -LiteralPath $HeldoutPath -PathType Leaf)) {
    Write-Output 'HELDOUT_FILE=NOT_FOUND'
    Write-Output 'Expected private file at C:\Users\ridha\jarvis_heldout\HELDOUT.md; no file contents were read.'
    exit 2
}

function Get-TextHash([string]$Text) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
        return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    } finally { $sha.Dispose() }
}

# Private format: ## <case-id>, followed by one Objective: line and one or more Check: key=value lines.
# Objective text is consumed only here, hashed, and passed to the mission CLI; it is never echoed.
$cases = @()
$current = $null
foreach ($line in [System.IO.File]::ReadAllLines($HeldoutPath, [System.Text.Encoding]::UTF8)) {
    if ($line -match '^##\s+([^\s]+)\s*$') {
        if ($null -ne $current) { $cases += $current }
        $current = [ordered]@{ id = $Matches[1]; objective = $null; checks = @() }
        continue
    }
    if ($null -eq $current) { continue }
    if ($line -match '^Objective:\s*(.*?)\s*$') {
        $current.objective = $Matches[1]
        continue
    }
    if ($line -match '^Check:\s*(.*?)\s*$') {
        $current.checks += $Matches[1]
    }
}
if ($null -ne $current) { $cases += $current }
if ($cases.Count -eq 0) {
    Write-Output 'HELDOUT_PARSE=FAIL no objective cases found'
    exit 2
}

$dbDir = Join-Path $env:LOCALAPPDATA 'JARVIS'
New-Item -ItemType Directory -Path $dbDir -Force | Out-Null
$db = Join-Path $dbDir 'heldout-missions.sqlite3'
$passed = 0
$failed = 0
$runId = [guid]::NewGuid().ToString('N')

foreach ($case in $cases) {
    if ([string]::IsNullOrWhiteSpace([string]$case.objective) -or $case.checks.Count -eq 0) {
        Write-Output ("CASE={0} OBJECTIVE_HASH=INVALID RESULT=FAIL FAILURE_CLASS=planner reason=missing_objective_or_checks" -f $case.id)
        $failed++
        continue
    }
    $hash = Get-TextHash ([string]$case.objective)
    $missionId = 'heldout-' + $runId + '-' + ([string]$case.id -replace '[^A-Za-z0-9_.-]', '_')
    $args = @($entry, '--mission', [string]$case.objective, '--mission-id', $missionId,
              '--mission-db', $db, '--workspace-root', $env:USERPROFILE)
    $raw = & $python @args 2>&1
    $exitCode = $LASTEXITCODE
    $output = ($raw | Out-String)
    $stateLine = ($output -split "`r?`n" | Where-Object { $_ -match '^MISSION_STATE=' } | Select-Object -Last 1)
    $state = if ($stateLine) { $stateLine.Substring('MISSION_STATE='.Length).Trim() } else { 'UNKNOWN' }
    $reasonLine = ($output -split "`r?`n" | Where-Object { $_ -match '^MISSION_FAILURE_REASON=' } | Select-Object -Last 1)
    $reason = if ($reasonLine) { $reasonLine.Substring('MISSION_FAILURE_REASON='.Length).Trim() } else { '' }
    $stepLines = @($output -split "`r?`n" | Where-Object { $_.StartsWith('STEP_RESULT=') })
    $steps = @()
    foreach ($stepLine in $stepLines) {
        try { $steps += ($stepLine.Substring('STEP_RESULT='.Length) | ConvertFrom-Json) }
        catch { Write-Output ("CASE={0} STEP_JSON=INVALID" -f $case.id) }
    }

    Write-Output ("CASE={0} OBJECTIVE_SHA256={1} MISSION_STATE={2} PROCESS_EXIT={3}" -f $case.id, $hash, $state, $exitCode)
    for ($i = 0; $i -lt $steps.Count; $i++) {
        $step = $steps[$i]
        Write-Output ("STEP_{0}_STATUS={1}" -f ($i + 1), $step.status)
        if ($null -ne $step.exit_code) { Write-Output ("STEP_{0}_OS_EXIT_CODE={1}" -f ($i + 1), $step.exit_code) }
        if ($null -ne $step.normalized_code) { Write-Output ("STEP_{0}_NORMALIZED_CODE={1}" -f ($i + 1), $step.normalized_code) }
        Write-Output ("STEP_{0}_STDOUT_BEGIN" -f ($i + 1))
        Write-Output ([string]$step.stdout)
        Write-Output ("STEP_{0}_STDOUT_END" -f ($i + 1))
        Write-Output ("STEP_{0}_STDERR={1}" -f ($i + 1), [string]$step.stderr)
        if ($step.error) { Write-Output ("STEP_{0}_ERROR={1}" -f ($i + 1), [string]$step.error) }
    }

    $checksPassed = $true
    $checkFailures = @()
    $allOutput = (($steps | ForEach-Object { [string]$_.stdout }) -join "`n")
    foreach ($check in $case.checks) {
        $pair = $check -split '=', 2
        if ($pair.Count -ne 2) { $checksPassed = $false; $checkFailures += 'invalid_check_syntax'; continue }
        $key, $value = $pair[0].Trim(), $pair[1]
        $ok = $false
        switch -Regex ($key) {
            '^state$' { $ok = ($state -eq $value.Trim()); break }
            '^step_count>$' { $ok = ($steps.Count -ge [int]$value); break }
            '^steps>$' { $ok = ($steps.Count -ge [int]$value); break }
            '^completed_steps>$' { $ok = (@($steps | Where-Object status -eq 'completed').Count -ge [int]$value); break }
            '^all_steps_completed$' { $ok = ($value.Trim().ToLowerInvariant() -eq 'true' -and $steps.Count -gt 0 -and @($steps | Where-Object status -ne 'completed').Count -eq 0); break }
            '^step_status$' { $ok = ($steps.Count -gt 0 -and @($steps | Where-Object status -ne $value.Trim()).Count -eq 0); break }
            '^stdout_contains$' { $ok = $allOutput.Contains($value); break }
            '^stdout_regex$' { try { $ok = [regex]::IsMatch($allOutput, $value) } catch { $ok = $false }; break }
            '^stderr_empty$' { $ok = ($value.Trim().ToLowerInvariant() -eq 'true' -and @($steps | Where-Object { -not [string]::IsNullOrEmpty([string]$_.stderr) }).Count -eq 0); break }
            '^os_exit_code$' { $ok = (@($steps | Where-Object { $null -ne $_.exit_code -and [int]$_.exit_code -eq [int]$value }).Count -gt 0); break }
            '^normalized_code$' { $ok = (@($steps | Where-Object { $null -ne $_.normalized_code -and [int]$_.normalized_code -eq [int]$value }).Count -gt 0); break }
            '^path_exists$' { $ok = (Test-Path -LiteralPath $value); break }
            default { $ok = $false; $checkFailures += ("unsupported_check:" + $key) }
        }
        if (-not $ok) { $checksPassed = $false; $checkFailures += ("check_failed:" + $key) }
    }

    if ($state -eq 'COMPLETED' -and $checksPassed -and $exitCode -eq 0) {
        Write-Output ("CASE_RESULT=PASS CASE={0}" -f $case.id)
        $passed++
    } else {
        $failureClass = 'tool'
        if ($output -match 'failure_class=planner|Unsupported objective|Planner produced|no executable steps') { $failureClass = 'planner' }
        elseif ($reason -match 'Execution policy|denied|confirmation') { $failureClass = 'policy' }
        elseif ($reason -match 'sqlite|database|WAL|persist|locked|corrupt' -or $output -match 'sqlite3\.(OperationalError|DatabaseError)') { $failureClass = 'persistence' }
        elseif ($exitCode -eq 2 -and $state -eq 'UNKNOWN') { $failureClass = 'planner' }
        Write-Output ("CASE_RESULT=FAIL CASE={0} FAILURE_CLASS={1} CHECK_FAILURES={2}" -f $case.id, $failureClass, ($checkFailures -join ','))
        if ($reason) { Write-Output ("FAILURE_REASON={0}" -f $reason) }
        $failed++
    }
}
Write-Output ("HELDOUT_SUMMARY=PASS:{0} FAIL:{1}" -f $passed, $failed)
if ($failed -gt 0) { exit 1 }
exit 0
