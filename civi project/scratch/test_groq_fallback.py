import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
groq_key = os.getenv("groq") or os.getenv("GROQ_API_KEY")
print(f"Groq API Key: {groq_key[:10] if groq_key else 'None'}...")

client = Groq(api_key=groq_key)

try:
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "user", "content": "Say hello in Vietnamese"}
        ],
        temperature=0.1
    )
    print("Groq Success!")
    print(completion.choices[0].message.content)
except Exception as e:
    print(f"Groq Failed: {e}")
