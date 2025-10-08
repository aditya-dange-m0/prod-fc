# test_streaming_api.py
"""
Test script for the Agno Multi-Agent Streaming API
==================================================

Simple script to test both single agent and multi-agent streaming endpoints.
"""

import requests
import json
import time
from datetime import datetime

# Configuration
API_BASE_URL = "http://127.0.0.1:8000"

def test_health_check():
    """Test API health endpoint"""
    print("🔍 Testing API health check...")
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/health", timeout=5)
        if response.status_code == 200:
            print("✅ API Server is healthy!")
            print(json.dumps(response.json(), indent=2))
            return True
        else:
            print(f"❌ API health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to connect to API: {e}")
        print("Make sure the API server is running: python api_server.py")
        return False

def test_single_agent_streaming():
    """Test single agent streaming endpoint"""
    print("\n🤖 Testing Single Agent Streaming...")
    
    # Prepare request
    request_data = {
        "message": "Can you check if Python is installed and show its version?",
        "user_id": "test_user",
        "project_id": "test_project",
        "stream_intermediate_steps": True
    }
    
    url = f"{API_BASE_URL}/api/v1/agent/stream"
    
    try:
        print(f"📡 Sending request to: {url}")
        print(f"📝 Message: {request_data['message']}")
        print("📊 Streaming events:")
        print("-" * 50)
        
        response = requests.post(
            url,
            json=request_data,
            stream=True,
            headers={"Accept": "text/event-stream"},
            timeout=30
        )
        response.raise_for_status()
        
        event_count = 0
        for line in response.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                try:
                    event_data = json.loads(line[6:])  # Remove "data: " prefix
                    event_count += 1
                    
                    # Format event for display
                    event_type = event_data.get("event_type", "unknown")
                    timestamp = event_data.get("timestamp", "")
                    content = event_data.get("content", "")
                    agent_id = event_data.get("agent_id", "")
                    
                    # Extract time from timestamp
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        time_str = dt.strftime("%H:%M:%S")
                    except:
                        time_str = timestamp[:8] if timestamp else "unknown"
                    
                    print(f"[{time_str}] {event_type.upper():20} | {agent_id:12} | {content[:80]}")
                    
                    if event_type in ["agent_completed", "agent_error"]:
                        break
                        
                except json.JSONDecodeError as e:
                    print(f"⚠️  Failed to parse event: {e}")
        
        print("-" * 50)
        print(f"✅ Single agent streaming completed! Received {event_count} events.")
        return True
        
    except Exception as e:
        print(f"❌ Single agent streaming failed: {e}")
        return False

def test_multi_agent_streaming():
    """Test multi-agent team streaming endpoint"""
    print("\n👥 Testing Multi-Agent Team Streaming...")
    
    # Prepare request
    request_data = {
        "message": "Create a simple landing page for a tech startup",
        "team_config": {},
        "stream_intermediate_steps": True
    }
    
    url = f"{API_BASE_URL}/api/v1/team/stream"
    
    try:
        print(f"📡 Sending request to: {url}")
        print(f"📝 Message: {request_data['message']}")
        print("📊 Streaming events:")
        print("-" * 50)
        
        response = requests.post(
            url,
            json=request_data,
            stream=True,
            headers={"Accept": "text/event-stream"},
            timeout=60
        )
        response.raise_for_status()
        
        event_count = 0
        for line in response.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                try:
                    event_data = json.loads(line[6:])  # Remove "data: " prefix
                    event_count += 1
                    
                    # Format event for display
                    event_type = event_data.get("event_type", "unknown")
                    timestamp = event_data.get("timestamp", "")
                    content = event_data.get("content", "")
                    agent_id = event_data.get("agent_id", "unknown")
                    
                    # Extract time from timestamp
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        time_str = dt.strftime("%H:%M:%S")
                    except:
                        time_str = timestamp[:8] if timestamp else "unknown"
                    
                    # Add emoji based on event type
                    emoji = "🤖"
                    if "orchestrator" in event_type:
                        emoji = "🧠"
                    elif "team" in event_type:
                        emoji = "👥"
                    elif "tool" in event_type:
                        emoji = "🔧"
                    
                    print(f"{emoji} [{time_str}] {event_type.upper():25} | {agent_id:12} | {content[:70]}")
                    
                    if event_type in ["team_completed", "team_error"]:
                        break
                        
                except json.JSONDecodeError as e:
                    print(f"⚠️  Failed to parse event: {e}")
        
        print("-" * 50)
        print(f"✅ Multi-agent streaming completed! Received {event_count} events.")
        return True
        
    except Exception as e:
        print(f"❌ Multi-agent streaming failed: {e}")
        return False

def test_agents_status():
    """Test agents status endpoint"""
    print("\n📊 Testing Agents Status...")
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/agents/status", timeout=5)
        if response.status_code == 200:
            status_data = response.json()
            print("✅ Agents status retrieved!")
            print(json.dumps(status_data, indent=2))
            return True
        else:
            print(f"❌ Agents status failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to get agents status: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Agno Multi-Agent Streaming API Test Suite")
    print("=" * 60)
    
    # Test health check first
    if not test_health_check():
        print("\n❌ API server is not running. Please start it first:")
        print("   python api_server.py")
        return
    
    # Test single agent streaming
    single_success = test_single_agent_streaming()
    
    # Test multi-agent streaming
    multi_success = test_multi_agent_streaming()
    
    # Test status endpoint
    status_success = test_agents_status()
    
    # Summary
    print("\n" + "=" * 60)
    print("🏁 Test Results Summary")
    print("-" * 30)
    print(f"Health Check:      {'✅ PASS' if True else '❌ FAIL'}")
    print(f"Single Agent:      {'✅ PASS' if single_success else '❌ FAIL'}")
    print(f"Multi-Agent Team:  {'✅ PASS' if multi_success else '❌ FAIL'}")
    print(f"Agents Status:     {'✅ PASS' if status_success else '❌ FAIL'}")
    
    if all([single_success, multi_success, status_success]):
        print("\n🎉 All tests passed! Your streaming API is working correctly.")
        print("\n🚀 Next steps:")
        print("   1. Start the Streamlit frontend: streamlit run streamlit_frontend.py")
        print("   2. Open http://localhost:8501 in your browser")
        print("   3. Test the interactive interface")
    else:
        print("\n⚠️  Some tests failed. Check the error messages above.")

if __name__ == "__main__":
    main()