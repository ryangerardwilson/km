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

Manually add this to `~/.bashrc` if `~/.local/bin` is not already on your PATH,
then reload your shell:

```bash
export PATH="$HOME/.local/bin:$PATH"
source ~/.bashrc
```

That keeps the internal launcher at `~/.km/bin/km`, publishes
`~/.local/bin/km`, and removes the old `keyd_manager` install footprint. If
you still have an old `keyd_manager` PATH line in `~/.bashrc`, remove it
manually.

## Release

```bash
./push_release_upgrade.sh
```

That pushes the current branch, tags the next patch release, waits for the GitHub release asset, and upgrades the installed app.
