import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
print(f"API Key present: {bool(api_key)}")

if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    print("Attempting simple generation...")
    try:
        response = model.generate_content("Explain 'Hello World' in 5 words.")
        print(f"Success: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
