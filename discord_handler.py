import requests
import os
from dotenv import load_dotenv

load_dotenv()

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def send_message(message):
    requests.post(WEBHOOK_URL, json={"content": message})