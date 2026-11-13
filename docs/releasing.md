# Releasing

Releases are published on [GitHub Releases](https://github.com/curious-pm/everything-agent/releases),
with the Windows and macOS installers attached. Versions follow [Semantic Versioning](https://semver.org):
`MAJOR.MINOR.PATCH`, where a fix raises the patch number, a new feature the minor number, and a
change that breaks existing setups the major number.

## Branches

- `main` holds the app.
- `launch-page` holds the app plus the project's web page and the release and Pages workflows.
  Merge `main` into it before releasing; never the other way round.

## Steps

1. **Check `main` is green.** The latest CI run on `main` must pass.

2. **Set the version** on `main`, in all of these:

   | File | Field |
   | --- | --- |
   | `pyproject.toml` | `version` |
   | `src/everything_agent/__init__.py` | `__version__` |
   | `desktop/src-tauri/tauri.conf.json` | `version` |
   | `desktop/src-tauri/Cargo.toml` | `version` (and its entry in `Cargo.lock`) |
   | `ui/package.json`, `desktop/package.json` | `version` (`npm version <x.y.z> --no-git-tag-version`) |

   Then run `uv lock`, commit ("Version x.y.z"), and push.

3. **Merge into `launch-page`**, set `site/package.json` to the same version, and push.

4. **Tag the release** on `launch-page` and push the tag:

   ```bash
   git tag -a vX.Y.Z -m "Everything Agent X.Y.Z"
   git push origin vX.Y.Z
   ```

   The tag must match the version in `tauri.conf.json`, or the release workflow stops.

5. **Wait for the installers.** The Release workflow (`.github/workflows/release.yml`) builds the
   Windows and macOS installers, which takes about 35 minutes, and opens a draft release with
   them attached.

6. **Write the release notes** in the draft: what's new, what's fixed, anything people must do
   when upgrading, and the download table. Then publish it.

## After releasing

- The README's release badge and the web page's download buttons pick up the new release by
  themselves.
- Robot users update with `pip install git+https://github.com/curious-pm/everything-agent@vX.Y.Z`.
