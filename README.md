# Market data engine

Daily Taiwan and US market screening computation. This repository contains computation
and export code only; no member website, account data, credentials, or website links.

## Migration state

Staged only. Scheduled triggers are intentionally absent. Daily/monthly dispatches
require repository variable `ENABLE_UPDATES=true`. Do not enable until database
migration, credential setup, parity checks and the single-writer cutover are complete.
The existing production pipeline remains authoritative during staging.

## Configuration

Screening parameters remain in `config/settings.py` and `config/us_settings.py`.
Secrets: `FINMIND_TOKEN`, `GOOGLE_CREDENTIALS_JSON`, and the ten market-specific
`SHEET_ID_*` / `US_SHEET_ID_*` variables referenced by the workflows.
Never commit their values. Set them using repository Settings / Actions secrets.

## Database snapshots

Only this repository's own `db-backup` and `us-db-backup` releases are read/written.
There is no fallback to another repository. Download/integrity failures stop the run.
Public release assets are public: review database contents before uploading them.

`Validate snapshot` restores both databases and validates exports without writing
Sheets, releases, or a website. Publication is not connected in this staging version.

Daily and monthly jobs for the same market share one concurrency group.
Cross-repository concurrency is not shared; disable the old writer before cutover.
No GitHub Pages website is needed or deployed by this repository.
