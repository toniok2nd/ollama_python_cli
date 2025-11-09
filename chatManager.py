import json
from typing import Union
from pathlib import Path


class ChatManagerError(RuntimeError):
    """Raised for any problem that occurs while loading or saving JSON files."""
    pass

class ChatManager:
    def __init__(self,_file_path: Union[str, Path]='historyList.json'):
        self.historyList=None
        self.historyFile=_file_path
        if _file_path != None:
            try:
                self.load_from_file(_file_path,endData='historyList')
            except:
                self.historyList=[]

    def load_from_file(self, file_path: Union[str, Path], endData='data') -> json:
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
        if self.data != None:
            return self.data.get('model')

    def save_history_file(self):
        try:
            path = Path(self.historyFile).expanduser().resolve()
            with open(path,'w') as f:
                json.dump(self.historyList, f)
        except json.JSONDecodeError as exc:
            raise ChatManagerError(f"Error saving json file {path}: {exc}") from exc

    def save_file(self, _filename, _model, _history):
        try:
            path = Path(_filename).expanduser().resolve()
            with open(path,'w') as f:
                data = {'model': _model, 'history': _history}
                json.dump(data, f)
            self.historyList.append({"fileName":_filename,"path":str(path)}) 
            self.save_history_file()
        except json.JSONDecodeError as exc:
            raise ChatManagerError(f"Error saving json file {path}: {exc}") from exc


if __name__=="__main__":
    c=ChatManager()
    model="testme"
    data={"kjlk":"kjlkjlk"}
    c.save_file("here.json", model, data)
    c.load_from_file("here.json")
    print(c.data)
    print(c.get_model())
