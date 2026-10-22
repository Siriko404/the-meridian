# Security

## Reporting a vulnerability

Report it privately through GitHub: **Security, Report a vulnerability** on this repository. Please do not open a public issue. You can expect an acknowledgement within a week.

## Supported versions

Only the latest commit on the default branch receives fixes.

## Scope

The online server (`social_roulette/online`) is public and unauthenticated by design: a papers number is the only credential, so issuing and lookups are rate limited. Report anything that lets one player act as another or touch files outside the data folder.
