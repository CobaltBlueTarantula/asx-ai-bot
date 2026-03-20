import requests
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("AI_API_KEY")
invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"

headers = {
  "Authorization": f"Bearer {api_key}",
  "Accept": "application/json"
}

history = [{"role":"system","content":"You are a helpful assistant."},]

while True:
    prompt = input("Input: ")
    
    if prompt.lower() in ["exit", "quit"]:
        break
    
    history.append({"role":"user","content":prompt})

    payload = {
        "model": "moonshotai/kimi-k2.5",
        "messages": history,
        "max_tokens": 128,
        "temperature": 0.7,
        "top_p": 1.00,
        "stream": False,
        "chat_template_kwargs": {"thinking": False},
    }

    response = requests.post(invoke_url, headers=headers, json=payload)

    try:
        response.raise_for_status()    
    except requests.RequestException as e:
        print(f"Error: {e}")
        break

    msg = response.json()["choices"][0]["message"]["content"]
    history.append({"role":"assistant","content":msg})
    print(msg)