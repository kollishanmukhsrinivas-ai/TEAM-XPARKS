import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
import io
import requests
import google.generativeai as genai

# === Set your API keys here or as environment variables ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or "AIzaSyAR3xXzN9e29iqtEOTX05Wyj7Es9_dTazY"
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY") or "0a8a05553d9b4882b7c164852250708"
MODEL_NAME = "gemini-2.5-pro"

app = Flask(__name__)
CORS(app)  # Enable CORS for all domains (for testing; configure for production)
logging.basicConfig(level=logging.INFO)

genai.configure(api_key=GEMINI_API_KEY)

# === Plugin commands ===
def get_time():
    return f"The current time is {datetime.now().strftime('%H:%M:%S')}."

def get_help():
    return (
        "Commands:\n"
        "- /time (show current time)\n"
        "- /help (show this help message)\n"
        "- /weather <city> (get current weather)\n"
        "- Upload image to ask about it\n"
        "- Ask anything else!"
    )

def get_weather(city):
    try:
        url = f"http://api.weatherapi.com/v1/current.json?key={WEATHER_API_KEY}&q={city}&aqi=no"
        response = requests.get(url)
        data = response.json()
        if "error" in data:
            return f"[Weather Error] {data['error']['message']}"
        location = data['location']
        current = data['current']
        return (
            f"Weather in {location['name']}, {location['country']}:\n"
            f"- Local Time: {location['localtime']}\n"
            f"- Condition: {current['condition']['text']}\n"
            f"- Temperature: {current['temp_c']}°C\n"
            f"- Humidity: {current['humidity']}%\n"
            f"- Wind: {current['wind_kph']} kph"
        )
    except Exception as e:
        return f"[Weather Error] Could not retrieve weather: {e}"

def plugin_handler(prompt):
    prompt_stripped = prompt.strip()
    if prompt_stripped == "/time":
        return get_time()
    elif prompt_stripped == "/help":
        return get_help()
    elif prompt_stripped.lower().startswith("/weather"):
        parts = prompt_stripped.split(maxsplit=1)
        if len(parts) == 2:
            return get_weather(parts[1])
        else:
            return "Usage: /weather <city>"
    return None

def ask_agent(prompt, image_bytes=None, history=None):
    logging.info(f"Received prompt: {prompt}")
    plugin_response = plugin_handler(prompt)
    if plugin_response:
        return plugin_response, history
    model = genai.GenerativeModel(MODEL_NAME)
    try:
        if image_bytes:
            img = Image.open(io.BytesIO(image_bytes))
            response = model.generate_content([prompt, img])
            return (response.text if response else "[No content returned]"), None
        if history:
            convo = model.start_chat(history=history)
            response = convo.send_message(prompt)
            return response.text, convo.history
        else:
            response = model.generate_content(prompt)
            return (response.text if response else "[No response]"), None
    except Exception as e:
        logging.error(f"Gemini error: {e}")
        return f"[Error: {e}]", None

@app.route('/api/ask', methods=['POST'])
def api_ask():
    # Accept both JSON and form-data
    if request.form:
        data = request.form
    else:
        data = request.get_json(silent=True) or {}
    prompt = data.get('question', '')
    history = data.get('history', None)
    if history and isinstance(history, str):
        # history might come as JSON string from form-data
        import json
        try:
            history = json.loads(history)
        except Exception:
            history = None
    image_bytes = None
    if 'image' in request.files:
        image_bytes = request.files['image'].read()
    answer, new_history = ask_agent(prompt, image_bytes, history)
    return jsonify({
        "answer": answer,
        "history": new_history
    })

if __name__ == '__main__':
    # Optionally set host="0.0.0.0" to allow external access
    app.run(host='127.0.0.1', port=5000, debug=True)
