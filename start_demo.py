# start_demo.py
"""
Demo Startup Script
===================

Simple script to help start the API server and frontend for demo purposes.
"""

import os
import sys
import subprocess
import time
import threading

def start_api_server():
    """Start the FastAPI server"""
    print("🚀 Starting API Server...")
    try:
        # Run the API server
        subprocess.run([
            sys.executable, "api_server.py"
        ], check=True)
    except KeyboardInterrupt:
        print("\n🛑 API Server stopped by user")
    except Exception as e:
        print(f"❌ API Server error: {e}")

def start_frontend():
    """Start the Streamlit frontend"""
    print("🌐 Starting Streamlit Frontend...")
    try:
        # Wait a bit for API server to start
        time.sleep(3)
        
        # Run streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "streamlit_frontend.py"
        ], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Frontend stopped by user")
    except Exception as e:
        print(f"❌ Frontend error: {e}")

def main():
    """Main demo startup"""
    print("🎬 Agno Multi-Agent Streaming Demo Startup")
    print("=" * 50)
    
    # Check if required files exist
    required_files = ["api_server.py", "streamlit_frontend.py", "multi_user_agents.py"]
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print(f"❌ Missing required files: {missing_files}")
        print("Please ensure all files are in the current directory.")
        return
    
    print("✅ All required files found")
    print("\n📋 Starting components:")
    print("   1. FastAPI server on http://127.0.0.1:8000")
    print("   2. Streamlit frontend on http://localhost:8501")
    print("\n⚡ Press Ctrl+C to stop both services")
    
    try:
        # Start API server in a separate thread
        api_thread = threading.Thread(target=start_api_server, daemon=True)
        api_thread.start()
        
        # Start frontend in main thread
        start_frontend()
        
    except KeyboardInterrupt:
        print("\n🛑 Demo stopped by user")
        print("👋 Thanks for trying the Agno Multi-Agent Streaming Demo!")

if __name__ == "__main__":
    main()