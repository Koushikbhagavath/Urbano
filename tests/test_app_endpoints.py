import unittest
import json
import uuid
import sys
import os

# Set target directory
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

try:
    from app import app, get_db_connection
except ImportError as e:
    print(f"Error: Could not import app.py. Make sure you run this script from the project directory. {e}")
    sys.exit(1)

class CleanCityAPITestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        self.created_users = []
        self.created_complaints = []

    def tearDown(self):
        # Clean up database records created during testing
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Delete test complaints
                for complaint_id in self.created_complaints:
                    cursor.execute("DELETE FROM complaint_status_history WHERE complaint_id = %s", (complaint_id,))
                    cursor.execute("DELETE FROM complaint_media WHERE complaint_id = %s", (complaint_id,))
                    cursor.execute("DELETE FROM complaints WHERE id = %s", (complaint_id,))
                
                # Delete test users
                for user_id in self.created_users:
                    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()
        except Exception as e:
            print(f"Warning: Error during test cleanup: {e}")
        finally:
            conn.close()

    def test_database_connection(self):
        """Test database connection is working."""
        try:
            conn = get_db_connection()
            self.assertIsNotNone(conn)
            conn.close()
        except Exception as e:
            self.fail(f"Database connection failed: {e}")

    def test_user_registration_and_login(self):
        """Test user registration, duplicate email handling, and user login."""
        unique_suffix = uuid.uuid4().hex[:8]
        test_email = f"test_{unique_suffix}@urbanotest.com"
        test_mobile = f"99{unique_suffix[:8]}"
        password = "SecurePassword123"

        # 1. Register User
        reg_payload = {
            "email": test_email,
            "mobile_number": test_mobile,
            "password": password,
            "name": "QA Tester",
            "age": 25,
            "gender": "Other",
            "address": "123 Testing Lane"
        }
        
        response = self.app.post("/api/register_user", 
                                 data=json.dumps(reg_payload),
                                 content_type="application/json")
        self.assertEqual(response.status_code, 201)
        res_data = json.loads(response.data)
        self.assertTrue(res_data.get("success"))

        # Fetch the created user ID for cleanup
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE email = %s", (test_email,))
                user_record = cursor.fetchone()
                if user_record:
                    user_id = user_record["id"]
                    self.created_users.append(user_id)
        finally:
            conn.close()

        # 2. Try duplicate registration
        response_dup = self.app.post("/api/register_user", 
                                     data=json.dumps(reg_payload),
                                     content_type="application/json")
        self.assertEqual(response_dup.status_code, 409)

        # 3. Test login with correct credentials
        login_payload = {
            "email": test_email,
            "password": password
        }
        response_login = self.app.post("/api/login_user",
                                       data=json.dumps(login_payload),
                                       content_type="application/json")
        self.assertEqual(response_login.status_code, 200)
        login_data = json.loads(response_login.data)
        self.assertTrue(login_data.get("success"))
        self.assertEqual(login_data.get("user_id"), user_id)

        # 4. Test login with invalid credentials
        bad_login = {
            "email": test_email,
            "password": "WrongPassword"
        }
        response_bad = self.app.post("/api/login_user",
                                     data=json.dumps(bad_login),
                                     content_type="application/json")
        self.assertEqual(response_bad.status_code, 401)

    def test_submit_and_fetch_complaint(self):
        """Test registering a complaint and fetching user complaints."""
        unique_suffix = uuid.uuid4().hex[:8]
        test_email = f"test_{unique_suffix}@urbanotest.com"
        test_mobile = f"99{unique_suffix[:8]}"
        password = "SecurePassword123"

        # Register a user first
        reg_payload = {
            "email": test_email,
            "mobile_number": test_mobile,
            "password": password,
            "name": "QA Tester",
            "age": 30,
            "gender": "Male",
            "address": "456 Mock Street"
        }
        self.app.post("/api/register_user", data=json.dumps(reg_payload), content_type="application/json")
        
        # Get user ID
        conn = get_db_connection()
        user_id = None
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE email = %s", (test_email,))
                user_record = cursor.fetchone()
                if user_record:
                    user_id = user_record["id"]
                    self.created_users.append(user_id)
        finally:
            conn.close()

        self.assertIsNotNone(user_id, "User registration failed inside complaint test setup.")

        # Submit Complaint
        complaint_payload = {
            "user_id": str(user_id),
            "title": "QA Test: Overflowing Garbage Bin",
            "details": "The community garbage bin in J P Nagar is overflowing. Needs immediate attention.",
            "landmark": "Near J P Nagar Park",
            "address": "J P Nagar Main Road",
            "city": "Mysore",
            "latitude": "12.2812",
            "longitude": "76.6432"
        }

        response = self.app.post("/api/submit_complaint", data=complaint_payload)
        self.assertEqual(response.status_code, 201)
        res_data = json.loads(response.data)
        self.assertTrue(res_data.get("success"))
        complaint_id = res_data.get("complaint_id")
        self.assertIsNotNone(complaint_id)
        self.created_complaints.append(complaint_id)

        # Fetch complaints for this user
        response_fetch = self.app.get(f"/api/user/complaints?user_id={user_id}")
        self.assertEqual(response_fetch.status_code, 200)
        fetch_data = json.loads(response_fetch.data)
        self.assertTrue(fetch_data.get("success"))
        complaints_list = fetch_data.get("complaints")
        self.assertTrue(len(complaints_list) > 0)
        self.assertEqual(complaints_list[0]["id"], complaint_id)

    def test_admin_and_online_status_endpoints(self):
        """Test admin statistics and real-time manager/department online status boards."""
        # 1. Test Admin Panel Route renders
        response_admin_page = self.app.get("/secure-admin-panel-hq-9921")
        self.assertEqual(response_admin_page.status_code, 200)

        # 2. Test Admin Stats Endpoint
        response_stats = self.app.get("/api/admin/stats")
        self.assertEqual(response_stats.status_code, 200)
        stats_data = json.loads(response_stats.data)
        self.assertTrue(stats_data.get("success"))
        self.assertIn("total_complaints", stats_data["stats"])
        self.assertIn("users", stats_data["stats"])
        self.assertIn("managers", stats_data["stats"])
        self.assertIn("departments", stats_data["stats"])

        # 3. Test Admin System Endpoint
        response_system = self.app.get("/api/admin/system")
        self.assertEqual(response_system.status_code, 200)
        system_data = json.loads(response_system.data)
        self.assertTrue(system_data.get("success"))
        self.assertIn("active_sessions", system_data["system"])
        self.assertIn("uptime_seconds", system_data["system"])
        self.assertIn("ip_address", system_data["system"])
        self.assertIn("mac_address", system_data["system"])

        # 4. Test Admin Online Status Board
        response_status_board = self.app.get("/api/admin/online_status")
        self.assertEqual(response_status_board.status_code, 200)
        status_data = json.loads(response_status_board.data)
        self.assertTrue(status_data.get("success"))
        self.assertIn("entities", status_data)

if __name__ == "__main__":
    unittest.main()
