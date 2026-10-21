"""Shortcut generation is tested without claiming actual Windows shell execution."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import desktop_launcher


class DesktopLauncherTests(unittest.TestCase):
    def test_non_windows_does_not_write_a_shortcut(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            result = desktop_launcher.install_shortcut(Path(__file__).resolve().parents[1], home,
                                                       platform_name='posix')
            self.assertEqual(result['status'], 'not_applicable')
            self.assertFalse((home / 'launcher').exists())

    def test_stable_launcher_keeps_original_root_and_previous_bootstrap(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            with patch('desktop_launcher.shutil.which', return_value='powershell.exe'), \
                 patch('desktop_launcher.subprocess.run') as command:
                command.return_value.returncode = 0
                command.return_value.stdout = json.dumps({'status':'installed'})
                result = desktop_launcher.install_shortcut(root, home, platform_name='nt')
                self.assertEqual(result['status'], 'installed')
                settings = json.loads((home / 'launcher/settings.json').read_text())
                self.assertEqual(settings['fallback_root'], str(root))
                self.assertEqual(settings['home'], str(home))
                stable = home / 'launcher/bootstrap.py'
                self.assertEqual(stable.read_bytes(), (root / 'bootstrap.py').read_bytes())
                stable.write_text('# previous working launcher\n')
                desktop_launcher.install_shortcut(root, home, platform_name='nt')
                self.assertEqual((home / 'launcher/bootstrap-previous.py').read_text(), '# previous working launcher\n')
                self.assertIn('WScript.Shell', command.call_args.args[0][-1] if '-Command' in command.call_args.args[0] else desktop_launcher.shortcut_script())

    def test_shortcut_failure_is_nonfatal_and_keeps_recovery_launcher(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            with patch('desktop_launcher.shutil.which', return_value='powershell.exe'), \
                 patch('desktop_launcher.subprocess.run', side_effect=OSError('denied')):
                result = desktop_launcher.install_shortcut(Path(__file__).resolve().parents[1], home,
                                                           platform_name='nt')
            self.assertEqual(result['status'], 'failed')
            self.assertTrue((home / 'launcher/bootstrap.py').exists())
            self.assertNotIn('denied', json.dumps(result))

    def test_instance_clear_is_scoped_to_its_boot(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            desktop_launcher.publish_instance(home, 8765, '0.31.0', 'new-boot')
            desktop_launcher.clear_instance(home, 'old-boot')
            self.assertTrue((home / 'diagnostics/instance.json').exists())
            desktop_launcher.clear_instance(home, 'new-boot')
            self.assertFalse((home / 'diagnostics/instance.json').exists())


if __name__ == '__main__':
    unittest.main()
