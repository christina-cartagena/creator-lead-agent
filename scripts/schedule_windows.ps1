# Runs the pipeline every weekday at 8:00 and checks replies every 2 hours, using Windows Task Scheduler.
# Usage (from the repo root, in PowerShell):  ./scripts/schedule_windows.ps1
$repo = (Resolve-Path "$PSScriptRoot\..").Path
$claude = (Get-Command claude).Source

$daily = New-ScheduledTaskAction -Execute $claude -WorkingDirectory $repo `
  -Argument '-p "/daily-run" --output-format text'
$replies = New-ScheduledTaskAction -Execute $claude -WorkingDirectory $repo `
  -Argument '-p "Use the check-replies skill. Draft responses, never send." --output-format text'

Register-ScheduledTask -TaskName "Creator Lead Agent - daily run" -Action $daily -Force `
  -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 8am)
Register-ScheduledTask -TaskName "Creator Lead Agent - replies" -Action $replies -Force `
  -Trigger (New-ScheduledTaskTrigger -Once -At 9am -RepetitionInterval (New-TimeSpan -Hours 2))
Write-Host "Scheduled. See them in Task Scheduler under 'Creator Lead Agent'."
