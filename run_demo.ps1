$ErrorActionPreference = 'Continue'
# PowerShell 7 can turn native stderr lines into terminating errors; capture them so task failures remain inspectable.
$PSNativeCommandUseErrorActionPreference = $false
$repo = $PSScriptRoot
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw "Project interpreter not found: $python" }
$demoRoot = Join-Path $env:TEMP ('jarvis-mission-demo-' + [guid]::NewGuid().ToString('N'))
$fixture = Join-Path $demoRoot 'fixture'
$db = Join-Path $demoRoot 'missions.sqlite3'
New-Item -ItemType Directory -Path $fixture -Force | Out-Null
for ($i = 0; $i -lt 12; $i++) {
    $payload = ('REAL_CONTENT_MARKER_{0} ' -f $i) + ('sample-data ' * ($i + 1))
    Set-Content -LiteralPath (Join-Path $fixture ('file-{0:D2}.txt' -f $i)) -Value $payload -NoNewline -Encoding utf8
}
$script:lastOutput = ''

function Invoke-JarvisMission([string]$name, [string[]]$arguments, [int]$expectedExitCode = 0) {
    $raw = & $python (Join-Path $repo 'main.py') @arguments 2>&1
    $actualExitCode = $LASTEXITCODE
    $script:lastOutput = ($raw | Out-String)
    if ($actualExitCode -ne $expectedExitCode) {
        Write-Output ("{0}=FAIL expected_exit={1} actual_exit={2}" -f $name, $expectedExitCode, $actualExitCode)
        Write-Output $script:lastOutput
        throw "$name failed"
    }
    Write-Output ("{0}=PASS exit_code={1}" -f $name, $actualExitCode)
    foreach ($line in ($script:lastOutput -split "`r?`n")) {
        if ($line -match '^(MISSION_ID|PLANNED_STEPS|STEP_\d+_STATUS|STEP_\d+_EXIT_CODE)=') { Write-Output $line }
    }
    $resultLine = ($script:lastOutput -split "`r?`n" | Where-Object { $_.StartsWith('MISSION_RESULT=') } | Select-Object -Last 1)
    if ($resultLine) {
        $summary = $resultLine.Substring('MISSION_RESULT='.Length) | ConvertFrom-Json
        Write-Output ("MISSION_STATE={0} COMPLETED_STEPS={1}/{2}" -f $summary.state, $summary.completed_steps, $summary.planned_steps)
        if ($summary.failure_reason) { Write-Output ("MISSION_FAILURE_REASON={0}" -f $summary.failure_reason) }
    }
}

try {
    Write-Output '=== TASK 1: real largest-file listing + summaries ==='
    $objective = "List the 10 largest files in $fixture and summarize them"
    Invoke-JarvisMission 'TASK_1' @('--mission', $objective, '--mission-db', $db, '--mission-id', 'demo-list-summary') 0
    $stepOneLine = ($script:lastOutput -split "`r?`n" | Where-Object { $_.StartsWith('STEP_1_STDOUT=') } | Select-Object -Last 1)
    $listed = ($stepOneLine.Substring('STEP_1_STDOUT='.Length) | ConvertFrom-Json).files
    Write-Output ('LARGEST_FILES=' + (($listed | ForEach-Object { '{0}:{1}' -f [IO.Path]::GetFileName($_.path), $_.size_bytes }) -join ', '))
    if ($listed.Count -ne 10 -or $listed[0].size_bytes -lt $listed[-1].size_bytes) { throw 'Largest-file results were not correctly sorted or limited to 10.' }
    $summaryLine = ($script:lastOutput -split "`r?`n" | Where-Object { $_.StartsWith('STEP_2_STDOUT=') } | Select-Object -Last 1)
    $summaries = ($summaryLine.Substring('STEP_2_STDOUT='.Length) | ConvertFrom-Json).files
    if (-not ($summaries | Where-Object { $_.preview -match 'REAL_CONTENT_MARKER_' })) { throw 'No real text preview was produced.' }
    Write-Output 'SUMMARY_PREVIEW=REAL_CONTENT_MARKER verified'

    Write-Output '=== TASK 2: standalone summarize objective ==='
    Invoke-JarvisMission 'TASK_2' @('--mission', "Summarize the largest files in $fixture", '--mission-db', $db, '--mission-id', 'demo-summary-only') 0
    $task2ResultLine = ($script:lastOutput -split "`r?`n" | Where-Object { $_.StartsWith('MISSION_RESULT=') } | Select-Object -Last 1)
    $task2Summary = $task2ResultLine.Substring('MISSION_RESULT='.Length) | ConvertFrom-Json
    if ($task2Summary.planned_steps -ne 1 -or $task2Summary.step_results[0].action -ne 'summarize_files') { throw 'Standalone summarize objective did not produce exactly one summarize_files step.' }
    if ($script:lastOutput -notmatch 'REAL_CONTENT_MARKER_') { throw 'Standalone summary did not return real file contents.' }

    Write-Output '=== TASK 3: existing policy blocks destructive action ==='
    Invoke-JarvisMission 'TASK_3' @('--mission', ('delete ' + (Join-Path $fixture 'file-00.txt')), '--mission-db', $db, '--mission-id', 'demo-policy-deny') 1
    if ($script:lastOutput -notmatch 'Execution policy denied') { throw 'Destructive action was not denied by policy.' }

    Write-Output '=== TASK 4: kill process after checkpoint, then resume ==='
    $recoveryId = 'demo-kill-restart'
    $stdoutPath = Join-Path $demoRoot 'interrupted.stdout.txt'
    $stderrPath = Join-Path $demoRoot 'interrupted.stderr.txt'
    $quotedObjective = '"' + $objective.Replace('"', '\"') + '"'
    $argLine = "main.py --mission $quotedObjective --mission-db `"$db`" --mission-id $recoveryId --pause-after-step 1"
    $proc = Start-Process -FilePath $python -ArgumentList $argLine -WorkingDirectory $repo -PassThru -NoNewWindow -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    while ([DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 100
        if ((Test-Path $stdoutPath) -and (Select-String -Path $stdoutPath -Pattern 'MISSION_CHECKPOINT_READY=1' -Quiet)) { break }
        if ($proc.HasExited) { break }
    }
    $interruptedOutput = if (Test-Path $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Raw } else { '' }
    if ($interruptedOutput -notmatch 'MISSION_CHECKPOINT_READY=1') { throw "Mission never reached durable checkpoint. Output: $interruptedOutput" }
    Stop-Process -Id $proc.Id -Force
    Write-Output 'PROCESS_KILLED_AFTER=STEP_1_STATUS=completed'
    Invoke-JarvisMission 'TASK_4_RESUME' @('--resume', '--mission-db', $db, '--mission-id', $recoveryId) 0
    if ($script:lastOutput -notmatch '"state": "COMPLETED"') { throw 'Restart did not finish the mission.' }

    Write-Output '=== TASK 5: real tool error persisted ==='
    $missing = Join-Path $demoRoot 'missing-directory'
    Invoke-JarvisMission 'TASK_5' @('--mission', "List the 10 largest files in $missing", '--mission-db', $db, '--mission-id', 'demo-missing-path') 1
    if ($script:lastOutput -notmatch 'does not exist') { throw 'Missing-path failure reason was not recorded.' }

    Write-Output 'DEMO_RESULT=PASS all 5 tasks passed in one run'
    Write-Output ("DEMO_DATABASE={0}" -f $db)
    Write-Output 'DEMO_WORKSPACE=temporary; jarvis_test_workspace preserved'
    exit 0
}
catch {
    Write-Output ("DEMO_RESULT=FAIL reason={0}" -f $_.Exception.Message)
    Write-Output ("DEMO_ERROR_DETAILS={0}" -f $_.ToString())
    Write-Output ("DEMO_ERROR_STACK={0}" -f $_.ScriptStackTrace)
    if ($script:lastOutput) { Write-Output $script:lastOutput }
    exit 1
}
