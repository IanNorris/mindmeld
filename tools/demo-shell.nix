{ pkgs ? import <nixpkgs> {} }:
# Environment for recording the Playwright demo: a wrapped Chromium plus
# fontconfig and fonts, so headless Chromium can render text (otherwise it
# aborts with "SkFontMgr_FontConfigInterface ... Not implemented").
pkgs.mkShell {
  buildInputs = [
    pkgs.chromium
    pkgs.fontconfig
    pkgs.dejavu_fonts
    pkgs.noto-fonts
    pkgs.noto-fonts-color-emoji
  ];
  # Build a fontconfig cache/conf so Chromium finds the fonts above.
  shellHook = ''
    export FONTCONFIG_FILE=$(mktemp)
    cat > "$FONTCONFIG_FILE" <<EOF
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>${pkgs.dejavu_fonts}/share/fonts</dir>
  <dir>${pkgs.noto-fonts}/share/fonts</dir>
  <dir>${pkgs.noto-fonts-color-emoji}/share/fonts</dir>
  <cachedir>$(mktemp -d)</cachedir>
  <include ignore_missing="yes">${pkgs.fontconfig.out}/etc/fonts/fonts.conf</include>
</fontconfig>
EOF
    export CHROME_BIN=$(command -v chromium)
  '';
}
