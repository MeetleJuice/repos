"""Removable feature tests: no existing test or application state is edited."""
from pathlib import Path
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from forge.core import Workbench
from forge.server import make_server


class DashboardRoutesTests(unittest.TestCase):
    def test_graph_source_references_and_endpoint_coverage(self):
        feature=Path(__file__).parent;root=feature.parents[1]
        graph=json.loads((feature/'src/graph.json').read_text())
        for node in graph['nodes']:
            lines=(root/node['source']).read_text().splitlines()
            # The single registration line can shift later line references only;
            # mapped server sites precede that seam.
            self.assertEqual(lines[node['line']-1][:280],node['excerpt'],node['label'])
        endpoints=json.loads((feature/'docs/endpoints.json').read_text())
        labels={node['label'] for node in graph['nodes']}
        for method,path,*_ in endpoints:self.assertIn(method+' '+path,labels)
        self.assertEqual(len(endpoints),37)

    def test_exact_allowlist_host_guard_and_unchanged_api(self):
        with tempfile.TemporaryDirectory() as temp:
            server=make_server(0,Workbench(Path(temp)/'projects'))
            threading.Thread(target=server.serve_forever,daemon=True).start()
            base='http://127.0.0.1:'+str(server.server_port)
            try:
                for path in ['/dashboard','/dashboard/','/dashboard/assets/app.js','/dashboard/assets/app.css','/dashboard/assets/elk-worker.js','/dashboard/launcher.js','/dashboard/launcher.css','/dashboard/map']:
                    with urllib.request.urlopen(base+path) as response:
                        self.assertEqual(response.status,200)
                        self.assertIn("worker-src 'self'",response.headers['Content-Security-Policy'])
                        self.assertEqual(response.headers['X-Frame-Options'],'DENY')
                        self.assertTrue(response.read())
                for path in ['/dashboard/.env','/dashboard/../server.py','/dashboard/package.json','/dashboard/assets/no.js']:
                    with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(base+path)
                    self.assertEqual(caught.exception.code,404);caught.exception.close()
                request=urllib.request.Request(base+'/dashboard',headers={'Host':'attacker.example'})
                with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(request)
                self.assertEqual(caught.exception.code,403);caught.exception.close()
                request=urllib.request.Request(base+'/api/projects',data=b'{}',headers={'Content-Type':'application/json'})
                with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(request)
                self.assertEqual(caught.exception.code,403);caught.exception.close()
                self.assertEqual(server.workbench.list_projects(),[])
            finally:server.shutdown();server.server_close()

    def test_dashboard_is_served_and_workbench_has_a_separate_tab_link(self):
        with tempfile.TemporaryDirectory() as temp:
            server=make_server(0,Workbench(Path(temp)/'projects'))
            threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                base='http://127.0.0.1:'+str(server.server_port)
                try:
                    with urllib.request.urlopen(base+'/dashboard') as response:
                        html=response.read().decode()
                        self.assertEqual(response.status,200)
                        self.assertIn('ifd-root',html)
                except urllib.error.HTTPError as error:
                    self.fail('Dashboard route should return 200; got HTTP '+str(error.code))
                with urllib.request.urlopen(base) as response:
                    html=response.read().decode()
                    self.assertIn('<button id="open-dashboard"',html)
                    self.assertIn('src="/dashboard/launcher.js"',html)
                    self.assertIn('href="/dashboard/launcher.css"',html)
                    self.assertIn('href="/dashboard"',html)
                    self.assertNotIn("unsafe-inline",response.headers['Content-Security-Policy'])
                with urllib.request.urlopen(base+'/health') as response:self.assertEqual(response.status,200)
            finally:server.shutdown();server.server_close()
