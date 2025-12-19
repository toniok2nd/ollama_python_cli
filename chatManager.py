from typing import Union
from pathlib import Path
import json


class ChatManagerError(RuntimeError):
    """Raised for any problem that occurs while loading or saving JSON files."""
    pass

class ChatManager:
    """
    Manages loading and saving of chat history and model selection.
    Stores a history list of chats in a central JSON file and individual chat sessions in separate files.
    """
    def __init__(self,_file_path: Union[str, Path]='.historyList.json'):
        """
        Initialize the ChatManager.
        
        Args:
            _file_path: Path to the main history index file. Defaults to 'historyList.json'.
                        If None, starts with empty history/data.
        """
        self.historyList=None
        self.historyFile=_file_path
        if _file_path != None:
            try:
                self.load_from_file(_file_path,endData='historyList')
            except:
                self.historyList=[]

    def load_from_file(self, file_path: Union[str, Path], endData='data') -> json:
        """
        Load JSON data from a file into an instance attribute.
        
        Args:
            file_path: Path to the JSON file to load.
            endData: Name of the attribute to store the loaded data in (e.g. 'data', 'historyList').
                     WARNING: uses exec() to set the attribute dynamically.
        
        Raises:
            ChatManagerError: If file not found or invalid JSON.
        """
        path = Path(file_path.strip()).expanduser().resolve()
        if not path.is_file():
            raise ChatManagerError(f"File not found: {path}")
        try:
            tmp = json.loads(path.read_text(encoding="utf-8"))
            cmd=f"self.{endData}=tmp"
            exec(cmd,globals(),locals())
        except json.JSONDecodeError as exc:
            raise ChatManagerError(f"Invalid JSON in {path}: {exc}") from exc

    def get_model(self):
        """
        Retrieve the model name from the currently loaded chat data.
        
        Returns:
            The model name string, or None if data is not loaded.
        """
        if self.data != None:
            return self.data.get('model')

    def save_history_file(self):
        """
        Save the global list of chat history files (historyList) to disk.
        """
        try:
            path = Path(self.historyFile).expanduser().resolve()
            with open(path,'w') as f:
                json.dump(self.historyList, f)
        except json.JSONDecodeError as exc:
            raise ChatManagerError(f"Error saving json file {path}: {exc}") from exc

    def save_file(self, _filename, _model, _history):
        """
        Save the current chat session to a file and update the global history list.
        
        Args:
            _filename: Name of the file to save the chat to.
            _model: Name of the model used in this chat.
            _history: Chat history content (list of messages or string).
        """
        try:
            path = Path(_filename).expanduser().resolve()
            with open(path,'w') as f:
                data = {'model': _model, 'history': _history}
                json.dump(data, f)
            
            # De-duplication: Remove existing entry for same path if it exists
            new_entry = {"fileName": _filename, "path": str(path)}
            self.historyList = [item for item in self.historyList if item.get('path') != str(path)]
            self.historyList.append(new_entry) 
            
            self.save_history_file()
        except json.JSONDecodeError as exc:
            raise ChatManagerError(f"Error saving json file {path}: {exc}") from exc


if __name__=="__main__":
    # Test block
    c=ChatManager()
    model="testme"
    data={"kjlk":"kjlkjlk"}
    c.save_file("here.json", model, data)
    c.load_from_file("here.json")
    print(c.data)
    print(c.get_model())
