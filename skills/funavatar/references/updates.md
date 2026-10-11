# Optional updates

Automatic updates are opt-in for local Codex and Claude Code installations. They check the stable `xcapsa/FunAvatar` GitHub release when the agent starts using FunAvatar, before production work. There is no background service, timer, account connection or avatar upload. The host must provide Python 3.10+, network access and a persistent writable local installation.

Users of older releases need one manual upgrade to a release containing `scripts/funavatar_update.py`. Publishing a release does not remotely change those older installations. A skill ZIP uploaded to a hosted account does not gain local execution or persistent installation access merely because the updater is included; use that host's supported update/import mechanism.

For a local installation without Git, download `funavatar-skill.zip` and `SHA256SUMS` from the official release, verify the ZIP checksum and extract it into a staging folder. From that staging folder, run the bundled installer:

```sh
python3 funavatar/scripts/funavatar_installer.py --target codex
```

Use `claude` or `both` for the intended hosts, and add `--update` for an existing recognized installation. The staging folder must be separate from the installed destination. The installer creates the receipt through its normal validation path; automatic enablement does not invent one for files previously copied by hand. Preserve any unrecognized installation and inspect it before migration. On Windows, use `python` if that is the registered Python 3.10+ command.

## Enable once

After the user requests automatic updates, choose only the installation targets they intend to update. Run from the relevant skill folder, or replace the relative script path with its actual installed path:

```sh
python3 scripts/funavatar_update.py enable --target codex
python3 scripts/funavatar_update.py enable --target claude
python3 scripts/funavatar_update.py enable --target both
```

These are alternatives: run only the selected command. `both` requires both installations. Enablement validates the existing managed files before saving the preference outside the skill folders in `~/.local/share/funavatar/auto-update.json`. Do not manufacture a receipt for an unrecognized or customized installation.

On subsequent new uses the agent runs:

```sh
python3 scripts/funavatar_update.py auto
```

Disabled means no network request. Enabled means checking the selected local targets against the latest stable release and applying an eligible update. Report an actual update briefly and reread the returned installed skill entrypoint. If no update is needed, continue the avatar work without a repetitive status announcement. A running chat may already have loaded older instructions; never claim those instructions were refreshed without reading the new files.

## Check, update once or disable

```sh
python3 scripts/funavatar_update.py check --target codex
python3 scripts/funavatar_update.py update --target codex
python3 scripts/funavatar_update.py disable
```

`check` is read-only. `update` is a single explicit update and does not turn on future automatic updates. Substitute `claude` or `both` for the intended local targets. `disable` turns off the saved opt-in; it does not uninstall the skill or remove avatar files.

## Protection and limits

The updater accepts stable numeric release versions from the fixed official repository, verifies the expected skill ZIP and its checksum, checks its contents before extraction, and uses the already-installed installer code for replacement. It does not run code from the downloaded package as part of the update. Prereleases, downgrades, unsafe archives and local modifications prevent replacement. Previous installations are retained under `~/.local/share/funavatar/backups`.

On network failure or a busy/changed installation, an automatic attempt leaves the current copy usable and reports that the update was deferred. Offline use therefore cannot guarantee the newest release. Keep custom files and avatar assets outside the managed skill folder; preserve existing changes before deciding how to migrate them. Never delete local changes merely to make an automatic update pass.

The updater's local-platform support is separate from the Tripo workflow adapter, which currently requires Unix file locking. An updater test on Windows does not establish Windows support for the Tripo adapter or runtime compatibility of an avatar.
