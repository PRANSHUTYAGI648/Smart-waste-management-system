import os
import sys
import unittest
from app import app, init_sqlite_db, get_db_connection

class SmartWasteAPITestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
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

    def test_02_update_dustbin(self):
        payload = {"id": 1, "waste_level": 82}
        res = self.client.post('/api/update-dustbin', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'Full')
        print("[PASS] POST /api/update-dustbin passed")

    def test_03_route_optimization(self):
        res = self.client.get('/api/route-optimization')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('route', data)
        print(f"[PASS] GET /api/route-optimization passed ({data['bins_to_collect']} stops, {data['total_distance_km']} km)")

    def test_04_analytics(self):
        res = self.client.get('/api/analytics')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('avg_fill_level', data)
        print(f"[PASS] GET /api/analytics passed (Avg fill: {data['avg_fill_level']}%)")

    def test_05_add_and_delete_node(self):
        new_node = {
            "location": "UnitTest Innovation Lab",
            "bin_type": "E-Waste & Batteries",
            "capacity_liters": 100,
            "latitude": 28.6150,
            "longitude": 77.2095,
            "waste_level": 40
        }
        res = self.client.post('/api/dustbin/add', json=new_node)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        node_id = data['id']
        print(f"[PASS] POST /api/dustbin/add passed (Created Bin #{node_id})")

        del_res = self.client.delete(f'/api/dustbin/{node_id}')
        self.assertEqual(del_res.status_code, 200)
        del_data = del_res.get_json()
        self.assertTrue(del_data['success'])
        print(f"[PASS] DELETE /api/dustbin/{node_id} passed")

    def test_06_collect_dustbin(self):
        res = self.client.post('/collect/1')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        print("[PASS] POST /collect/1 passed")

    def test_07_export_csv(self):
        res = self.client.get('/api/export/csv')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'text/csv')
        print("[PASS] GET /api/export/csv passed")

if __name__ == '__main__':
    unittest.main()