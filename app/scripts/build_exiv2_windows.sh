#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the Immage authors

set -eu

root=$(cd "$(dirname "$0")/../.." && pwd)
work="$root/build/exiv2-windows"
source=https://github.com/Exiv2/exiv2
tag=v0.28.9
revision=b0859fc61fea5dedfc898aece6b15893ddf4314e
patch="$root/patches/exiv2-windows-unicode.patch"
key=$(printf '%s\n' "$revision" "$(git hash-object "$patch")" "$(git hash-object "$0")" |
      git hash-object --stdin | cut -c1-16)
src="$work/src-$key"
build="$work/build-$key"
install="$work/install"

if [ -f "$install/bin/libexiv2-28.dll" ] &&
   [ "$(cat "$install/build-key" 2>/dev/null)" = "$key" ]; then
  exit 0
fi

if [ ! -d "$src/.git" ]; then
  git init --quiet "$src"
  git -C "$src" config core.autocrlf false
fi
if ! git -C "$src" rev-parse --verify HEAD >/dev/null 2>&1; then
  git -C "$src" fetch --quiet --depth 1 "$source" "$revision"
  git -C "$src" -c advice.detachedHead=false checkout --quiet --detach FETCH_HEAD
fi
test "$(git -C "$src" rev-parse HEAD)" = "$revision"
if ! git -C "$src" apply --reverse --check "$patch" 2>/dev/null; then
  git -C "$src" apply "$patch"
fi

# Use the MSYS2 DLL name and keep the build private to Immage. Exiv2's
# translation catalogs were never included in the Windows bundle.
cmake -S "$src" -B "$build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX="$install" -DCMAKE_INSTALL_LIBDIR=lib \
      -DCMAKE_DLL_NAME_WITH_SOVERSION=ON -DEXIV2_ENABLE_NLS=OFF \
      -DEXIV2_ENABLE_WEBREADY=ON -DEXIV2_ENABLE_CURL=ON \
      -DEXIV2_TEAM_WARNINGS_AS_ERRORS=ON
cmake --build "$build"
cmake --install "$build"
test -f "$install/bin/libexiv2-28.dll"
cp "$src/COPYING" "$install/COPYING"
printf 'Exiv2 %s\n  license: GPL-2.0-or-later\n  source: %s/tree/%s\n' \
  "${tag#v}" "$source" "$revision" > "$install/info"
printf '%s\n' "$key" > "$install/build-key"
