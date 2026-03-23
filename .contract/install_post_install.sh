LEGACY_APP="keyd_manager"
LEGACY_APP_HOME="$HOME/.${LEGACY_APP}"
LEGACY_LAUNCHER="${PUBLIC_BIN_DIR}/${LEGACY_APP}"

rm -f "$LEGACY_LAUNCHER"
rm -rf "$LEGACY_APP_HOME"
print_message info "Legacy cleanup: remove any old keyd_manager PATH line from ~/.bashrc manually if you still have one"
