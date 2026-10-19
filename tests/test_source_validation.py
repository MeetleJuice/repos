"""Regression coverage from the uploaded dashboard's malformed repair responses."""
from pathlib import Path
import tempfile
import unittest
import threading
from tests.test_workbench import ScriptedModels
from forge.core import Workbench
from forge.inspection import inspect_files
from tests.test_cloud import state_for


class SourceValidationTests(unittest.TestCase):
    def test_bad_changed_files_never_replace_working_source(self):
        with tempfile.TemporaryDirectory() as directory:
            bench = Workbench(Path(directory))
            state = state_for(bench)
            source = bench.directory(state['id']) / 'source'
            original = 'def create_server(host, port):\n    return None\n'
            (source / 'app.py').write_text(original)
            for name, text in [('test_api.py','NEW file contents'), ('test_db.py','COMPLETE file contents'), ('app.py','def broken(:'), ('index.html',r'<html lang=\"en\">\n<body>broken</body></html>')]:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    bench.apply(state, {'files':{'app.py':original,name:text}})
                self.assertEqual((source / 'app.py').read_text(), original)
                if name != 'app.py': self.assertFalse((source / name).exists())
                self.assertFalse(state.get('snapshots'))

    def test_invalid_response_gets_one_complete_file_correction(self):
        with tempfile.TemporaryDirectory() as directory:
            models = ScriptedModels([{'files':{'test_api.py':'NEW file contents'}},
                                     {'files':{'test_api.py':'import app\n'}}])
            bench = Workbench(Path(directory), models)
            state = state_for(bench)
            state.update(next_task=0,snapshots=[])
            bench.generate_and_apply(state, {'files':{}}, threading.Event())
            self.assertEqual(len(models.calls),2)
            self.assertEqual(models.calls[1]['response_mode'],'complete_files')
            self.assertEqual(len(state['snapshots']),1)
            self.assertEqual(bench.files(state['id'])['test_api.py'],'import app\n')

    def test_database_unit_tests_can_import_real_project_module(self):
        result = inspect_files({'app.py':'def create_server(host, port): pass',
                                'db.py':'def get_project(): return 1',
                                'test_db.py':'import unittest\nimport db\nclass Tests(unittest.TestCase):\n def test_query(self): self.assertEqual(db.get_project(),1)\n'})
        self.assertTrue(result['passed'], result['issues'])
        result = inspect_files({'app.py':'def create_server(host, port): pass',
                                'test_fake.py':'import unittest\nclass Tests(unittest.TestCase):\n def test_fake(self): self.assertEqual(1,1)\n'})
        self.assertFalse(result['passed'])
