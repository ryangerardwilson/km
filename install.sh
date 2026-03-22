#!/usr/bin/env bash
set -euo pipefail

APP="km"
REPO="ryangerardwilson/km"
APP_HOME="$HOME/.${APP}"
INSTALL_DIR="$APP_HOME/bin"
APP_DIR="$APP_HOME/app"
FILENAME="km-linux-x64.tar.gz"
PRIMARY_LAUNCHER="$HOME/.local/bin/${APP}"
LEGACY_APP="keyd_manager"
LEGACY_APP_HOME="$HOME/.${LEGACY_APP}"
LEGACY_LAUNCHER="$HOME/.local/bin/${LEGACY_APP}"

MUTED='\033[0;2m'
RED='\033[0;31m'
ORANGE='\033[38;5;214m'
NC='\033[0m'

usage() {
  cat <<EOF
${APP} Installer

Usage: install.sh [options]

Options:
  -h                         Show this help and exit
  -v [<version>]             Print the latest release version, or install a specific one
  -u                         Upgrade to the latest release only when newer
  -n                         Compatibility no-op; installer never modifies shell config
      --help                 Compatibility alias for -h
      --version [<version>]  Compatibility alias for -v
      --upgrade              Compatibility alias for -u
      --no-modify-path       Compatibility alias for -n
EOF
}

requested_version=${VERSION:-}
show_latest=false
upgrade=false
latest_version_cache=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    -v|--version)
      if [[ -n "${2:-}" && "${2:0:1}" != "-" ]]; then
        requested_version="${2#v}"
        shift 2
      else
        show_latest=true
        shift
      fi
      ;;
    -u|--upgrade)
      upgrade=true
      shift
      ;;
    -n|--no-modify-path)
      shift
      ;;
    *)
      echo -e "${ORANGE}Warning: Unknown option '$1'${NC}" >&2
      shift
      ;;
  esac
done

print_message() {
  local level=$1
  local message=$2
  local color="${NC}"
  [[ "$level" == "error" ]] && color="${RED}"
  echo -e "${color}${message}${NC}"
}

die() {
  print_message error "$1"
  exit 1
}

write_primary_launcher() {
  mkdir -p "$(dirname "$PRIMARY_LAUNCHER")"
  cat > "${PRIMARY_LAUNCHER}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
"${HOME}/.${APP}/bin/${APP}" "\$@"
EOF
  chmod 755 "${PRIMARY_LAUNCHER}"
}

remove_legacy_install() {
  rm -f "$LEGACY_LAUNCHER"
  rm -rf "$LEGACY_APP_HOME"
}

finalize_install() {
  write_primary_launcher
  remove_legacy_install
}

print_manual_shell_steps() {
  print_message info "${MUTED}Manually add to ~/.bashrc if needed:${NC} export PATH=\$HOME/.local/bin:\$PATH"
  print_message info "${MUTED}Legacy cleanup:${NC} remove any old keyd_manager PATH line from ~/.bashrc manually if you still have one"
}

get_latest_version() {
  command -v curl >/dev/null 2>&1 || die "'curl' is required but not installed."
  if [[ -z "$latest_version_cache" ]]; then
    local release_url
    local tag
    release_url="$(curl -fsSL -o /dev/null -w "%{url_effective}" "https://github.com/${REPO}/releases/latest")" \
      || die "Unable to determine latest release"
    tag="${release_url##*/}"
    tag="${tag#v}"
    [[ -n "$tag" && "$tag" != "latest" ]] || die "Unable to determine latest release"
    latest_version_cache="$tag"
  fi
  printf '%s\n' "$latest_version_cache"
}

if $show_latest; then
  [[ "$upgrade" == false && -z "$requested_version" ]] || \
    die "-v (no arg) cannot be combined with other options"
  get_latest_version
  exit 0
fi

if $upgrade; then
  [[ -z "$requested_version" ]] || die "-u cannot be combined with -v <version>"
  requested_version="$(get_latest_version)"
  if command -v "${APP}" >/dev/null 2>&1; then
    installed_version="$(${APP} -v 2>/dev/null || true)"
    installed_version="${installed_version#v}"
    if [[ -n "$installed_version" && "$installed_version" == "$requested_version" ]]; then
      finalize_install
      print_manual_shell_steps
      print_message info "${MUTED}${APP} version ${NC}${requested_version}${MUTED} already installed${NC}"
      exit 0
    fi
  fi
fi

raw_os=$(uname -s)
arch=$(uname -m)

if [[ "$raw_os" != "Linux" ]]; then
  print_message error "Unsupported OS: $raw_os (this installer supports Linux only)"
  exit 1
fi

if [[ "$arch" != "x86_64" ]]; then
  print_message error "Unsupported arch: $arch (this installer supports x86_64 only)"
  exit 1
fi

command -v curl >/dev/null 2>&1 || die "'curl' is required but not installed."
command -v tar >/dev/null 2>&1 || die "'tar' is required but not installed."

mkdir -p "$APP_DIR" "$INSTALL_DIR"

if [[ -z "$requested_version" ]]; then
  specific_version="$(get_latest_version)"
else
  requested_version="${requested_version#v}"
  specific_version="${requested_version}"
  http_status=$(curl -sI -o /dev/null -w "%{http_code}" "https://github.com/${REPO}/releases/tag/v${requested_version}")
  if [[ "$http_status" == "404" ]]; then
    print_message error "Release v${requested_version} not found"
    print_message info  "${MUTED}See available releases: ${NC}https://github.com/${REPO}/releases"
    exit 1
  fi
fi

url="https://github.com/${REPO}/releases/download/v${specific_version}/${FILENAME}"

if command -v "${APP}" >/dev/null 2>&1; then
  installed_version="$(${APP} -v 2>/dev/null || true)"
  installed_version="${installed_version#v}"
  if [[ -n "$installed_version" && "$installed_version" == "$specific_version" ]]; then
    finalize_install
    print_manual_shell_steps
    print_message info "${MUTED}${APP} version ${NC}${specific_version}${MUTED} already installed${NC}"
    exit 0
  fi
fi

print_message info "\n${MUTED}Installing ${NC}${APP} ${MUTED}version: ${NC}${specific_version}"
tmp_dir="${TMPDIR:-/tmp}/${APP}_install_$$"
mkdir -p "$tmp_dir"

curl -# -L -o "$tmp_dir/$FILENAME" "$url"
tar -xzf "$tmp_dir/$FILENAME" -C "$tmp_dir"

if [[ ! -f "$tmp_dir/${APP}/${APP}" ]]; then
  print_message error "Archive did not contain expected directory '${APP}/${APP}'"
  print_message info  "Expected: $tmp_dir/${APP}/${APP}"
  exit 1
fi

rm -rf "$APP_DIR"
mkdir -p "$APP_DIR"
mv "$tmp_dir/${APP}" "$APP_DIR"
rm -rf "$tmp_dir"

cat > "${INSTALL_DIR}/${APP}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
"${HOME}/.${APP}/app/${APP}/${APP}" "\$@"
EOF
chmod 755 "${INSTALL_DIR}/${APP}"
finalize_install
print_manual_shell_steps
print_message info "${MUTED}Run:${NC} ${APP} -h"
