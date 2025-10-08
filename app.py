from google import genai
from dotenv import load_dotenv
from google.genai import types
import os
load_dotenv()



GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
LLM_MODEL = os.getenv('LLM_MODEL')


client = genai.Client(api_key=GEMINI_API_KEY)



while True:
    user_query = input('Please Ask Question...')
    if user_query == 'exit':
        break
    response = client.models.generate_content(
        model=LLM_MODEL, contents=user_query
    )
    print(response.text)
