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

    def test_other_metal_stops(self):
        for key in ('metal_macosx', 'metal_iphoneos'):
            with self.assertRaises(SystemExit) as e: self.check([mismatch(key, OTHER)])
            msg = str(e.exception.code)
            self.assertTrue(msg.startswith('[RED] '), msg)
            for want in (key, OTHER, LOCKED[key], f'Xcode {own_compilers.XCODE_VERSION}', 'macOS 26.6', 'xcodebuild -downloadComponent MetalToolchain', 'DM_ALLOW_OTHER_METAL=1', '#242'): self.assertIn(want, msg)

    def test_other_metal_says_to_select_the_tested_xcode(self):   # a newer Xcode selected downloads its own toolchain again (GitHub issue #717)
        sel = ' (selected: Xcode 27.3 in /Applications/Xcode.app/Contents/Developer)'
        with mock.patch.object(own_compilers, 'selected_xcode', lambda: sel):
            msg = own_compilers.other_metal_message([('metal_macosx', LOCKED['metal_macosx'], OTHER)])
        app = own_compilers.XCODE_APP
        for want in (sel, 'https://developer.apple.com/download/all/', f'sudo xcode-select -s {app}', f'DEVELOPER_DIR={app}/Contents/Developer'): self.assertIn(want, msg)
        self.assertLess(msg.index('xcode-select -s'), msg.index('-downloadComponent'), 'select the tested Xcode before downloading its toolchain')

    def test_selected_xcode_without_xcode(self):   # no xcode-select or xcodebuild: the message goes without the selected Xcode
        with mock.patch.object(own_compilers.subprocess, 'run', side_effect=FileNotFoundError):
            self.assertEqual(own_compilers.selected_xcode(), '')

    def test_real_check_has_no_xcode_requirement(self):
        r = subprocess.run([sys.executable, str(REPO / 'dm/gfx/tools/own_compilers.py'), '--check-metal'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


class NspScript(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.tmp)

    def test_stops_with_the_script_override(self):
        msg = own_compilers.other_metal_message([('metal_macosx', LOCKED['metal_macosx'], OTHER)])
        done = subprocess.CompletedProcess([], 1, stdout=msg + '\n', stderr='')
        with mock.patch.object(nsp, 'ALLOW_OTHER_METAL', False), mock.patch.object(nsp.subprocess, 'run', return_value=done) as run, self.assertRaises(nsp.BuildError) as e:
            nsp.check_metal(sys.executable, REPO, {})
        self.assertIn('--check-metal', run.call_args[0][0])
        text = str(e.exception)
        self.assertIn(f'Xcode {own_compilers.XCODE_VERSION}', text); self.assertIn('ALLOW_OTHER_METAL = True (--allow-other-metal)', text); self.assertFalse(text.startswith('[RED]'))

    def test_tested_metal_or_override_goes_on(self):
        with mock.patch.object(nsp, 'ALLOW_OTHER_METAL', False), mock.patch.object(nsp.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')):
            nsp.check_metal(sys.executable, REPO, {})
        with mock.patch.object(nsp, 'ALLOW_OTHER_METAL', True), mock.patch.object(nsp.subprocess, 'run') as run:
            nsp.check_metal(sys.executable, REPO, {})
        run.assert_not_called()

    def test_check_metal_runs(self):   # the real tool with the real lock: exit 0 or 1 with the message, never a traceback (no Xcode: no compiler, which dmsh_build.py reports)
        r = subprocess.run([sys.executable, str(REPO / 'dm/gfx/tools/own_compilers.py'), '--check-metal'], capture_output=True, text=True,
                           env={k: v for k, v in os.environ.items() if k != own_compilers.ALLOW})
        self.assertIn(r.returncode, (0, 1), r.stderr)
        if r.returncode: self.assertIn(f'Xcode {own_compilers.XCODE_VERSION}', r.stdout)

    def test_flag(self):
        self.assertTrue(nsp.parse_args(['x', '--allow-other-metal']).allow_other_metal)


if __name__ == '__main__':
    unittest.main()
