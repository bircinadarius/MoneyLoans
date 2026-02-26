import requests
import sys
import json
from datetime import datetime, date

class MoneyLentTrackerAPITester:
    def __init__(self, base_url="https://money-owed-4.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.created_loan_id = None

    def log_test(self, name, success, response_data=None, error=None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
        
        result = {
            "test": name,
            "status": "PASS" if success else "FAIL",
            "response": response_data,
            "error": str(error) if error else None
        }
        self.test_results.append(result)
        
        status_icon = "✅" if success else "❌"
        print(f"{status_icon} {name}")
        if error:
            print(f"   Error: {error}")

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        if headers is None:
            headers = {'Content-Type': 'application/json'}

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=10)

            success = response.status_code == expected_status
            response_data = None
            
            try:
                response_data = response.json()
            except:
                response_data = response.text

            if not success:
                error = f"Expected {expected_status}, got {response.status_code}. Response: {response_data}"
                self.log_test(name, False, response_data, error)
                return False, {}
            
            self.log_test(name, True, response_data)
            return True, response_data

        except Exception as e:
            self.log_test(name, False, None, str(e))
            return False, {}

    def test_root_endpoint(self):
        """Test API root endpoint"""
        return self.run_test("API Root", "GET", "", 200)

    def test_dashboard_initial(self):
        """Test dashboard stats with no data"""
        success, data = self.run_test("Dashboard Stats (Empty)", "GET", "dashboard", 200)
        if success:
            required_fields = ['total_loaned', 'total_remaining', 'total_paid_back', 'active_loans', 'fully_paid_loans']
            for field in required_fields:
                if field not in data:
                    print(f"   Warning: Missing field '{field}' in dashboard response")
        return success, data

    def test_get_loans_empty(self):
        """Test get loans when empty"""
        return self.run_test("Get Loans (Empty)", "GET", "loans", 200)

    def test_create_loan(self):
        """Test creating a loan"""
        loan_data = {
            "person_name": "John Doe",
            "original_amount": 1000.00,
            "date": "2025-01-15",
            "notes": "Test loan for groceries"
        }
        success, data = self.run_test("Create Loan", "POST", "loans", 200, loan_data)
        if success and 'id' in data:
            self.created_loan_id = data['id']
            # Verify loan fields
            if data.get('remaining_amount') != loan_data['original_amount']:
                print(f"   Warning: remaining_amount should equal original_amount for new loan")
        return success, data

    def test_create_loan_invalid_data(self):
        """Test creating loan with invalid data"""
        invalid_data = {
            "person_name": "",  # Empty name
            "original_amount": -100,  # Negative amount
            "date": "invalid-date"
        }
        return self.run_test("Create Loan (Invalid)", "POST", "loans", 422, invalid_data)

    def test_get_loans_after_creation(self):
        """Test get loans after creating one"""
        success, data = self.run_test("Get Loans (After Creation)", "GET", "loans", 200)
        if success and isinstance(data, list) and len(data) > 0:
            print(f"   Found {len(data)} loan(s)")
        return success, data

    def test_get_single_loan(self):
        """Test get single loan by ID"""
        if not self.created_loan_id:
            print("❌ Get Single Loan - No loan ID available")
            return False, {}
        return self.run_test("Get Single Loan", "GET", f"loans/{self.created_loan_id}", 200)

    def test_get_nonexistent_loan(self):
        """Test get nonexistent loan"""
        return self.run_test("Get Nonexistent Loan", "GET", "loans/nonexistent-id", 404)

    def test_add_payment(self):
        """Test adding a payment to loan"""
        if not self.created_loan_id:
            print("❌ Add Payment - No loan ID available")
            return False, {}
        
        payment_data = {
            "amount": 250.00,
            "date": "2025-01-20",
            "note": "First payment"
        }
        success, data = self.run_test("Add Payment", "POST", f"loans/{self.created_loan_id}/payments", 200, payment_data)
        if success:
            # Check if remaining amount was updated correctly
            expected_remaining = 1000.00 - 250.00
            if abs(data.get('remaining_amount', 0) - expected_remaining) > 0.01:
                print(f"   Warning: Remaining amount calculation may be incorrect")
        return success, data

    def test_add_payment_exceeds_balance(self):
        """Test adding payment that exceeds remaining balance"""
        if not self.created_loan_id:
            print("❌ Add Payment (Exceeds) - No loan ID available")
            return False, {}
        
        payment_data = {
            "amount": 10000.00,  # More than remaining amount
            "date": "2025-01-21",
            "note": "Too much payment"
        }
        return self.run_test("Add Payment (Exceeds Balance)", "POST", f"loans/{self.created_loan_id}/payments", 400, payment_data)

    def test_add_negative_payment(self):
        """Test adding negative payment"""
        if not self.created_loan_id:
            print("❌ Add Negative Payment - No loan ID available")
            return False, {}
        
        payment_data = {
            "amount": -50.00,
            "date": "2025-01-21",
            "note": "Negative payment"
        }
        return self.run_test("Add Negative Payment", "POST", f"loans/{self.created_loan_id}/payments", 400, payment_data)

    def test_full_payment(self):
        """Test full payment to mark loan as paid"""
        if not self.created_loan_id:
            print("❌ Full Payment - No loan ID available")
            return False, {}
        
        # Get current loan state first
        success, loan_data = self.run_test("Get Loan Before Full Payment", "GET", f"loans/{self.created_loan_id}", 200)
        if not success:
            return False, {}
        
        remaining_amount = loan_data.get('remaining_amount', 0)
        payment_data = {
            "amount": remaining_amount,
            "date": "2025-01-22",
            "note": "Final payment"
        }
        
        success, data = self.run_test("Full Payment", "POST", f"loans/{self.created_loan_id}/payments", 200, payment_data)
        if success and data.get('remaining_amount', 1) != 0:
            print(f"   Warning: After full payment, remaining should be 0, got {data.get('remaining_amount')}")
        return success, data

    def test_dashboard_after_operations(self):
        """Test dashboard stats after loan operations"""
        success, data = self.run_test("Dashboard After Operations", "GET", "dashboard", 200)
        if success:
            print(f"   Total Loaned: ${data.get('total_loaned', 0)}")
            print(f"   Outstanding: ${data.get('total_remaining', 0)}")
            print(f"   Paid Back: ${data.get('total_paid_back', 0)}")
            print(f"   Active Loans: {data.get('active_loans', 0)}")
            print(f"   Fully Paid: {data.get('fully_paid_loans', 0)}")
        return success, data

    def test_delete_payment(self):
        """Test deleting a payment"""
        if not self.created_loan_id:
            print("❌ Delete Payment - No loan ID available")
            return False, {}
        
        # First get the loan to find a payment ID
        success, loan_data = self.run_test("Get Loan for Payment Deletion", "GET", f"loans/{self.created_loan_id}", 200)
        if not success or not loan_data.get('payments'):
            print("❌ Delete Payment - No payments found")
            return False, {}
        
        payment_id = loan_data['payments'][0]['id']
        success, data = self.run_test("Delete Payment", "DELETE", f"loans/{self.created_loan_id}/payments/{payment_id}", 200)
        return success, data

    def test_update_loan(self):
        """Test updating loan details"""
        if not self.created_loan_id:
            print("❌ Update Loan - No loan ID available")
            return False, {}
        
        update_data = {
            "person_name": "John Smith",
            "notes": "Updated notes for the loan"
        }
        return self.run_test("Update Loan", "PUT", f"loans/{self.created_loan_id}", 200, update_data)

    def test_delete_loan(self):
        """Test deleting a loan"""
        if not self.created_loan_id:
            print("❌ Delete Loan - No loan ID available")
            return False, {}
        
        return self.run_test("Delete Loan", "DELETE", f"loans/{self.created_loan_id}", 200)

    def test_delete_nonexistent_loan(self):
        """Test deleting nonexistent loan"""
        return self.run_test("Delete Nonexistent Loan", "DELETE", "loans/nonexistent-id", 404)

    def run_all_tests(self):
        """Run all API tests"""
        print(f"🚀 Starting Money Lent Tracker API Tests")
        print(f"📍 Base URL: {self.base_url}")
        print("=" * 60)

        # Basic API tests
        self.test_root_endpoint()
        self.test_dashboard_initial()
        self.test_get_loans_empty()

        # Loan CRUD tests
        self.test_create_loan()
        self.test_create_loan_invalid_data()
        self.test_get_loans_after_creation()
        self.test_get_single_loan()
        self.test_get_nonexistent_loan()
        self.test_update_loan()

        # Payment tests
        self.test_add_payment()
        self.test_add_payment_exceeds_balance()
        self.test_add_negative_payment()
        self.test_full_payment()
        self.test_delete_payment()

        # Dashboard tests
        self.test_dashboard_after_operations()

        # Cleanup tests
        self.test_delete_loan()
        self.test_delete_nonexistent_loan()

        # Final results
        print("=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print("❌ Some tests failed!")
            failed_tests = [r for r in self.test_results if r['status'] == 'FAIL']
            print(f"Failed tests: {len(failed_tests)}")
            for test in failed_tests:
                print(f"  - {test['test']}: {test['error']}")
            return 1

def main():
    tester = MoneyLentTrackerAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())