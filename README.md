# install ollama 
```bash
curl -fsSL https://ollama.com/install.sh | sh
```
then
# install with curl
```bash
curl -fsSL https://raw.githubusercontent.com/toniok2nd/ollama_python_cli/main/install_ollama_cli.sh | bash
```


-------------------------------------------------

## 🎬 Demo video

<video controls width="720" poster="https://raw.githubusercontent.com/toniok2nd/ollama_python_cli/main/docs/video/preview.png">
  <!-- Preferred MP4 source -->
  <source src="https://github.com/toniok2nd/ollama_python_cli/raw/refs/heads/main/docs/video/myollama.mp4" type="video/mp4">
  <source src="https://github.com/toniok2nd/ollama_python_cli/raw/refs/heads/main/docs/video/myollama.mkv" type="video/mkv">
  Your browser does not support the HTML5 video tag.
</video>

*If the video doesn’t play, try the direct download link:*  
[Download MP4](https://github.com/toniok2nd/ollama_python_cli/raw/refs/heads/main/docs/video/myollama.mp4)
[Download MKV](https://github.com/toniok2nd/ollama_python_cli/raw/refs/heads/main/docs/video/myollama.mkv)


https://github.com/user-attachments/assets/486091e7-41cb-4280-ba64-4ced43bca1ab
-------------------------------------------------




# install fzf
```bash
sudo apt install fzf
```
# you need to connect
```bash
(VENV) (base) toniok@hpDre:~/ollama_python_cli 🥩 $ ollama signin
You need to be signed in to Ollama to run Cloud models.

To sign in, navigate to:
    https://ollama.com/connect?name=hpDre.local&key=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

# then install your python venv
```python3
python3 -m venv VENV
source VENV/bin/activate
pip install -r requirements.txt
```

# then run script
```bash
python cliOllama.py
```

