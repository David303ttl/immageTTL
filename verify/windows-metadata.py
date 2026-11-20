#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the Immage authors

"""Test the bundled Windows engine with Unicode photo and working paths."""

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
EXIV2 = ROOT / 'build' / 'exiv2-windows'
BUNDLE = ROOT / 'app' / 'src-tauri' / 'resources' / 'darktable' / 'bin'
ENV = {k: v for k, v in os.environ.items() if k.upper() != 'LANG' and not k.upper().startswith('LC_')}
ENV['OMP_NUM_THREADS'] = '2'
ENV['PATH'] = os.pathsep.join([str(BUNDLE), str(Path(os.environ['SystemRoot']) / 'System32')])


def requests(work, *commands):
    config = ['--core', '--configdir', str(work / 'config'), '--cachedir', str(work / 'cache'),
              '--conf', 'opencl=false']
    payload = ''.join(json.dumps(cmd | {'rid': rid}) + '\n' for rid, cmd in enumerate(commands, 1))
    result = subprocess.run([BUNDLE / 'darktable-engine.exe', *config], cwd=work, env=ENV,
                            input=payload, capture_output=True, encoding='utf-8', errors='replace',
                            timeout=45, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, result.stderr
    for marker in ('darktable.localedir:', 'GLib-CRITICAL', 'Illegal byte sequence'):
        assert marker not in result.stderr, result.stderr
    replies = {obj['rid']: obj for line in result.stdout.splitlines()
               if line.startswith('{') and 'rid' in (obj := json.loads(line))}
    assert len(replies) == len(commands), (replies, result.stderr)
    return [replies[i] for i in range(1, len(commands) + 1)]


def check_lens_config(work, photo):
    exiv = EXIV2 / 'install' / 'bin' / 'exiv2.exe'
    ini = work / 'exiv2.ini'
    ini.write_text('[nikon]\n127=Immage test lens\n', encoding='ascii')
    try:
        result = subprocess.run([exiv, '-pa', '-g', 'LensIDNumber', photo], cwd=work, env=ENV,
                                capture_output=True, encoding='utf-8', errors='replace',
                                timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode == 0, result.stderr
        assert 'Immage test lens' in result.stdout, (result.stdout, result.stderr)
    finally:
        ini.unlink()


def check_xmp(work, photo):
    sidecar = photo.with_name(photo.name + '.xmp')
    open_photo = {'cmd': 'open', 'path': str(photo)}

    def save(exposure):
        return requests(work, open_photo, {'cmd': 'set', 'op': 'exposure', 'enabled': True,
                        'params': {'exposure': exposure}}, {'cmd': 'save'})

    replies = save(0.5)
    assert all(reply['ok'] for reply in replies), replies
    first = sidecar.read_bytes()
    replies = save(1.5)
    assert all(reply['ok'] for reply in replies), replies
    updated = sidecar.read_bytes()
    assert first != updated, photo

    replies = requests(work, open_photo, {'cmd': 'get', 'modules': {'exposure': ['exposure']}})
    assert all(reply['ok'] for reply in replies), replies
    exposure = replies[-1]['modules']['exposure']
    assert exposure['enabled'] and math.isclose(exposure['params']['exposure'], 1.5), replies

    # A read-only destination makes replacement fail after the temp XMP is written.
    sidecar.chmod(0o444)
    try:
        replies = save(2.5)
        assert all(reply['ok'] for reply in replies[:-1]), replies
        assert not replies[-1]['ok'] and 'could not save' in replies[-1]['error'], replies
        assert sidecar.read_bytes() == updated, sidecar
        assert not list(sidecar.parent.glob('.immage-*.tmp')), sidecar.parent
    finally:
        sidecar.chmod(0o666)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('photos', nargs='*', type=Path, help='additional Nikon NEF or JPEG fixtures')
    parser.add_argument('--other-drive', type=Path, help='directory on a second drive for test copies')
    args = parser.parse_args()
    key = (EXIV2 / 'install' / 'build-key').read_text(encoding='ascii').strip()
    nikon = EXIV2 / f'src-{key}' / 'test' / 'data' / 'exiv2-nikon-d70.jpg'

    with (tempfile.TemporaryDirectory(prefix='immage-metadata-', dir=os.environ['USERPROFILE']) as profile,
          tempfile.TemporaryDirectory(prefix='immage-metadata-', dir=args.other_drive) as other):
        work = Path(profile) / 'work-ł-写真'
        work.mkdir()
        unicode_photos = []
        ascii_photos = []
        for i, fixture in enumerate([nikon, *args.photos]):
            unicode_photo = work / f'{i}-ł-写真{fixture.suffix}'
            ascii_photo = Path(other) / f'{i}{fixture.suffix}'
            shutil.copyfile(fixture, unicode_photo)
            shutil.copyfile(fixture, ascii_photo)
            unicode_photos.append(unicode_photo)
            ascii_photos.append(ascii_photo)

        # Without an INI in this working directory, Nikon maker notes use the
        # Windows profile lookup, even for photos imported from another drive.
        photos = ascii_photos + unicode_photos
        imported, = requests(work, {'cmd': 'import', 'files': list(map(str, photos))})
        assert imported['ok'] and not imported['unanswered'], imported
        assert len(imported['images']) == len(photos), imported
        for image in imported['images']:
            assert image['exif']['model'], image

        check_lens_config(work, unicode_photos[0])
        for photo in photos:
            check_xmp(work, photo)
        print('Windows metadata and XMP checks passed.')


if __name__ == '__main__':
    main()
