from unittest.mock import patch, mock_open, MagicMock
import unittest
import sys
import os
import json

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from chatManager import ChatManager, ChatManagerError
from markedownExtractor import MarkdownExtractor

class TestChatManager(unittest.TestCase):
    def setUp(self):
        # Prevent ChatManager from trying to load historyList.json on init during tests
        # We can pass None to _file_path in init if the class supports it, 
        # based on code: def __init__(self,_file_path...='historyList.json')
        # if _file_path != None: load...
        pass

    @patch('chatManager.Path')
    def test_load_from_file_success(self, mock_path_cls):
        # Setup mock path
        mock_path_obj = MagicMock()
        mock_path_cls.return_value = mock_path_obj
        mock_path_obj.expanduser.return_value.resolve.return_value = mock_path_obj
        mock_path_obj.is_file.return_value = True
        
        # Mock file content
        test_data = {"model": "test-model", "history": "test-history"}
        mock_path_obj.read_text.return_value = json.dumps(test_data)

        cm = ChatManager(_file_path=None) # Start empty
        cm.load_from_file("dummy.json")
        
        # Verify data was loaded
        self.assertEqual(cm.get_model(), "test-model")
        self.assertEqual(cm.data.get('history'), "test-history")

    @patch('chatManager.Path')
    def test_load_from_file_not_found(self, mock_path_cls):
        mock_path_obj = MagicMock()
        mock_path_cls.return_value = mock_path_obj
        mock_path_obj.expanduser.return_value.resolve.return_value = mock_path_obj
        mock_path_obj.is_file.return_value = False

        cm = ChatManager(_file_path=None)
        with self.assertRaises(ChatManagerError) as context:
            cm.load_from_file("nonexistent.json")
        self.assertIn("File not found", str(context.exception))

    @patch('chatManager.json.dump')
    @patch('builtins.open', new_callable=mock_open)
    @patch('chatManager.Path')
    def test_save_file(self, mock_path_cls, mock_file, mock_json_dump):
        mock_path_obj = MagicMock()
        mock_path_cls.return_value = mock_path_obj
        mock_path_obj.expanduser.return_value.resolve.return_value = mock_path_obj
        
        # We need historyList initialized
        cm = ChatManager(_file_path=None)
        cm.historyList = []
        cm.historyFile = "history.json" # Needed for save_history_file call inside save_file

        cm.save_file("new_chat.json", "my-model", "my-history")

        # Verify file open was called for new_chat.json
        mock_file.assert_any_call(mock_path_obj, 'w')
        
        # Verify json.dump called with correct data
        # Note: save_file calls json.dump twice: once for the chat data, once for historyList
        # We check the first call args
        expected_data = {'model': 'my-model', 'history': 'my-history'}
        mock_json_dump.assert_any_call(expected_data, mock_file())

class TestMarkdownExtractor(unittest.TestCase):
    def test_extract_code_blocks(self):
        text = """
Some text.
```python
print("Hello")
```
More text.
```bash
ls -la
```
"""
        extractor = MarkdownExtractor(text)
        blocks = extractor.extract_code_blocks()
        
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]['language'], 'python')
        self.assertEqual(blocks[0]['code'], 'print("Hello")')
        self.assertEqual(blocks[1]['language'], 'bash')
        self.assertEqual(blocks[1]['code'], 'ls -la')

    def test_extract_tables(self):
        text = """
| Header 1 | Header 2 |
|----------|----------|
| Row 1    | Data 1   |

Not a table.
"""
        extractor = MarkdownExtractor(text)
        tables = extractor.extract_tables()
        
        self.assertEqual(len(tables), 1)
        self.assertIn("Header 1", tables[0])
        self.assertIn("Row 1", tables[0])

    def test_extract_mixed_content(self):
        text = """
# Title
```text
code
```
| A | B |
|---|---|
| 1 | 2 |
"""
        extractor = MarkdownExtractor(text)
        result = extractor.extract_all()
        
        self.assertEqual(len(result['code_blocks']), 1)
        self.assertEqual(len(result['tables']), 1)

if __name__ == '__main__':
    unittest.main()
