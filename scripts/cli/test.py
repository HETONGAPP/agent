"""
Testing commands
"""

import os
from datetime import datetime

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


def print_header(title):
    """Print section header"""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def test_agent():
    """Run Agent test suite"""
    if not REQUESTS_AVAILABLE:
        print("✗ Error: requests package not installed")
        return False

    print_header("BESS AI Agent Test Suite")

    agent_url = os.getenv("AGENT_URL", "http://localhost:8000")
    timeout = 10

    print(f"Agent URL: {agent_url}")
    print(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    results = []

    # Test health
    print("=" * 60)
    print("1. Health Check Test")
    print("=" * 60)
    try:
        response = requests.get(f"{agent_url}/health", timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Service status: {data.get('status')}")
            print(f"✓ InfluxDB connected: {data.get('influxdb_connected')}")
            results.append(("Health Check", True))
        else:
            print(f"✗ Health check failed: {response.status_code}")
            results.append(("Health Check", False))
    except Exception as e:
        print(f"✗ Cannot connect: {e}")
        results.append(("Health Check", False))

    # Test collect
    print("\n" + "=" * 60)
    print("2. Data Collection Test")
    print("=" * 60)
    try:
        response = requests.post(f"{agent_url}/api/collect", timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Status: {data.get('status')}")
            print(f"✓ Alarm count: {data.get('alarms_count', 0)}")
            print(f"✓ InfluxDB written: {data.get('influxdb_written', False)}")
            results.append(("Data Collection", True))
        else:
            print(f"✗ Failed: {response.status_code}")
            results.append(("Data Collection", False))
    except Exception as e:
        print(f"✗ Error: {e}")
        results.append(("Data Collection", False))

    # Test get alarms
    print("\n" + "=" * 60)
    print("3. Get Alarms Test")
    print("=" * 60)
    try:
        response = requests.get(f"{agent_url}/api/alarms", timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            alarms = data.get("alarms", [])
            print(f"✓ Status: {data.get('status')}")
            print(f"✓ Alarm count: {len(alarms)}")
            results.append(("Get Alarms", True))
        else:
            print(f"✗ Failed: {response.status_code}")
            results.append(("Get Alarms", False))
    except Exception as e:
        print(f"✗ Error: {e}")
        results.append(("Get Alarms", False))

    # Test get BMS data
    print("\n" + "=" * 60)
    print("4. Get BMS Data Test")
    print("=" * 60)
    try:
        response = requests.get(
            f"{agent_url}/api/bms-data?pack_id=PACK_001", timeout=timeout
        )
        if response.status_code == 200:
            data = response.json()
            bms = data.get("bms_data", {})
            print(f"✓ Status: {data.get('status')}")
            print(f"✓ Pack ID: {bms.get('pack_id')}")
            print(f"✓ SOC: {bms.get('soc')}%")
            results.append(("Get BMS Data", True))
        else:
            print(f"✗ Failed: {response.status_code}")
            results.append(("Get BMS Data", False))
    except Exception as e:
        print(f"✗ Error: {e}")
        results.append(("Get BMS Data", False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ Passed" if result else "✗ Failed"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return True
    else:
        print(f"\n⚠ {total - passed} tests failed")
        return False
