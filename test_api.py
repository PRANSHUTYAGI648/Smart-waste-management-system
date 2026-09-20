import os
import sys
import unittest
from app import app, init_sqlite_db, get_db_connection

class SmartWasteAPITestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.secret_key = 'test_secret_key'
        self.client = app.test_client()
        init_sqlite_db()

    def test_01_get_dustbins(self):
        res = self.client.get('/api/dustbins')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'] if 'success' in data else True)
        self.assertIn('dustbins', data)
        self.assertGreater(len(data['dustbins']), 0)
        print(f"[PASS] GET /api/dustbins passed ({len(data['dustbins'])} bins found)")

    def test_02_login_admin(self):
        res = self.client.post('/login', data={
            'email': 'admin@smartwaste.com',
            'password': 'admin123'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        print("[PASS] POST /login admin credentials passed")

    def test_03_route_optimization(self):
        res = self.client.get('/api/route-optimization')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('route', data)
        print(f"[PASS] GET /api/route-optimization passed ({data['bins_to_collect']} stops, {data['total_distance_km']} km)")

    def test_04_ai_predictions(self):
        res = self.client.get('/api/predictions')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('predictions', data)
        print(f"[PASS] GET /api/predictions passed ({len(data['predictions'])} predictions calculated)")

    def test_05_citizen_report(self):
        report_data = {
            "dustbin_id": 1,
            "location_name": "Main Gate",
            "issue_type": "Overflowing Waste Bin",
            "description": "Bin is overflowing onto sidewalk.",
            "reporter_name": "Test Resident",
            "reporter_contact": "resident@example.com"
        }
        res = self.client.post('/api/citizen-report', json=report_data)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        report_id = data['report_id']
        print(f"[PASS] POST /api/citizen-report passed (Ticket #{report_id})")

        list_res = self.client.get('/api/citizen-reports')
        self.assertEqual(list_res.status_code, 200)

        resolve_res = self.client.post(f'/api/citizen-report/resolve/{report_id}')
        self.assertEqual(resolve_res.status_code, 200)
        print(f"[PASS] POST /api/citizen-report/resolve/{report_id} passed")

    def test_06_portal_routes(self):
        self.assertEqual(self.client.get('/report').status_code, 200)
        self.assertEqual(self.client.get('/simulator').status_code, 200)
        print("[PASS] Multi-portal pages rendering passed (/report, /simulator)")

    def test_07_export_csv(self):
        res = self.client.get('/api/export/csv')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'text/csv')
        print("[PASS] GET /api/export/csv passed")

if __name__ == '__main__':
    unittest.main()