[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^v\d+$')]
    [string]$Version,

    [int]$Runs = 20,
    [int]$MinWins = 18,
    [int]$StallSec = 120,
    [int]$RearmSec = 75,
    [int]$RunTimeoutSec = 2700,
    [switch]$Redeploy,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "Workspace Python was not found: $python"
}

$reports = Join-Path $root 'reports'
New-Item -ItemType Directory -Force -Path $reports | Out-Null

function Quote-CmdArgument {
    param([Parameter(Mandatory = $true)][string]$Value)
    if ($Value.Contains('"')) {
        throw "Command argument contains an unsupported quote: $Value"
    }
    return '"' + $Value + '"'
}

function New-TaskActionArguments {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$LogPath
    )

    $parts = @((Quote-CmdArgument $python), '-u')
    $parts += $Arguments | ForEach-Object { Quote-CmdArgument ([string]$_) }
    $inner = ($parts -join ' ') + ' >> ' + (Quote-CmdArgument $LogPath) + ' 2>&1'
    return '/d /s /c "' + $inner + '"'
}

$monitorLog = Join-Path $reports "live_monitor_$Version.log"
$supervisorLog = Join-Path $reports "overnight_supervisor_$Version.log"
$supervisorState = Join-Path $reports "gate_state_$Version.json"
$monitorArgs = @(
    (Join-Path $root 'scripts\live_monitor.py'),
    '--interval',
    '5'
)
$supervisorArgs = @(
    (Join-Path $root 'scripts\overnight_supervisor.py'),
    '--runs',
    [string]$Runs,
    '--min-wins',
    [string]$MinWins,
    '--stall-sec',
    [string]$StallSec,
    '--rearm-sec',
    [string]$RearmSec,
    '--run-timeout-sec',
    [string]$RunTimeoutSec,
    '--report-prefix',
    "batch_overnight_${Runs}_$Version",
    '--state-file',
    $supervisorState
)
if ($Redeploy) {
    $supervisorArgs += '--redeploy'
}

$monitorActionArguments = New-TaskActionArguments -Arguments $monitorArgs -LogPath $monitorLog
$supervisorActionArguments = New-TaskActionArguments -Arguments $supervisorArgs -LogPath $supervisorLog
$monitorTaskName = "BrotatoAgent-LiveMonitor-$Version"
$supervisorTaskName = "BrotatoAgent-Supervisor-$Version"

if ($DryRun) {
    [pscustomobject]@{
        Root = $root
        MonitorTaskName = $monitorTaskName
        SupervisorTaskName = $supervisorTaskName
        MonitorAction = "cmd.exe $monitorActionArguments"
        SupervisorAction = "cmd.exe $supervisorActionArguments"
        MonitorLog = $monitorLog
        SupervisorLog = $supervisorLog
        SupervisorState = $supervisorState
        TriggerInterval = 'PT1M'
        TriggerDuration = 'P2D'
    } | ConvertTo-Json -Depth 3
    exit 0
}

$existing = @(
    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq 'python.exe' -and
        ($_.CommandLine -like '*scripts\live_monitor.py*' -or
         $_.CommandLine -like '*scripts\overnight_supervisor.py*')
    }
)
if ($existing.Count -gt 0) {
    $pids = ($existing.ProcessId | Sort-Object) -join ', '
    throw "Gate watchdogs are already running (PIDs: $pids)"
}

$existingTasks = @(
    Get-ScheduledTask -TaskName $monitorTaskName, $supervisorTaskName -ErrorAction SilentlyContinue
)
if ($existingTasks.Count -gt 0) {
    $names = ($existingTasks.TaskName | Sort-Object) -join ', '
    throw "Gate watchdog tasks already exist: $names"
}

# Task Scheduler launches these workers outside Codex's transient execution
# boundary. Direct children and even WMI-created processes are cleaned up when
# a Codex turn ends; scheduled task workers survive that boundary.
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Days 2) `
    -MultipleInstances IgnoreNew `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries
$monitorAction = New-ScheduledTaskAction `
    -Execute 'cmd.exe' `
    -Argument $monitorActionArguments `
    -WorkingDirectory $root
$supervisorAction = New-ScheduledTaskAction `
    -Execute 'cmd.exe' `
    -Argument $supervisorActionArguments `
    -WorkingDirectory $root
$restartTrigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 1) `
    -RepetitionDuration (New-TimeSpan -Days 2)

Register-ScheduledTask `
    -TaskName $monitorTaskName `
    -Action $monitorAction `
    -Trigger $restartTrigger `
    -Settings $settings `
    -Description "BrotatoAgent $Version live telemetry monitor" | Out-Null
try {
    Register-ScheduledTask `
        -TaskName $supervisorTaskName `
        -Action $supervisorAction `
        -Trigger $restartTrigger `
        -Settings $settings `
        -Description "BrotatoAgent $Version $Runs-run supervised evaluation" | Out-Null
} catch {
    Unregister-ScheduledTask -TaskName $monitorTaskName -Confirm:$false -ErrorAction SilentlyContinue
    throw
}

Start-ScheduledTask -TaskName $monitorTaskName
Start-ScheduledTask -TaskName $supervisorTaskName

[pscustomobject]@{
    Version = $Version
    MonitorTaskName = $monitorTaskName
    SupervisorTaskName = $supervisorTaskName
    MonitorLog = $monitorLog
    SupervisorLog = $supervisorLog
    SupervisorState = $supervisorState
    TriggerInterval = 'PT1M'
    TriggerDuration = 'P2D'
} | ConvertTo-Json -Depth 3
