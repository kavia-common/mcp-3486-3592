# MCP Server

FastAPI backend that provides message processing, rule management, audit logging, and JIRA integration.

## Quick start

1. Create a `.env` from the example:
   cp MCPServer/.env.example MCPServer/.env

2. Create and activate a virtual environment, then install dependencies:
   pip install -r MCPServer/requirements.txt

3. Run the server:
   uvicorn MCPServer.src.api.main:app --reload

4. Access docs:
   http://localhost:8000/docs

## Environment

- Preferred: DB_DSN (postgresql+asyncpg)
- Alternatively: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
- JWT_SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES
- JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN

## Endpoints (high-level)

- GET /health
- POST /auth/token
- GET /auth/me
- /users (admin)
- /messages
- /rules (admin)
- /audit (admin)
- /jira
- /webhooks

## Database

For MVP, tables are auto-created on startup. Add Alembic later under MCPServer/migrations.