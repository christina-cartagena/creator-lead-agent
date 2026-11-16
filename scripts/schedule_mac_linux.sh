#!/usr/bin/env bash
# Adds two cron jobs: the daily run on weekdays at 8:00, and a reply check every 2 hours.
REPO="$(cd "$(dirname "$0")/.." && pwd)"
CLAUDE="$(command -v claude)"
( crontab -l 2>/dev/null | grep -v creator-lead-agent
  echo "0 8 * * 1-5 cd $REPO && $CLAUDE -p '/daily-run' >> data/runs.log 2>&1 # creator-lead-agent"
  echo "0 9-21/2 * * * cd $REPO && $CLAUDE -p 'Use the check-replies skill. Draft responses, never send.' >> data/runs.log 2>&1 # creator-lead-agent"
) | crontab -
echo "Scheduled. Run 'crontab -l' to see the jobs."
