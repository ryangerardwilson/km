# km Agent Guide

## Workspace Defaults
- Follow `/home/ryan/Documents/agent_context/CLI_TUI_STYLE_GUIDE.md` for CLI taste and help shape.
- Follow `/home/ryan/Documents/agent_context/CANONICAL_REFERENCE_IMPLEMENTATION_FOR_CLI_AND_TUI_APPS.md` where it usefully applies to launcher and installer behavior.

## Scope
- `km` is only for the managed sticky-keys `keyd` config.
- Keep it focused on three flows:
  - open the managed config in an editor
  - install/apply that config into `/etc/keyd/`
  - inspect `keyd.service` status
- Do not expand this into a generic keyboard remapping suite unless the user explicitly asks.

## Storage
- The editable config lives at `~/.config/km/keyd.config`.
- Seed that file from `assets/keyd.config` when it does not exist yet.
- If `~/.config/keyd_manager/keyd.config` exists from the previous app name, copy it into the new `km` location on first use.
- Keep mutable state out of the repo.
