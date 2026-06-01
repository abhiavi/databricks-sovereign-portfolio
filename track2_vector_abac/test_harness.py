import time
import threading
import requests
import uvicorn
import sys
from vector_proxy import app

def start_server():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

def main():
    print("=" * 70)
    print("      NATOMA VECTOR ABAC PROXY: SECURITY INTEGRATION HARNESS")
    print("=" * 70)

    # 1. Spin up FastAPI server in a background daemon thread
    print("[Harness] Starting FastAPI proxy server in background...")
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    time.sleep(1.5)  # Allow server to initialize
    print("[Harness] Server started successfully on http://127.0.0.1:8000")

    base_url = "http://127.0.0.1:8000/v1/search"
    query_params = {"q": "financial budget"}

    success = True

    try:
        # Test Case A (High Privilege): token-finance
        print("\n" + "-" * 50)
        print("[TEST CASE A] High Privilege Authorization: 'token-finance'")
        print("-" * 50)
        headers_a = {"Authorization": "Bearer token-finance"}
        
        response_a = requests.get(base_url, params=query_params, headers=headers_a)
        print(f"HTTP Status Code: {response_a.status_code}")
        
        if response_a.status_code != 200:
            print(f"❌ Test Case A Failed with error response: {response_a.text}")
            success = False
        else:
            results_a = response_a.json().get("results", [])
            print(f"Retrieved {len(results_a)} document(s):")
            for doc in results_a:
                print(f"  - Document ID: {doc['id']}")
                print(f"    Title:       {doc['title']}")
                print(f"    Tags:        {doc['tags']}")
                print(f"    Content:     {doc['content']}")
                print(f"    Score:       {doc['score']:.4f}")
            
            # Verify we received FINANCE tagged documents
            finance_docs = [doc for doc in results_a if "FINANCE" in doc["tags"]]
            if not finance_docs:
                print("❌ Failure: Expected sensitive FINANCE documents but received none.")
                success = False
            else:
                print("✅ Success: Sensitive FINANCE documents successfully retrieved by authorized user.")

        # Test Case B (Low Privilege): token-public
        print("\n" + "-" * 50)
        print("[TEST CASE B] Low Privilege Authorization: 'token-public'")
        print("-" * 50)
        headers_b = {"Authorization": "Bearer token-public"}
        
        response_b = requests.get(base_url, params=query_params, headers=headers_b)
        print(f"HTTP Status Code: {response_b.status_code}")
        
        if response_b.status_code != 200:
            print(f"❌ Test Case B Failed with error response: {response_b.text}")
            success = False
        else:
            results_b = response_b.json().get("results", [])
            print(f"Retrieved {len(results_b)} document(s):")
            for doc in results_b:
                print(f"  - Document ID: {doc['id']}")
                print(f"    Title:       {doc['title']}")
                print(f"    Tags:        {doc['tags']}")
                print(f"    Content:     {doc['content']}")
                print(f"    Score:       {doc['score']:.4f}")
            
            # Verify NO FINANCE tagged documents are present
            finance_docs = [doc for doc in results_b if "FINANCE" in doc["tags"]]
            if finance_docs:
                print("❌ CRITICAL RLS VIOLATION: Sensitive FINANCE documents leaked to public user!")
                success = False
            else:
                print("✅ Success: Sensitive documents were pre-filtered and blocked.")

    except Exception as e:
        print(f"❌ Exception occurred during test run: {e}")
        success = False

    print("\n" + "=" * 70)
    if success:
        print("          VERIFICATION SUCCESSFUL: ALL SECURITY INVARIANTS MET")
        print("=" * 70)
        sys.exit(0)
    else:
        print("          VERIFICATION FAILED: SECURITY GAP DETECTED")
        print("=" * 70)
        sys.exit(1)

if __name__ == "__main__":
    main()
