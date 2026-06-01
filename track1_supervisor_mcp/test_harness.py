import threading
import time
import requests
import uvicorn
import sys
from mcp_proxy import app, validator

def run_server():
    # Start FastAPI server on 127.0.0.1:8001
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="warning")

def main():
    print("=== STARTING DATABRICKS SUPERVISOR AGENT TEST HARNESS ===")
    
    # 1. Start Server in background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    print("[INFO] Waiting for FastAPI server to initialize...")
    time.sleep(2)  # Give uvicorn a moment to start
    
    # 2. Generate Tokens using the shared public key set of the proxy
    print("[INFO] Generating mock signatures...")
    analyst_token = validator.generate_mock_token({
        "sub": "analyst_abhishek",
        "metadata_containment": {
            "allowed_catalogs": ["prod_finance"],
            "allowed_actions": ["SELECT_ONLY", "DESCRIBE_ONLY"]
        }
    })
    
    admin_token = validator.generate_mock_token({
        "sub": "admin_system",
        "metadata_containment": {
            "allowed_catalogs": ["prod_finance", "dev_sandbox"],
            "allowed_actions": ["SELECT_ONLY", "DESCRIBE_ONLY"]
        }
    })
    
    mcp_endpoint = "http://127.0.0.1:8001/v1/mcp/tools/call"
    
    # Define test payloads
    # payload_a: Valid Read
    payload_a = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "query_unity_catalog",
            "arguments": {
                "catalog": "prod_finance",
                "sql_query": "SELECT asset_name, allocation FROM holdings WHERE risk_score < 5"
            }
        },
        "id": 101
    }
    
    # payload_b: Malicious SQL injection (drop table)
    payload_b = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "query_unity_catalog",
            "arguments": {
                "catalog": "prod_finance",
                "sql_query": "SELECT * FROM holdings; DROP TABLE users;"
            }
        },
        "id": 102
    }
    
    # payload_c: Cross-tenant catalog access (dev_sandbox access attempted by analyst)
    payload_c = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "query_unity_catalog",
            "arguments": {
                "catalog": "dev_sandbox",
                "sql_query": "SELECT * FROM audit_logs"
            }
        },
        "id": 103
    }
    
    # payload_d: Egress failure timeout simulation (contains TIMEOUT_TEST keyword)
    payload_d = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "query_unity_catalog",
            "arguments": {
                "catalog": "prod_finance",
                "sql_query": "SELECT * FROM holdings TIMEOUT_TEST"
            }
        },
        "id": 104
    }

    # ==========================================
    # RUN TESTS
    # ==========================================
    tests_failed = False
    
    # Test A: Valid Read
    print("\n--- TEST A: Valid Read ---")
    headers = {"Authorization": f"Bearer {analyst_token}"}
    r = requests.post(mcp_endpoint, json=payload_a, headers=headers)
    print(f"Status Code: {r.status_code}")
    print(f"Response: {r.json()}")
    if r.status_code != 200 or "error" in r.json():
        print("❌ TEST A FAILED!")
        tests_failed = True
    else:
        print("✅ TEST A PASSED (Proxy successfully validated token & routed query to Oracle Egress)")

    # Test B: Malicious Write Injection (DROP TABLE)
    print("\n--- TEST B: Malicious Write/Injection ---")
    headers = {"Authorization": f"Bearer {analyst_token}"}
    r = requests.post(mcp_endpoint, json=payload_b, headers=headers)
    print(f"Status Code: {r.status_code}")
    print(f"Response: {r.json()}")
    if r.status_code != 403 or r.json().get("error", {}).get("code") != -32004:
        print("❌ TEST B FAILED (Expected: 403 Forbidden with code -32004)")
        tests_failed = True
    else:
        print("✅ TEST B PASSED (Proxy successfully intercepted and blocked the DROP TABLE statement)")

    # Test C: Cross-Tenant Access attempt
    print("\n--- TEST C: Cross-Tenant Access ---")
    headers = {"Authorization": f"Bearer {analyst_token}"} # Analyst only has prod_finance
    r = requests.post(mcp_endpoint, json=payload_c, headers=headers)
    print(f"Status Code: {r.status_code}")
    print(f"Response: {r.json()}")
    if r.status_code != 403 or r.json().get("error", {}).get("code") != -32003:
        print("❌ TEST C FAILED (Expected: 403 Forbidden with code -32003)")
        tests_failed = True
    else:
        print("✅ TEST C PASSED (Proxy successfully blocked tenant data access escape)")

    # Test D: Egress Failure Timeout simulation
    print("\n--- TEST D: Egress Failure Timeout ---")
    headers = {"Authorization": f"Bearer {analyst_token}"}
    r = requests.post(mcp_endpoint, json=payload_d, headers=headers)
    print(f"Status Code: {r.status_code}")
    print(f"Response: {r.json()}")
    if r.status_code != 502 or r.json().get("error", {}).get("code") != -32099:
        print("❌ TEST D FAILED (Expected: 502 Bad Gateway with code -32099)")
        tests_failed = True
    else:
        print("✅ TEST D PASSED (Proxy caught egress error and returned safe JSON-RPC 2.0 gateway error)")

    print("\n=== TEST HARNESS EVALUATION COMPLETE ===")
    if tests_failed:
        print("❌ ONE OR MORE SECURITY INVARIANTS VIOLATED!")
        sys.exit(1)
    else:
        print("🟢 ALL SOVEREIGN BOUNDARY INVARIANTS HOLD!")
        sys.exit(0)

if __name__ == "__main__":
    main()
