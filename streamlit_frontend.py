# streamlit_frontend.py
"""
Streamlit Frontend for Agno Multi-Agent Streaming
=================================================

Interactive web interface to demonstrate real-time streaming from both
single agents and multi-agent teams with live event visualization.
"""

import streamlit as st
import requests
import json
import time
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, Any, List
import pandas as pd

# =============================================================================
# STREAMLIT CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="Agno Multi-Agent Streaming Demo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# CONFIGURATION
# =============================================================================

API_BASE_URL = "http://127.0.0.1:8000"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def parse_sse_event(line: str) -> Dict[str, Any]:
    """Parse Server-Sent Event line"""
    if line.startswith("data: "):
        try:
            data = json.loads(line[6:])  # Remove "data: " prefix
            return data
        except json.JSONDecodeError:
            return {"error": "Failed to parse JSON", "raw": line}
    return None

def format_event_for_display(event: Dict[str, Any]) -> str:
    """Format event for display in Streamlit"""
    event_type = event.get("event_type", "unknown")
    timestamp = event.get("timestamp", "")
    agent_id = event.get("agent_id", "unknown")
    content = event.get("content", "")
    
    # Format timestamp
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        time_str = dt.strftime("%H:%M:%S")
    except:
        time_str = timestamp[:8] if timestamp else "unknown"
    
    # Create formatted string based on event type
    if event_type == "agent_started":
        return f"🚀 **[{time_str}]** Agent `{agent_id}` started: {content}"
    elif event_type == "agent_thinking":
        return f"🤔 **[{time_str}]** Agent `{agent_id}` thinking: {content}"
    elif event_type == "agent_response":
        return f"💬 **[{time_str}]** Agent `{agent_id}` response:\n\n{content}"
    elif event_type == "tool_started":
        tool_name = event.get("tool_name", "unknown")
        return f"🔧 **[{time_str}]** Tool `{tool_name}` started by `{agent_id}`"
    elif event_type == "tool_completed":
        tool_name = event.get("tool_name", "unknown")
        return f"✅ **[{time_str}]** Tool `{tool_name}` completed by `{agent_id}`"
    elif event_type == "orchestrator_thinking":
        return f"🧠 **[{time_str}]** Orchestrator: {content}"
    elif event_type == "orchestrator_routing":
        return f"🎯 **[{time_str}]** Orchestrator routing: {content}"
    elif event_type == "team_started":
        return f"👥 **[{time_str}]** Team started: {content}"
    elif event_type == "team_response":
        return f"🏆 **[{time_str}]** Team response:\n\n{content}"
    elif event_type == "team_completed":
        return f"🎉 **[{time_str}]** Team completed: {content}"
    elif event_type in ["agent_completed", "agent_error", "team_error"]:
        icon = "✅" if "completed" in event_type else "❌"
        return f"{icon} **[{time_str}]** {event_type.replace('_', ' ').title()}: {content}"
    else:
        return f"ℹ️ **[{time_str}]** {event_type}: {content}"

def stream_request(url: str, data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Make streaming request and return list of events"""
    events = []
    try:
        response = requests.post(
            url,
            json=data,
            stream=True,
            headers={"Accept": "text/event-stream"},
            timeout=30
        )
        response.raise_for_status()
        
        for line in response.iter_lines(decode_unicode=True):
            if line:
                event = parse_sse_event(line)
                if event:
                    events.append(event)
                    yield event
                    
    except requests.exceptions.RequestException as e:
        error_event = {
            "event_type": "connection_error",
            "content": f"Connection error: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }
        events.append(error_event)
        yield error_event

# =============================================================================
# MAIN STREAMLIT APP
# =============================================================================

def main():
    st.title("🤖 Agno Multi-Agent Streaming Demo")
    st.markdown("Real-time streaming interface for single agents and multi-agent teams")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # API Server Status
        st.subheader("API Server Status")
        try:
            health_response = requests.get(f"{API_BASE_URL}/api/v1/health", timeout=5)
            if health_response.status_code == 200:
                health_data = health_response.json()
                st.success("✅ API Server Online")
                st.json(health_data)
            else:
                st.error("❌ API Server Error")
        except:
            st.error("❌ API Server Offline")
            st.warning("Make sure to run: `python api_server.py`")
        
        st.divider()
        
        # User Configuration
        st.subheader("User Settings")
        user_id = st.text_input("User ID", value="demo_user")
        project_id = st.text_input("Project ID", value="demo_project")
        
        st.subheader("Stream Settings")
        stream_intermediate = st.checkbox("Stream Intermediate Steps", value=True)
        
        # Clear logs button
        if st.button("🗑️ Clear Logs"):
            if 'single_events' in st.session_state:
                st.session_state.single_events = []
            if 'team_events' in st.session_state:
                st.session_state.team_events = []
            st.rerun()
    
    # Main content area with tabs
    tab1, tab2, tab3 = st.tabs(["🤖 Single Agent", "👥 Multi-Agent Team", "📊 Event Analytics"])
    
    # =============================================================================
    # SINGLE AGENT TAB
    # =============================================================================
    
    with tab1:
        st.header("Single Agent Streaming")
        st.markdown("Test streaming responses from a single agent with real-time tool execution visibility.")
        
        # Input form
        with st.form("single_agent_form"):
            message = st.text_area(
                "Enter your message:",
                placeholder="e.g., Can you check if ripgrep and fd-find are installed and show their versions?",
                height=100
            )
            submitted = st.form_submit_button("🚀 Send to Agent", use_container_width=True)
        
        if submitted and message:
            # Initialize session state for events
            if 'single_events' not in st.session_state:
                st.session_state.single_events = []
            
            # Create containers for real-time updates
            status_container = st.empty()
            events_container = st.empty()
            
            # Prepare request
            request_data = {
                "message": message,
                "user_id": user_id,
                "project_id": project_id,
                "stream_intermediate_steps": stream_intermediate
            }
            
            url = f"{API_BASE_URL}/api/v1/agent/stream"
            
            # Stream events
            status_container.info("🔄 Connecting to agent...")
            
            try:
                event_count = 0
                for event in stream_request(url, request_data):
                    event_count += 1
                    st.session_state.single_events.append(event)
                    
                    # Update status
                    event_type = event.get("event_type", "unknown")
                    if event_type == "agent_started":
                        status_container.info("🤖 Agent is processing your request...")
                    elif event_type == "tool_started":
                        tool_name = event.get("tool_name", "unknown")
                        status_container.warning(f"🔧 Executing tool: {tool_name}")
                    elif event_type == "agent_completed":
                        status_container.success("✅ Agent completed successfully!")
                    elif "error" in event_type:
                        status_container.error(f"❌ Error: {event.get('content', 'Unknown error')}")
                    
                    # Update events display
                    events_markdown = "## 📜 Event Stream\n\n"
                    for i, evt in enumerate(reversed(st.session_state.single_events[-10:])):  # Show last 10 events
                        events_markdown += format_event_for_display(evt) + "\n\n---\n\n"
                    
                    events_container.markdown(events_markdown)
                    
                    # Small delay for visual effect
                    time.sleep(0.1)
                
                status_container.success(f"✅ Stream completed! Received {event_count} events.")
                
            except Exception as e:
                status_container.error(f"❌ Stream error: {str(e)}")
    
    # =============================================================================
    # MULTI-AGENT TEAM TAB
    # =============================================================================
    
    with tab2:
        st.header("Multi-Agent Team Streaming")
        st.markdown("Watch how an orchestrator coordinates multiple agents to handle complex requests.")
        
        # Input form
        with st.form("team_form"):
            team_message = st.text_area(
                "Enter your team request:",
                placeholder="e.g., Create a landing page for a tech startup with hero section and contact form",
                height=100
            )
            team_submitted = st.form_submit_button("👥 Send to Team", use_container_width=True)
        
        if team_submitted and team_message:
            # Initialize session state for team events
            if 'team_events' not in st.session_state:
                st.session_state.team_events = []
            
            # Create containers for real-time updates
            team_status_container = st.empty()
            team_events_container = st.empty()
            
            # Create columns for orchestrator and agents
            col1, col2 = st.columns(2)
            
            with col1:
                orchestrator_container = st.empty()
            with col2:
                agents_container = st.empty()
            
            # Prepare request
            team_request_data = {
                "message": team_message,
                "team_config": {},
                "stream_intermediate_steps": stream_intermediate
            }
            
            team_url = f"{API_BASE_URL}/api/v1/team/stream"
            
            # Stream team events
            team_status_container.info("🔄 Connecting to team...")
            
            try:
                team_event_count = 0
                orchestrator_events = []
                agent_events = []
                
                for event in stream_request(team_url, team_request_data):
                    team_event_count += 1
                    st.session_state.team_events.append(event)
                    
                    # Categorize events
                    event_type = event.get("event_type", "unknown")
                    agent_id = event.get("agent_id", "")
                    
                    if "orchestrator" in event_type or agent_id == "orchestrator":
                        orchestrator_events.append(event)
                    else:
                        agent_events.append(event)
                    
                    # Update status
                    if event_type == "team_started":
                        team_status_container.info("👥 Team is processing your request...")
                    elif event_type == "orchestrator_thinking":
                        team_status_container.warning("🧠 Orchestrator is analyzing the request...")
                    elif event_type == "orchestrator_routing":
                        team_status_container.warning("🎯 Orchestrator is routing to specialists...")
                    elif event_type == "team_completed":
                        team_status_container.success("✅ Team completed successfully!")
                    elif "error" in event_type:
                        team_status_container.error(f"❌ Error: {event.get('content', 'Unknown error')}")
                    
                    # Update orchestrator display
                    orch_markdown = "### 🧠 Orchestrator Activity\n\n"
                    for evt in orchestrator_events[-5:]:  # Last 5 events
                        orch_markdown += format_event_for_display(evt) + "\n\n"
                    orchestrator_container.markdown(orch_markdown)
                    
                    # Update agents display
                    agents_markdown = "### 🤖 Agent Activity\n\n"
                    for evt in agent_events[-5:]:  # Last 5 events
                        agents_markdown += format_event_for_display(evt) + "\n\n"
                    agents_container.markdown(agents_markdown)
                    
                    # Update full events display
                    team_events_markdown = "## 📜 Complete Team Event Stream\n\n"
                    for evt in reversed(st.session_state.team_events[-8:]):  # Show last 8 events
                        team_events_markdown += format_event_for_display(evt) + "\n\n---\n\n"
                    
                    team_events_container.markdown(team_events_markdown)
                    
                    # Small delay for visual effect
                    time.sleep(0.2)
                
                team_status_container.success(f"✅ Team stream completed! Received {team_event_count} events.")
                
            except Exception as e:
                team_status_container.error(f"❌ Team stream error: {str(e)}")
    
    # =============================================================================
    # ANALYTICS TAB
    # =============================================================================
    
    with tab3:
        st.header("📊 Event Analytics")
        st.markdown("Analyze streaming events and performance metrics.")
        
        # Combine all events for analysis
        all_events = []
        if 'single_events' in st.session_state:
            for event in st.session_state.single_events:
                event['source'] = 'Single Agent'
                all_events.append(event)
        
        if 'team_events' in st.session_state:
            for event in st.session_state.team_events:
                event['source'] = 'Multi-Agent Team'
                all_events.append(event)
        
        if all_events:
            # Create DataFrame for analysis
            df = pd.DataFrame(all_events)
            
            # Event type distribution
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Event Type Distribution")
                event_counts = df['event_type'].value_counts()
                st.bar_chart(event_counts)
            
            with col2:
                st.subheader("Events by Source")
                source_counts = df['source'].value_counts()
                st.bar_chart(source_counts)
            
            # Recent events table
            st.subheader("Recent Events")
            display_columns = ['timestamp', 'event_type', 'agent_id', 'source']
            available_columns = [col for col in display_columns if col in df.columns]
            st.dataframe(df[available_columns].tail(20), use_container_width=True)
            
            # Event timeline
            if 'timestamp' in df.columns:
                st.subheader("Event Timeline")
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df_timeline = df.set_index('timestamp')
                st.line_chart(df_timeline.groupby([df_timeline.index.floor('1s'), 'source']).size().unstack(fill_value=0))
        
        else:
            st.info("No events to analyze yet. Try sending requests to agents in the other tabs!")

# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

if 'single_events' not in st.session_state:
    st.session_state.single_events = []

if 'team_events' not in st.session_state:
    st.session_state.team_events = []

# =============================================================================
# RUN APP
# =============================================================================

if __name__ == "__main__":
    main()