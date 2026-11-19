# Market data engine

Daily Taiwan and US market screening computation. This repository contains computation
and export code only; no member website, account data, credentials, or website links.

## Operation

Daily/monthly workflows require repository variable `ENABLE_UPDATES=true`.
Keep only this repository's stock writers enabled after migration; GitHub concurrency
is scoped to a repository and cannot coordinate an old writer in another repository.

Taipei (UTC+8) scheduled start times:
- Taiwan: weekdays 15:00, with a 16:30 refresh.
- US: Tuesday–Saturday 06:30 (previous US trading day).
- Monthly universe refresh: day 1, Taiwan 09:00 and US 09:30.

These are start times, not completion times. GitHub scheduled jobs can be delayed.
US retrieval commonly takes more than two hours. Public-repository scheduled workflows
may be disabled after 60 days without repository activity: monitor Actions and re-enable
if GitHub disables them. Failure alerts and Actions run conclusions must be reviewed.

To pause computation, set ENABLE_UPDATES=false. Manual validation and deployment
remain available. Never start a second database writer in another repository.

## Configuration

Screening parameters remain in `config/settings.py` and `config/us_settings.py`.
Secrets: `FINMIND_TOKEN`, `GOOGLE_CREDENTIALS_JSON`, and the ten market-specific
`SHEET_ID_*` / `US_SHEET_ID_*` variables referenced by the workflows.
Publishing also requires `ZF_WORDPRESS_ORIGIN`, `ZF_WORDPRESS_PUBLISH_KEY`, and
`ZF_PUBLISH_SITE`. Never commit secret values. Set them in Settings / Actions secrets.
The Cloudflare endpoint verifies GitHub OIDC identity; its trust configuration is
maintained separately in the private deployment repository.

## Database snapshots

Only this repository's own `db-backup` and `us-db-backup` releases are read/written.
There is no fallback to another repository. Download/integrity failures stop the run.
Public release assets are public: review database contents before uploading them.

`Validate snapshot` restores both databases and validates exports without writing
Sheets, releases, or a website. `Verify connections` checks provider and Sheet access.
`Sync Company Google Sheets` recomputes against a temporary copy of saved databases,
checks parity, writes the ten company sheets and reads back the saved rows.

`Deploy Site` runs after a successful daily workflow, or manually. It restores both
market snapshots with retry/integrity checks and rejects invalid/empty exports before
publishing. Member results are pushed server-to-server; no GitHub Pages UI is deployed.
Cloudflare receives the complete data set. The `site-data` Release contains the full
`site-data.tar.gz` plus `site-data.json` (dates, SHA-256 and byte count). Consumers must
verify the metadata against the archive and retain their previous snapshot on mismatch.
The archive uploads first; metadata uploads last. A release-copy failure does not
suppress the member/Cloudflare publishing steps.

Daily and monthly jobs for the same market share one concurrency group.
Cross-repository concurrency is not shared; disable the old writer before cutover.
No GitHub Pages website is needed or deployed by this repository.
