import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch
import uuid
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'panel/scripts'))
spec = importlib.util.spec_from_file_location('svent_network_badge', ROOT / 'panel/scripts/ip.py')
badge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(badge)


class NetworkBadgeTests(unittest.TestCase):
    def test_scale_changes_intrinsic_dimensions_without_distorting_artwork(self):
        small = ET.fromstring(badge.badge_svg('192.168.15.65', 'other', 1))
        large = ET.fromstring(badge.badge_svg('192.168.15.65', 'other', 2))
        self.assertEqual(int(large.get('width')), 2 * int(small.get('width')))
        self.assertEqual(int(large.get('height')), 2 * int(small.get('height')))
        self.assertEqual(large.get('viewBox'), small.get('viewBox'))
        self.assertEqual(large.find('{http://www.w3.org/2000/svg}text').text, '192.168.15.65')

    def test_runtime_state_changes_are_read_without_restarting_script(self):
        folder = ROOT / ('badge-test-' + uuid.uuid4().hex)
        suffix = hashlib.sha256(b':77').hexdigest()[:12]
        state = folder / ('svent-display-' + suffix) / 'state.json'
        state.parent.mkdir(parents=True)
        try:
            with patch.dict(os.environ, {'XDG_RUNTIME_DIR': str(folder), 'DISPLAY': ':77'}):
                self.assertEqual(badge.display_scale(), 1)
                state.write_text(json.dumps({'scale': 2}))
                self.assertEqual(badge.display_scale(), 2)
                state.write_text(json.dumps({'scale': 1.25}))
                self.assertEqual(badge.display_scale(), 1.25)
                state.write_text(json.dumps({'scale': float('nan')}))
                self.assertEqual(badge.display_scale(), 1)
        finally:
            shutil.rmtree(folder)
