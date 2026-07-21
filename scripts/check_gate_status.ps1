[CmdletBinding()]
param(
    [ValidatePattern('^v\d+$')]
    [string]$Version
)

$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$reports = Join-Path $root 'reports'
$runbookPath = Join-Path $reports 'WP1_ACTIVE_GATE.md'
$monitorPath = Join-Path $reports 'live_monitor.json'

if (-not (Test-Path -LiteralPath $runbookPath)) {
    throw "Active gate runbook was not found: $runbookPath"
}
if (-not (Test-Path -LiteralPath $monitorPath)) {
    throw "Live monitor snapshot was not found: $monitorPath"
}

$runbook = Get-Content -Raw -LiteralPath $runbookPath
if (-not $Version) {
    $versionMatch = [regex]::Match($runbook, '(?m)^- Version: (v\d+)\b')
    if (-not $versionMatch.Success) {
        throw 'Could not determine the active version from WP1_ACTIVE_GATE.md'
    }
    $Version = $versionMatch.Groups[1].Value
}

$gateStart = $null
$gateStartMatch = [regex]::Match(
    $runbook,
    '(?m)^- Gate start: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) Australia/Brisbane\.$'
)
if ($gateStartMatch.Success) {
    $gateStart = Get-Date $gateStartMatch.Groups[1].Value
}

$monitor = Get-Content -Raw -LiteralPath $monitorPath | ConvertFrom-Json
$hudPath = Join-Path $env:APPDATA 'Brotato\brotato_agent\batch_hud.json'
$hud = if (Test-Path -LiteralPath $hudPath) {
    Get-Content -Raw -LiteralPath $hudPath | ConvertFrom-Json
} else {
    $null
}

$taskNames = @(
    "BrotatoAgent-LiveMonitor-$Version",
    "BrotatoAgent-Supervisor-$Version"
)
$allTasks = @(Get-ScheduledTask)
$tasks = @(
    foreach ($taskName in $taskNames) {
        $task = $allTasks | Where-Object { $_.TaskName -eq $taskName } | Select-Object -First 1
        if (-not $task) {
            [pscustomobject]@{
                name = $taskName
                found = $false
            }
            continue
        }

        $info = Get-ScheduledTaskInfo -TaskName $taskName -TaskPath $task.TaskPath
        $triggers = @($task.Triggers)
        $repeatTrigger = $triggers | Select-Object -First 1
        [pscustomobject]@{
            name = $taskName
            found = $true
            state = [string]$task.State
            restart_count = $task.Settings.RestartCount
            restart_interval = $task.Settings.RestartInterval
            stop_on_idle_end = $task.Settings.IdleSettings.StopOnIdleEnd
            trigger_count = $triggers.Count
            trigger_enabled = if ($repeatTrigger) { $repeatTrigger.Enabled } else { $null }
            trigger_interval = if ($repeatTrigger) { $repeatTrigger.Repetition.Interval } else { $null }
            trigger_duration = if ($repeatTrigger) { $repeatTrigger.Repetition.Duration } else { $null }
            last_run = $info.LastRunTime.ToString('s')
            last_result = $info.LastTaskResult
            last_result_is_ignored_trigger = (
                $task.State -eq 'Running' -and $info.LastTaskResult -eq 2147946720
            )
        }
    }
)

$allProcesses = @(Get-CimInstance Win32_Process)
$watchdogProcesses = @(
    $allProcesses | Where-Object {
        $_.CommandLine -and
        $_.CommandLine.IndexOf($root, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        ($_.CommandLine -match 'scripts\\live_monitor\.py' -or
         $_.CommandLine -match 'scripts\\overnight_supervisor\.py')
    } | ForEach-Object {
        [pscustomobject]@{
            name = $_.Name
            pid = $_.ProcessId
            parent_pid = $_.ParentProcessId
            role = if ($_.CommandLine -match 'scripts\\live_monitor\.py') {
                'live_monitor'
            } else {
                'supervisor'
            }
        }
    }
)
$brotatoProcesses = @(
    $allProcesses | Where-Object { $_.Name -ieq 'Brotato.exe' } | ForEach-Object {
        [pscustomobject]@{
            pid = $_.ProcessId
            parent_pid = $_.ParentProcessId
        }
    }
)

$supervisorLogPath = Join-Path $reports "overnight_supervisor_$Version.log"
$supervisorSignals = @()
if (Test-Path -LiteralPath $supervisorLogPath) {
    $supervisorSignals = @(
        Get-Content -Tail 120 -LiteralPath $supervisorLogPath |
            Where-Object {
                $_ -match 'GATE IMPOSSIBLE|Overnight supervisor targeting|record \d+W / \d+L|terminal|summary'
            } |
            Select-Object -Last 12 |
            ForEach-Object { [string]$_ }
    )
}

$currentSummaryPath = $null
if ($monitor.run.events_path) {
    $candidate = Join-Path (Split-Path -Parent ([string]$monitor.run.events_path)) 'summary.json'
    if (Test-Path -LiteralPath $candidate) {
        $currentSummaryPath = $candidate
    }
}
$latestSummary = $null
$summaryFile = if ($currentSummaryPath) {
    Get-Item -LiteralPath $currentSummaryPath
} else {
    Get-ChildItem -LiteralPath (Join-Path $env:APPDATA 'Brotato\brotato_agent\runs') `
        -Recurse -Filter summary.json -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
}
if ($summaryFile) {
    $summary = Get-Content -Raw -LiteralPath $summaryFile.FullName | ConvertFrom-Json
    $latestSummary = [pscustomobject]@{
        path = $summaryFile.FullName
        modified = $summaryFile.LastWriteTime.ToString('s')
        run_id = $summary.run_id
        result = $summary.result
        last_wave = $summary.last_wave
        telemetry_complete = $summary.telemetry_complete
    }
}

$crashes = @()
if ($gateStart) {
    try {
        $crashEvents = @()
        $crashEvents += Get-WinEvent -FilterHashtable @{
            LogName = 'Application'
            ProviderName = 'Application Error'
            Id = 1000
            StartTime = $gateStart
        } -ErrorAction SilentlyContinue
        $crashEvents += Get-WinEvent -FilterHashtable @{
            LogName = 'Application'
            ProviderName = 'Windows Error Reporting'
            Id = 1001
            StartTime = $gateStart
        } -ErrorAction SilentlyContinue
        $crashes = @(
            $crashEvents |
                Where-Object { $_.Message -match '(?i)Brotato(?:\.exe)?' } |
                Sort-Object TimeCreated |
                ForEach-Object {
                    [pscustomobject]@{
                        time = $_.TimeCreated.ToString('s')
                        id = $_.Id
                        provider = $_.ProviderName
                    }
                }
        )
    } catch [System.Exception] {
        $crashes = @([pscustomobject]@{ query_error = $_.Exception.Message })
    }
}

$taskInfrastructureOk =
    $tasks.Count -eq 2 -and
    @($tasks | Where-Object {
        -not $_.found -or
        $_.state -ne 'Running' -or
        $_.restart_count -ne 999 -or
        $_.restart_interval -ne 'PT1M' -or
        $_.stop_on_idle_end -ne $false -or
        $_.trigger_count -ne 1 -or
        $_.trigger_enabled -ne $true -or
        $_.trigger_interval -ne 'PT1M' -or
        $_.trigger_duration -ne 'P2D'
    }).Count -eq 0
$watchdogInfrastructureOk =
    @($watchdogProcesses | Where-Object role -eq 'live_monitor').Count -ge 2 -and
    @($watchdogProcesses | Where-Object role -eq 'supervisor').Count -ge 2

[pscustomobject]@{
    checked_at = (Get-Date).ToString('s')
    version = $Version
    gate_start = if ($gateStart) { $gateStart.ToString('s') } else { $null }
    monitor = [pscustomobject]@{
        updated_at = $monitor.updated_at
        game_running = $monitor.game_running
        severity = $monitor.run.severity
        alerts = @($monitor.run.alerts)
        wins = $monitor.hud.wins
        runs = $monitor.hud.runs
        run_id = $monitor.run.run_id
        active = $monitor.run.active
        terminal_result = $monitor.run.terminal_result
        policy_version = $monitor.run.policy_version
        wave = $monitor.run.wave
        hp = $monitor.run.hp
        recent_min_hp = $monitor.run.recent_min_hp
        enemies = $monitor.run.enemies
        telemetry_age_sec = $monitor.run.telemetry_age_sec
    }
    hud = if ($hud) {
        [pscustomobject]@{
            wins = $hud.wins
            runs = $hud.runs
            policy_version = $hud.policy_version
        }
    } else {
        $null
    }
    tasks = $tasks
    watchdog_processes = $watchdogProcesses
    brotato_processes = $brotatoProcesses
    supervisor_signals = $supervisorSignals
    latest_summary = $latestSummary
    appcrashes_since_gate_start = $crashes
    infrastructure = [pscustomobject]@{
        tasks_ok = $taskInfrastructureOk
        watchdog_processes_ok = $watchdogInfrastructureOk
        brotato_running = $brotatoProcesses.Count -gt 0
    }
} | ConvertTo-Json -Depth 7
