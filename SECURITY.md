# Security policy

## Reporting a vulnerability

Please don't open a public issue for a security problem. Report it privately through
[GitHub's private vulnerability reporting](../../security/advisories/new) (the **Report a
vulnerability** button on the Security tab).

Include what you found, how to reproduce it, and what an attacker could do with it. We'll
confirm we got it within a week, keep you posted while we fix it, and credit you in the release
notes unless you'd rather we didn't.

## Supported versions

Only the latest release gets security fixes.

## What's in scope

- The web page and its API: sign-in, the PIN, settings, and anything reachable without signing in.
- The desktop app: the shell, its local API token, and the packaged core.
- The Claude Code tool: anything that lets a spoken or typed question read files, run commands
  or reach data outside the folders listed in `CLAUDE_CODE_FOLDERS`.
- Where the app stores keys and settings, and who else on the computer can read them.

Problems in Reachy Mini's own software, Claude Code, or the speech and model providers belong
with those projects.

The README's [Security](README.md#security) section describes how the app is meant to be
protected and what it deliberately doesn't cover, such as plain HTTP on your local network.
