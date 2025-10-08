# Agno Multi-Agent Streaming API

Production-ready FastAPI server with streaming support for both single agents and multi-agent orchestrator systems, complete with a Streamlit frontend for real-time visualization.

## 🚀 Features

- **Single Agent Streaming**: Real-time streaming of agent responses with tool execution visibility
- **Multi-Agent Team Streaming**: Orchestrator + sub-agent coordination with live event tracking
- **Production API**: RESTful endpoints with proper error handling and monitoring
- **Interactive Frontend**: Streamlit web interface for testing and visualization
- **Real-time Events**: Server-Sent Events (SSE) for live streaming
- **Event Analytics**: Performance metrics and event analysis

## 📁 Project Structure

```
prod-fc/
├── multi_user_agents.py          # Original agent implementation (unchanged)
├── api_server.py                  # FastAPI streaming server
├── streamlit_frontend.py          # Streamlit web interface
├── requirements_api.txt           # Additional dependencies
└── README_API.md                  # This file
```

## 🛠️ Setup

### 1. Install Dependencies

```bash
# Install additional API dependencies
pip install -r requirements_api.txt
```

### 2. Environment Setup

Make sure your `.env` file contains the required API keys:

```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

## 🚀 Usage

### Starting the API Server

```bash
# Start the FastAPI server
python api_server.py
```

The API server will start on `http://127.0.0.1:8000`

- **API Documentation**: http://127.0.0.1:8000/docs
- **Alternative Docs**: http://127.0.0.1:8000/redoc

### Starting the Frontend

```bash
# In a new terminal, start the Streamlit frontend
streamlit run streamlit_frontend.py
```

The frontend will open in your browser at `http://localhost:8501`

## 📡 API Endpoints

### Single Agent Streaming

```http
POST /api/v1/agent/stream
Content-Type: application/json

{
  "message": "Your query here",
  "user_id": "demo_user",
  "project_id": "demo_project",
  "stream_intermediate_steps": true
}
```

**Response**: Server-Sent Events (SSE) stream with:
- `agent_started`: Agent begins processing
- `agent_thinking`: Agent reasoning steps
- `tool_started`: Tool execution begins
- `tool_completed`: Tool execution ends
- `agent_response`: Agent response content
- `agent_completed`: Processing finished

### Multi-Agent Team Streaming

```http
POST /api/v1/team/stream
Content-Type: application/json

{
  "message": "Your team query here",
  "team_config": {},
  "stream_intermediate_steps": true
}
```

**Response**: Server-Sent Events (SSE) stream with:
- `team_started`: Team processing begins
- `orchestrator_thinking`: Orchestrator analysis
- `orchestrator_routing`: Request routing decisions
- `agent_started`: Sub-agent begins processing
- `agent_response`: Sub-agent responses
- `team_response`: Consolidated team response
- `team_completed`: Team processing finished

### Health & Monitoring

```http
GET /api/v1/health              # Server health check
GET /api/v1/agents/status       # Active agents status
DELETE /api/v1/agents/cleanup   # Cleanup inactive agents
```

## 🖥️ Frontend Features

### Single Agent Tab
- Send queries to individual agents
- Real-time tool execution visibility
- Live event stream display
- Agent response formatting

### Multi-Agent Team Tab
- Orchestrator + specialist agent coordination
- Live routing decisions
- Parallel agent activity tracking
- Consolidated team responses

### Analytics Tab
- Event type distribution charts
- Timeline analysis
- Performance metrics
- Event history table

## 🔧 Frontend Integration (JavaScript/React)

If you want to integrate the streaming API with a custom frontend:

```javascript
// Connect to single agent stream
const eventSource = new EventSource('/api/v1/agent/stream?message=your_query');

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.event_type) {
    case 'agent_started':
      console.log('Agent started:', data.content);
      break;
    case 'tool_started':
      console.log('Tool started:', data.tool_name);
      break;
    case 'agent_response':
      console.log('Agent response:', data.content);
      break;
    case 'agent_completed':
      console.log('Agent completed');
      eventSource.close();
      break;
  }
};

eventSource.onerror = (error) => {
  console.error('Stream error:', error);
  eventSource.close();
};
```

## 📊 Event Structure

All streaming events follow this structure:

```json
{
  "event_type": "agent_response",
  "timestamp": "2025-10-08T10:30:00.000Z",
  "agent_id": "demo_user",
  "content": "Agent response content",
  "tool_name": "tool_name",
  "tool_input": {...},
  "tool_output": {...},
  "metadata": {...}
}
```

## 🔒 Production Considerations

### Security
- Add authentication middleware
- Implement rate limiting
- Validate user permissions
- Use HTTPS in production

### Scalability
- Replace in-memory agent storage with Redis
- Add database for event logging
- Implement horizontal scaling
- Add load balancing

### Monitoring
- Add structured logging
- Implement metrics collection
- Set up health checks
- Monitor memory usage

## 🧪 Testing

### Test Single Agent Streaming

```bash
# Using curl
curl -X POST "http://127.0.0.1:8000/api/v1/agent/stream" \
  -H "Content-Type: application/json" \
  -d '{"message": "Test message", "user_id": "test"}' \
  --no-buffer
```

### Test Multi-Agent Team Streaming

```bash
# Using curl
curl -X POST "http://127.0.0.1:8000/api/v1/team/stream" \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a landing page", "team_config": {}}' \
  --no-buffer
```

## 🐛 Troubleshooting

### Common Issues

1. **API Server won't start**
   - Check if port 8000 is available
   - Verify all dependencies are installed
   - Check environment variables

2. **Frontend can't connect**
   - Ensure API server is running
   - Check CORS settings
   - Verify API base URL in frontend

3. **Streaming events not appearing**
   - Check browser dev tools for SSE errors
   - Verify network connectivity
   - Check agent configuration

### Debug Mode

Enable debug logging by setting:

```bash
export LOG_LEVEL=DEBUG
python api_server.py
```

## 📝 Notes

- The API server uses your existing `multi_user_agents.py` without modifications
- Agents are cached in memory for performance
- Frontend automatically handles connection errors and retries
- All streaming events are logged for debugging

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## 📄 License

This project follows the same license as the main Agno framework.