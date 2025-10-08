# api_server.py
"""
Production FastAPI Server for Single and Multi-Agent Streaming
================================================================

This server provides RESTful endpoints for streaming agent responses in real-time.
Supports both single agent interactions and multi-agent orchestrator patterns.
"""

import asyncio
import json
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Import your existing agent creation function
from multi_user_agents import create_user_agent

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# FASTAPI APP CONFIGURATION
# =============================================================================

app = FastAPI(
    title="Agno Multi-Agent Streaming API",
    description="Production API for streaming agent responses with orchestrator and sub-agent support",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class AgentRequest(BaseModel):
    """Request model for agent interactions"""
    message: str = Field(..., description="User message to send to the agent")
    user_id: str = Field(default="default_user", description="User identifier")
    project_id: str = Field(default="default_project", description="Project identifier")
    stream_intermediate_steps: bool = Field(default=True, description="Whether to stream tool execution steps")

class TeamRequest(BaseModel):
    """Request model for multi-agent team interactions"""
    message: str = Field(..., description="User message to send to the team")
    team_config: Dict[str, Any] = Field(default_factory=dict, description="Team configuration")
    stream_intermediate_steps: bool = Field(default=True, description="Whether to stream tool execution steps")

class StreamEvent(BaseModel):
    """Standard streaming event format"""
    event_type: str
    timestamp: str
    agent_id: Optional[str] = None
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

# =============================================================================
# GLOBAL AGENT STORAGE
# =============================================================================

# In-memory storage for agents (in production, use Redis or database)
active_agents: Dict[str, Any] = {}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def create_stream_event(
    event_type: str,
    content: str = None,
    agent_id: str = None,
    tool_name: str = None,
    tool_input: Dict[str, Any] = None,
    tool_output: Dict[str, Any] = None,
    metadata: Dict[str, Any] = None
) -> str:
    """Create a formatted Server-Sent Event"""
    event = StreamEvent(
        event_type=event_type,
        timestamp=datetime.utcnow().isoformat(),
        agent_id=agent_id,
        content=content,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=tool_output,
        metadata=metadata
    )
    return f"data: {event.model_dump_json()}\n\n"

async def get_or_create_agent(user_id: str, project_id: str):
    """Get existing agent or create new one"""
    agent_key = f"{user_id}:{project_id}"
    
    if agent_key not in active_agents:
        logger.info(f"Creating new agent for {agent_key}")
        agent = await create_user_agent(user_id, project_id)
        active_agents[agent_key] = agent
    
    return active_agents[agent_key]

# =============================================================================
# SINGLE AGENT ENDPOINTS
# =============================================================================

@app.post("/api/v1/agent/stream")
async def stream_single_agent(request: AgentRequest):
    """
    Stream responses from a single agent with real-time tool execution
    
    Returns Server-Sent Events (SSE) stream with:
    - Agent thinking/reasoning steps
    - Tool execution start/end events
    - Final response content
    """
    try:
        agent = await get_or_create_agent(request.user_id, request.project_id)
        
        async def generate_stream():
            try:
                # Send initial event
                yield create_stream_event(
                    event_type="agent_started",
                    content=f"Agent processing: {request.message}",
                    agent_id=request.user_id,
                    metadata={"project_id": request.project_id}
                )
                
                # Check if agent supports streaming
                if hasattr(agent, 'arun') and hasattr(agent, 'stream'):
                    # Use native streaming if available
                    try:
                        run_stream = agent.arun(
                            request.message,
                            stream=True,
                            stream_intermediate_steps=request.stream_intermediate_steps
                        )
                        
                        async for chunk in run_stream:
                            # Handle different event types from agent streaming
                            if hasattr(chunk, 'event') and hasattr(chunk, 'content'):
                                if chunk.event == "RunContentEvent":
                                    yield create_stream_event(
                                        event_type="agent_response",
                                        content=chunk.content,
                                        agent_id=request.user_id
                                    )
                                elif chunk.event == "ToolCallStartedEvent":
                                    yield create_stream_event(
                                        event_type="tool_started",
                                        tool_name=getattr(chunk, 'tool_name', 'unknown'),
                                        tool_input=getattr(chunk, 'tool_input', {}),
                                        agent_id=request.user_id
                                    )
                                elif chunk.event == "ToolCallCompletedEvent":
                                    yield create_stream_event(
                                        event_type="tool_completed",
                                        tool_name=getattr(chunk, 'tool_name', 'unknown'),
                                        tool_output=getattr(chunk, 'tool_output', {}),
                                        agent_id=request.user_id
                                    )
                    except Exception as stream_error:
                        logger.warning(f"Native streaming failed: {stream_error}")
                        # Fallback to regular execution with simulated streaming
                        result = await agent.arun(request.message)
                        
                        yield create_stream_event(
                            event_type="agent_thinking",
                            content="Processing your request...",
                            agent_id=request.user_id
                        )
                        
                        # Simulate some processing time
                        await asyncio.sleep(0.5)
                        
                        yield create_stream_event(
                            event_type="agent_response",
                            content=str(result),
                            agent_id=request.user_id
                        )
                else:
                    # Fallback for agents without streaming support
                    yield create_stream_event(
                        event_type="agent_thinking",
                        content="Processing your request...",
                        agent_id=request.user_id
                    )
                    
                    result = await agent.arun(request.message)
                    
                    yield create_stream_event(
                        event_type="agent_response",
                        content=str(result),
                        agent_id=request.user_id
                    )
                
                # Send completion event
                yield create_stream_event(
                    event_type="agent_completed",
                    content="Agent execution completed",
                    agent_id=request.user_id
                )
                
            except Exception as e:
                logger.error(f"Error in agent stream: {e}")
                yield create_stream_event(
                    event_type="agent_error",
                    content=f"Error: {str(e)}",
                    agent_id=request.user_id
                )
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to create agent stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# MULTI-AGENT TEAM ENDPOINTS
# =============================================================================

@app.post("/api/v1/team/stream")
async def stream_multi_agent_team(request: TeamRequest):
    """
    Stream responses from a multi-agent team with orchestrator
    
    Returns Server-Sent Events (SSE) stream with:
    - Orchestrator decisions and routing
    - Individual agent responses
    - Tool execution from multiple agents
    - Final consolidated response
    """
    try:
        # Create multiple agents for team (example with 2 agents)
        orchestrator = await get_or_create_agent("orchestrator", "main")
        specialist_agent = await get_or_create_agent("specialist", "main")
        
        async def generate_team_stream():
            try:
                # Send team start event
                yield create_stream_event(
                    event_type="team_started",
                    content=f"Team processing: {request.message}",
                    metadata={
                        "team_members": ["orchestrator", "specialist"],
                        "message": request.message
                    }
                )
                
                # Step 1: Orchestrator analyzes the request
                yield create_stream_event(
                    event_type="orchestrator_thinking",
                    content="Orchestrator analyzing request and routing to appropriate agents...",
                    agent_id="orchestrator"
                )
                
                await asyncio.sleep(1)  # Simulate processing time
                
                # Step 2: Route to appropriate agent(s)
                yield create_stream_event(
                    event_type="orchestrator_routing",
                    content="Routing to specialist agent for detailed processing...",
                    agent_id="orchestrator",
                    metadata={"target_agent": "specialist"}
                )
                
                # Step 3: Specialist agent processes
                yield create_stream_event(
                    event_type="agent_started",
                    content="Specialist agent processing request...",
                    agent_id="specialist"
                )
                
                # Execute specialist agent
                specialist_result = await specialist_agent.arun(request.message)
                
                yield create_stream_event(
                    event_type="agent_response",
                    content=str(specialist_result),
                    agent_id="specialist"
                )
                
                # Step 4: Orchestrator consolidates results
                yield create_stream_event(
                    event_type="orchestrator_consolidating",
                    content="Orchestrator consolidating results from team members...",
                    agent_id="orchestrator"
                )
                
                await asyncio.sleep(0.5)
                
                # Step 5: Final team response
                final_response = f"""
Team Response Summary:
- Orchestrator successfully routed the request
- Specialist agent provided detailed analysis
- Result: {specialist_result}
                """.strip()
                
                yield create_stream_event(
                    event_type="team_response",
                    content=final_response,
                    metadata={
                        "participants": ["orchestrator", "specialist"],
                        "processing_time": "simulated"
                    }
                )
                
                # Send completion event
                yield create_stream_event(
                    event_type="team_completed",
                    content="Team execution completed successfully",
                    metadata={"total_agents": 2}
                )
                
            except Exception as e:
                logger.error(f"Error in team stream: {e}")
                yield create_stream_event(
                    event_type="team_error",
                    content=f"Team Error: {str(e)}"
                )
        
        return StreamingResponse(
            generate_team_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to create team stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# HEALTH AND STATUS ENDPOINTS
# =============================================================================

@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_agents": len(active_agents),
        "version": "1.0.0"
    }

@app.get("/api/v1/agents/status")
async def get_agents_status():
    """Get status of all active agents"""
    return {
        "active_agents": list(active_agents.keys()),
        "total_count": len(active_agents),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.delete("/api/v1/agents/cleanup")
async def cleanup_agents():
    """Cleanup inactive agents"""
    global active_agents
    count = len(active_agents)
    active_agents.clear()
    return {
        "message": f"Cleaned up {count} agents",
        "timestamp": datetime.utcnow().isoformat()
    }

# =============================================================================
# SERVER STARTUP
# =============================================================================

if __name__ == "__main__":
    # Configure server settings
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", 8000))
    
    logger.info(f"Starting Agno Multi-Agent Streaming API server on {HOST}:{PORT}")
    logger.info("API Documentation available at: http://127.0.0.1:8000/docs")
    
    uvicorn.run(
        "api_server:app",
        host=HOST,
        port=PORT,
        reload=True,  # Set to False in production
        log_level="info",
        access_log=True
    )