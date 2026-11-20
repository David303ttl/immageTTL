# Building Immage on Windows

The result is an x64 `.exe` installer, that runs on any 64-bit
Windows 10 or 11 PC, and on Windows on ARM through its x64 emulation. It is
built on Windows itself; a Windows 11 on ARM virtual machine works, building
under the same emulation, only more slowly.

## One-time setup

Install, choosing the x64 download wherever there is a choice:

1. **Git for Windows** (git-scm.com)
2. **MSYS2** (msys2.org), into `C:\msys64`
3. **Visual Studio or Visual Studio Build Tools**, with the *Desktop
   development with C++* workload, MSVC x64/x86 tools, and a Windows SDK.
   The fork builds with Visual Studio 2026 Build Tools. For Visual Studio
   2022, select *MSVC v143 - VS 2022 C++ x64/x86 build tools*.
4. **Rust 1.89 or newer** (rustup.rs), using the x64 MSVC toolchain. After
   installing rustup, open a fresh PowerShell and run:

   ```powershell
   rustup toolchain install stable-x86_64-pc-windows-msvc
   rustup default stable-x86_64-pc-windows-msvc
   rustc -vV
   ```
   On Windows on ARM, add `--force-non-host` to the install command if
   rustup selected an ARM host. Check that `rustc -vV` reports
   `host: x86_64-pc-windows-msvc`.
5. **Node.js LTS** (nodejs.org, the x64 `.msi`). The fork builds with Node 22 x64.

Then, in the **MSYS2 UCRT64** shell (not "MSYS2 MSYS"), darktable's
libraries: the list darktable's own Windows CI installs, without those of
the features the engine build turns off (G'MIC, GraphicsMagick, OpenCV,
maps, cameras, ...), plus `json-glib` for the engine. The CI build
(`.github/workflows/build.yml`) installs the same:

```sh
pacman -Syu        # again if it closes the shell half way
pacman -S --needed git intltool po4a mingw-w64-ucrt-x86_64-{cc,cmake,ninja,libxslt,python-jsonschema,curl,drmingw,exiv2,gcc-libs,gettext,gtk3,imath,iso-codes,lcms2,lensfun,libarchive,libavif,libheif,libjpeg-turbo,libjxl,libpng,libraw,librsvg,libtiff,libwebp,libxml2,omp,openexr,openjpeg2,potrace,pugixml,sqlite3,zlib,json-glib}
```

Clone the fork in the UCRT64 shell. A short path such as `C:\src` helps
avoid Windows path length limits. Set `core.autocrlf=false` at clone time
to keep LF endings in shell scripts and the darktable patch, as Windows CI does.

```sh
mkdir -p /c/src && cd /c/src
git clone --config core.autocrlf=false --config core.longpaths=true \
  https://github.com/David303ttl/immageTTL.git immageTTL
cd immageTTL
```

## Each build

**1. The engine**, in the **MSYS2 UCRT64** shell. The first build takes a
long while; later ones only rebuild what changed:

```sh
cd /c/src/immageTTL
GIT_CONFIG_COUNT=2 \
  GIT_CONFIG_KEY_0=core.autocrlf GIT_CONFIG_VALUE_0=false \
  GIT_CONFIG_KEY_1=core.longpaths GIT_CONFIG_VALUE_1=true \
  sh scripts/build.sh
```

The environment settings also apply to the Git commands the build runs.
The script initializes the pinned darktable checkout and its engine
submodules, builds OpenCV and the engine, and checks out the importer at
the commit in `app/immporter.rev`.

It ends with `bundled N DLLs, ... MB; not found: 0`.

The engine derives its version from the release tags in the pinned
[darktable checkout](docs/dev/darktable-pin.md). The AI model downloader
uses that version to find compatible models. After the engine build,
`git -C darktable describe --tags --match 'release-*'` should print
`release-5.7.0-...` for the current pin.

**2. The app and its installers**, in **PowerShell** (MSYS2's shell does
not see Windows' Node and Rust):

Use `npm.cmd` to run npm with PowerShell's existing execution policy.

```powershell
cd C:\src\immageTTL\immporter
npm.cmd ci
cd ..\app
npm.cmd ci
npm.cmd run tauri build
```

The installer lands in
`app\src-tauri\target\release\bundle\nsis\Immage_<version>_x64-setup.exe`.
The `.exe` asks: for everyone, into Program Files, or just for you, under
AppData, without administrator rights. On an administrator's account
Windows asks for permission before that choice either way; a standard
user gets no prompt and installs just for themselves. Settings, AI
models and caches stay in each user's AppData. Installing for everyone
over a per-user install (0.31 and earlier were always per user) removes
that copy first.

## When it goes wrong

- Copy the last 20 or so lines of the window's output; the first error is
  the one that matters.
- If `git ls-files --eol scripts/build.sh` shows `w/crlf`, use a fresh
  checkout with the clone command above. Shell scripts and patch context
  need LF endings.
- If PowerShell cannot find Rust after installation, open a fresh session.
  If you installed rustup without adding it to PATH, run
  `$env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"` for the build session.
- An unsigned installer makes SmartScreen warn on first run: *More info >
  Run anyway*.
- AI masks download their models on first use with Windows' own `curl`
  and `tar`, which come with Windows 10 (1803 and later) and Windows 11.
  A download that fails says so in the status line at the bottom right of
  the photo.
