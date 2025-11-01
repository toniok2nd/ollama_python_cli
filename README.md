# you need to have ollama installed 
```bash
curl -fsSL https://ollama.com/install.sh | sh
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

