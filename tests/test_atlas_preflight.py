import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

SOURCE = Path(os.environ.get('ATLAS_SOURCE', Path(__file__).resolve().parents[1] / 'tools/build_codex.py'))

class PreflightTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('atlas_under_test', SOURCE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.m.CW = self.m.CH = 2
        self.m.N = 4
        self.m.STAGE = str(root / 'stage')
        for name in ['BASE', 'FRAMES', 'QA', 'DIST']:
            setattr(self.m, name, str(root / name.lower()))
        self.outputs = []
        for name in ['BASE', 'FRAMES', 'QA', 'DIST']:
            path = Path(getattr(self.m, name)) / 'previous-output'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'existing artifact')
            self.outputs.append(path)
        for state, _, durations in self.m.ROWS:
            for i in range(len(durations)):
                self.png(f'{state}/{i:02d}.png')
        for i in range(16): self.png(f'look/{i:02d}_{i * 225:04d}.png')
        self.png('neutral/neutral.png')

    def png(self, name, size=(8, 8)):
        path = Path(self.m.STAGE) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGBA', size, (10, 20, 30, 255)).save(path)
        return path

    def reject_before_write(self):
        # Execute the real main entrypoint. Any attempt to create an output
        # directory proves preflight did not reject before writing began.
        with patch.object(self.m.os, 'makedirs', side_effect=AssertionError('output write attempted')):
            with self.assertRaisesRegex(ValueError, 'existing outputs preserved'):
                self.m.main()
        for path in self.outputs:
            self.assertEqual(path.read_bytes(), b'existing artifact')

    def test_missing_state(self):
        for p in (Path(self.m.STAGE) / 'idle').glob('*.png'): p.unlink()
        self.reject_before_write()

    def test_wrong_state_count(self):
        (Path(self.m.STAGE) / 'running-left/00.png').unlink()
        self.reject_before_write()

    def test_extra_frame(self):
        self.png('idle/extra.png')
        self.reject_before_write()

    def test_missing_look(self):
        (Path(self.m.STAGE) / 'look/00_0000.png').unlink()
        self.reject_before_write()

    def test_missing_neutral(self):
        (Path(self.m.STAGE) / 'neutral/neutral.png').unlink()
        self.reject_before_write()

    def test_wrong_dimensions(self):
        self.png('idle/00.png', (4, 4))
        self.reject_before_write()

    def test_corrupt_png(self):
        (Path(self.m.STAGE) / 'idle/00.png').write_bytes(b'not a png')
        self.reject_before_write()

    def test_replacement_stray_same_count(self):
        (Path(self.m.STAGE) / 'idle/00.png').rename(Path(self.m.STAGE) / 'idle/stale.png')
        self.reject_before_write()

    def test_wrong_look_angle_same_count(self):
        (Path(self.m.STAGE) / 'look/00_0000.png').rename(Path(self.m.STAGE) / 'look/00_0001.png')
        self.reject_before_write()

    def test_rgb_loses_alpha(self):
        Image.new('RGB', (8, 8), (10, 20, 30)).save(Path(self.m.STAGE) / 'idle/00.png')
        self.reject_before_write()

    def test_checksum_valid_undecodable_pixels(self):
        import struct
        import zlib
        path = Path(self.m.STAGE) / 'idle/00.png'
        data = path.read_bytes()
        output = bytearray(data[:8])
        offset = 8
        while offset < len(data):
            size = struct.unpack('>I', data[offset:offset+4])[0]
            kind = data[offset+4:offset+8]
            chunk = data[offset+8:offset+8+size]
            if kind == b'IDAT': chunk = b'invalid zlib data'
            output.extend(struct.pack('>I', len(chunk)) + kind + chunk + struct.pack('>I', zlib.crc32(kind + chunk)))
            offset += 12 + size
        path.write_bytes(output)
        with Image.open(path) as image: image.verify()  # container itself is valid
        self.reject_before_write()

    def test_complete_inputs_reach_existing_build(self):
        with patch.object(self.m.os, 'makedirs', side_effect=RuntimeError('valid build reached')):
            with self.assertRaisesRegex(RuntimeError, 'valid build reached'):
                self.m.main()

if __name__ == '__main__':
    unittest.main()
