# km

`km` formalizes the old ad hoc keyd helper into a real app under `~/Apps`.

It manages one user-editable config:

- `~/.config/km/keyd.config`

## Usage

```text
km -h
km -v
km -u
km conf
km apply
km status
```

## Install

```bash
./install.sh -u
```

That installs the latest released `km` into `~/.km/bin/km`, creates `~/.local/bin/km`, and removes the old `keyd_manager` install footprint.

## Release

```bash
./push_release_upgrade.sh
```

That pushes the current branch, tags the next patch release, waits for the GitHub release asset, and upgrades the installed app.
