"""Provisional memory layouts must leave room for the game's initial heap."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'dm/games'))
import profile_guess as pg


class DepthSignal(unittest.TestCase):
    ZERO, GL = '[dm] [nvn] depth mode near=0 (as D3D / Metal)\n', '[dm] [nvn] depth mode near=-w (GL)\n'
    RESET = '[dm] [nvn-mtl] depth mode: near=-w (GL), vertex shaders use the main0 entry\n'   # the host's own reset at device init, also printed for a game that never calls the setter

    def profile(self, **keys):
        return type('Profile', (), {'get': staticmethod(lambda k, d='': keys.get(k, d))})

    def seen(self, log, **keys):
        return pg.depth_signal(log, self.profile(**keys)).get('depth_mode', (None,))[0]

    def test_the_game_sets_near_zero(self):
        self.assertEqual(self.seen(self.ZERO), 'zero')

    def test_no_call_is_unknown_not_gl(self):
        self.assertIsNone(self.seen('>>> nnMain\n'))
        self.assertIsNone(self.seen('>>> nnMain\n', depth_mode='zero'))   # a boot that stopped before the call says nothing against the key

    def test_the_host_reset_is_not_the_game_calling(self):
        self.assertIsNone(self.seen(self.RESET, depth_mode='zero'))
        self.assertEqual(self.seen(self.ZERO + self.RESET), 'zero')   # a second device's reset does not undo the game's call

    def test_a_profile_that_agrees_gets_no_change(self):
        self.assertIsNone(self.seen(self.ZERO, depth_mode='zero'))
        self.assertIsNone(self.seen(self.GL))

    def test_the_last_call_counts(self):
        self.assertEqual(self.seen(self.GL + self.ZERO), 'zero')
        self.assertEqual(self.seen(self.ZERO + self.GL, depth_mode='zero'), 'gl')

    def test_the_reason_is_one_comment_line(self):
        value, why = pg.depth_signal(self.ZERO, self.profile())['depth_mode']
        self.assertEqual(value, 'zero'); self.assertIn('near = 0', why); self.assertNotIn('\n', why)


class GlslSources(unittest.TestCase):
    def test_language_preamble_is_not_a_shader(self):
        self.assertEqual(pg.glsl_sources(b'#version 450 core\n#define float4 vec4\n\0void main() {}\0'), 0)

    def test_complete_embedded_sources(self):
        image = b'#version 450\nvoid main() {}\0#version 450\nvoid main (void) {}\0'
        self.assertEqual(pg.glsl_sources(image), 2)

    def test_only_text_files_count_as_glsl_sources(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root / 'shaders').mkdir()
            (root / 'shaders/sprite.vert').write_bytes(b'#version 450\n\tvoid main() {}\r\n')
            (root / 'shaders/sprite.FRAG').write_bytes('// café\nvoid main() {}\n'.encode())
            (root / 'shaders/sprite.txt').write_bytes(b'void main() {}\n')   # not a shader file by its name
            (root / 'shaders/cipher.vert').write_bytes(hashlib.sha256(b'ciphertext').digest() * 128)   # Skyward Sword HD's Dummy.vert: encrypted, read only on a cache miss
            (root / 'shaders/empty.frag').write_bytes(b'')
            self.assertEqual(pg.romfs_glsl_files(root), 2)


class Npdm(unittest.TestCase):
    def npdm(self, flags):
        d = bytearray(0x80); d[:4] = b'META'; d[0xc] = flags
        p = Path(self.tmp.name) / 'main.npdm'; p.write_bytes(d); return p

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)

    def test_64bit_flag(self):
        self.assertTrue(pg.aarch64(self.npdm(0x3f)))   # 64-bit, 39-bit address space

    def test_32bit_program(self):
        self.assertFalse(pg.aarch64(self.npdm(0x04)))   # Pikmin 3 Deluxe: 32-bit, no reserved region

    def test_no_npdm(self):
        self.assertTrue(pg.aarch64(Path(self.tmp.name) / 'missing.npdm'))


class UnrealMemory(unittest.TestCase):
    def test_initial_heap_fits_beside_the_engine_region(self):
        facts = {
            'mods': {'main': {'imports': {'nvnBootstrapLoader', pg.HEAP_API}, 'bss': 0, 'far': False}},
            'romfs': {'root': set(), 'exts': {'.pak': 1}},
            'sysres': 40 * pg.MiB,
            'main_markers': {'Unreal 4'},
        }
        keys = pg.guess(facts, hooks=set())
        reserve, alias, stack = (int(keys[k][0], 0) for k in ('mem_reserve', 'mem_alias', 'mem_stack'))
        self.assertGreaterEqual(alias, 64 * 1024**3)
        # mem_init puts the modules before the alias region, then stacks and the heap.
        heap = reserve - 0x10000000 - alias - stack
        self.assertGreaterEqual(heap, 128 * pg.MiB)


if __name__ == '__main__':
    unittest.main()
