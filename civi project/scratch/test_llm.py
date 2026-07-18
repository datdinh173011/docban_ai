import sys
import io
from dotenv import load_dotenv
load_dotenv()

# Set UTF-8 output on Windows
if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("Testing Groq LLM API connection...")
from src.agents.llm import call_groq_llm

messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Xin chào, hãy trả lời ngắn gọn xem bạn có nhận được tin nhắn này không?"}
]

try:
    response = call_groq_llm(messages)
    print("\n--- RESPONSE ---")
    print(response)
    print("----------------")
    if "không" in response.lower() or "nhận" in response.lower() or "có" in response.lower() or "chào" in response.lower():
        print("🎉 Success! Groq LLM API is responding perfectly.")
    else:
        print("⚠️ Warning: Received response, but it looks unusual. Check output above.")
except Exception as e:
    print(f"❌ Failed: Error during connection: {e}")
