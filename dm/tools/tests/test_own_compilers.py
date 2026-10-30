"""Mac shader builds do not require an installed Metal CLI."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'dm/gfx/tools'))
import own_compilers  # noqa: E402

spec = importlib.util.spec_from_file_location('build_ipa_from_nsp', REPO / 'scripts/build_ipa_from_nsp.py')
assert spec and spec.loader
nsp = importlib.util.module_from_spec(spec); spec.loader.exec_module(nsp)


class CheckTools(unittest.TestCase):
    def test_compiler_mismatch_is_not_special(self):
        failure = 'spirv-cross: lock expected / actual changed'
        with mock.patch.object(own_compilers, 'strict', lambda: [failure]):
            self.assertEqual(own_compilers.check_tools(), [failure])

    def test_metal_check_always_allows_runtime_compilation(self):
        self.assertEqual(own_compilers.check_metal(), '')

    def test_real_check_has_no_xcode_requirement(self):
        r = subprocess.run([sys.executable, str(REPO / 'dm/gfx/tools/own_compilers.py'), '--check-metal'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


class NspScript(unittest.TestCase):
    def test_mac_metal_check_is_a_noop(self):
        with mock.patch.object(nsp.subprocess, 'run') as run:
            nsp.check_metal(sys.executable, REPO, {})
        run.assert_not_called()

    def test_legacy_flag_is_still_accepted(self):
        self.assertTrue(nsp.parse_args(['x', '--allow-other-metal']).allow_other_metal)


if __name__ == '__main__':
    unittest.main()
