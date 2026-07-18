import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
api_key = os.getenv("germini") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# Mocked conversation starting with assistant message (violates Gemini API rule)
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "assistant", "content": "Xin chào! Tôi là CIVI, trợ lý hành chính công. Bạn đang cần giải quyết thủ tục gì hôm nay?"},
    {"role": "user", "content": "Tôi muốn xây nhà cấp 4 trên đất mua đứng tên 2 vợ chồng"}
]

contents = []
system_instruction = None

for m in messages:
    role = m.get("role")
    content = m.get("content", "")
    if role == "system":
        system_instruction = content
    elif role == "user":
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=content)]
            )
        )
    elif role in ("assistant", "model"):
        contents.append(
            types.Content(
                role="model",
                parts=[types.Part.from_text(text=content)]
            )
        )

# Strip initial model messages to comply with Gemini multi-turn role sequence
while contents and contents[0].role != "user":
    contents.pop(0)

print(f"Contents start role: {contents[0].role if contents else 'Empty'}")

try:
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.1
    )
    response = client.models.generate_content(
        model='gemini-3.5-flash',
        contents=contents,
        config=config
    )
    print("Success response:")
    print(response.text)
except Exception as e:
    print(f"Failed: {e}")
