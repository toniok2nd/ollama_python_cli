from unittest.mock import patch, MagicMock, AsyncMock
import unittest
import asyncio
import sys
import os

# Ensure the parent directory is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the async function
# We need to mock ollama/mcp modules before import if they are fast-imported, 
# but they are imported at top-level. 
# Assuming environment has them or we mock sys.modules.
# Since we installed them in VENV, we can rely on them being present or mocked.

from cliOllama import run_chat_turn

class TestRunChatTurn(unittest.IsolatedAsyncioTestCase):
    @patch('cliOllama.ollama')
    async def test_run_chat_turn_simple(self, mock_ollama):
        # Setup mock for simple chat (no tools)
        mock_ollama.chat.return_value = [
            {'message': {'content': 'Hello'}},
            {'message': {'content': ' World'}}
        ]

        messages = [{'role': 'user', 'content': 'Hi'}]
        results = []
        async for token in run_chat_turn('model', messages):
            results.append(token)
        
        self.assertEqual(''.join(results), 'Hello World')
        self.assertEqual(len(messages), 2) # User + Assistant
        self.assertEqual(messages[-1]['content'], 'Hello World')

    @patch('cliOllama.ollama')
    async def test_run_chat_turn_with_tool(self, mock_ollama):
        # Mock session
        mock_session = AsyncMock()
        mock_tool_result = MagicMock()
        mock_tool_result.content = [MagicMock(text="Tool Output")]
        mock_session.call_tool.return_value = mock_tool_result
        
        # Mock tools list
        mock_list_tools = MagicMock()
        mock_list_tools.tools = [] # Empty for simplicity or mock one
        mock_session.list_tools.return_value = mock_list_tools

        # Mock ollama chat sequence
        # 1. Tool Call
        # 2. Final Response
        
        # We need side_effect for iterators on multiple calls
        
        # Call 1 iterator
        iter1 = [
            {'message': {'tool_calls': [{'function': {'name': 'test_tool', 'arguments': {}}}]}}
        ]
        
        # Call 2 iterator
        iter2 = [
            {'message': {'content': 'Final Answer'}}
        ]
        
        mock_ollama.chat.side_effect = [iter1, iter2]

        messages = [{'role': 'user', 'content': 'Do tool'}]
        results = []
        
        async for token in run_chat_turn('model', messages, session=mock_session):
            results.append(token)
        
        # Verify tool execution output in stream
        self.assertIn('\n[Executing tool: test_tool...]', results)
        self.assertIn('Final Answer', results)
        
        # Verify structure
        # Messages should have: User, Assistant(ToolCall), ToolResult, Assistant(Final)
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[1]['role'], 'assistant')
        self.assertTrue(messages[1]['tool_calls'])
        self.assertEqual(messages[2]['role'], 'tool')
        self.assertEqual(messages[2]['content'], 'Tool Output')
        self.assertEqual(messages[3]['role'], 'assistant')
        self.assertEqual(messages[3]['content'], 'Final Answer')

if __name__ == '__main__':
    unittest.main()
