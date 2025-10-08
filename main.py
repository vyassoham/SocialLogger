from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("LLM_MODEL")

gemini = genai.Client(api_key=API_KEY)

def chatwithgemini():
    print("Hey Send Your Question :  ")
    while True:
        query = input("Your question: ")
        if query == "exit":
            print("Goodbye!")
            break

        reply = gemini.models.generate_content(
            model=MODEL_NAME,
            contents=query
        )
        print(reply.text)

if __name__ == "__main__":
    chatwithgemini()
