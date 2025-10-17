#!/bin/bash
cd /home/kavia/workspace/code-generation/mcp-3486-3592/MCPServer
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

