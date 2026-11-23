"""tools/CreateUpdateRelease.py: the files of a new release, built without touching Git or the working tree."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_tool', ROOT / 'tools' / 'CreateUpdateRelease.py')
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)

CHANGELOG = '# CHANGELOG\n\n---\n\n## Release: v0.1.0\n### Release Date: 2026-03-26\n#### 🌟 Novedades:\n- X\n'
SERVICE_WORKER = 'const CACHE_NAME = "mam-ia-v0.1.0";\nconst ASSETS = [];\n'


class ReleaseToolTests(unittest.TestCase):
    def test_validate_inputs(self):
        self.assertIsNone(rt.validate_inputs('0.2.0', '2026-12-01'))
        self.assertTrue(rt.validate_inputs('0.2', '2026-12-01'))
        self.assertTrue(rt.validate_inputs('0.2.0-rc1', '2026-12-01'))   # release branches are only X.Y.Z
        self.assertTrue(rt.validate_inputs('0.2.0', '2026-02-30'))

    def test_new_release_goes_on_top_with_empty_sections(self):
        out = rt.add_changelog_release(CHANGELOG, '0.2.0', '2026-12-01')
        self.assertLess(out.index('## Release: v0.2.0'), out.index('## Release: v0.1.0'))
        for section in rt.RELEASE_SECTIONS:
            self.assertIn(section, out)
        with self.assertRaises(RuntimeError):
            rt.add_changelog_release(out, '0.2.0', '2026-12-01')

    def test_update_header_and_service_worker(self):
        out = rt.replace_current_changelog_metadata(CHANGELOG, '0.1.1', '2026-11-20')
        self.assertIn('## Release: v0.1.1\n### Release Date: 2026-11-20', out)
        self.assertIn('const CACHE_NAME = "mam-ia-v1.4.2";', rt.replace_service_worker_version(SERVICE_WORKER, '1.4.2'))
        with self.assertRaises(RuntimeError):
            rt.replace_service_worker_version('const ASSETS = [];\n', '1.4.2')

    def test_real_files_build_without_writing(self):
        before = {p: p.read_text(encoding='utf-8') for p in (rt.CHANGELOG_PATH, rt.SERVICE_WORKER_PATH)}
        version, _ = rt.read_release_metadata()
        major, minor, patch = map(int, version.split('.'))
        new_version = f'{major}.{minor}.{patch + 1}'
        files = rt.release_file_contents(new_version, '2030-01-01', create_changelog_release=True)
        self.assertIn(f'## Release: v{new_version}', files[rt.CHANGELOG_PATH])
        self.assertIn(f'"mam-ia-v{new_version}"', files[rt.SERVICE_WORKER_PATH])
        self.assertEqual({p: p.read_text(encoding='utf-8') for p in before}, before)   # nothing written


if __name__ == '__main__':
    unittest.main()
