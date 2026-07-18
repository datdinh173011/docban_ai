import os
import json
import time
from google import genai
from google.genai import types
from groq import Groq
from src.config import Config

# Initialize Groq client as fallback with correct key from env
groq_key = os.getenv("groq") or os.getenv("GROQ_API_KEY") or Config.GROQ_API_KEY
try:
    groq_client = Groq(api_key=groq_key)
except Exception as e:
    print(f"[Groq Init Error] {e}")
    groq_client = None

# Initialize Gemini client
gemini_api_key = os.getenv("germini") or os.getenv("GEMINI_API_KEY")
if gemini_api_key:
    gemini_client = genai.Client(api_key=gemini_api_key)
else:
    gemini_client = None

def call_groq_llm(messages, temperature=0.1, max_tokens=2048):
    """
    Unified LLM calling function.
    Primarily uses Gemini 3.5 Flash (via google-genai SDK),
    with robust retries for free tier rate limits (429) and high demand (503),
    and falls back to Groq (Llama-3.3-70b) if Gemini key is completely exhausted/fails.
    """
    is_json = any("json" in m["content"].lower() for m in messages if m["role"] == "system")
    
    # ─── 1. Try Gemini 3.5 Flash ─────────────────────────────────────
    if gemini_client:
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

        # Gemini rule: The first message in a multi-turn chat MUST be from the user.
        # Strip any initial greeting model messages from the history contents.
        while contents and contents[0].role != "user":
            contents.pop(0)

        if contents:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json" if is_json else "text/plain"
            )
            
            # Retry logic for 429 (Rate Limit) and 503 (High Demand / Unavailable)
            for attempt in range(3):
                try:
                    print(f"[Gemini] Calling models/gemini-3.5-flash (Attempt {attempt + 1})...")
                    response = gemini_client.models.generate_content(
                        model='gemini-3.5-flash',
                        contents=contents,
                        config=config
                    )
                    if response and response.text:
                        return response.text
                except Exception as e:
                    err_str = str(e)
                    print(f"[Gemini Error] Attempt {attempt + 1} failed: {err_str}")
                    # If it's a rate limit or service unavailable, wait and retry
                    if any(code in err_str for code in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE"]):
                        sleep_time = 3 * (attempt + 1)
                        print(f"[Gemini Rate/Load Limit] Sleeping for {sleep_time}s and retrying...")
                        time.sleep(sleep_time)
                    else:
                        break # Break out and go to fallback for other exceptions (like bad schema)
        else:
            print("[Gemini] Skipped call because contents list was empty after stripping non-user messages.")
                    
    # ─── 2. Fallback to Groq ─────────────────────────────────────────
    if groq_client:
        print("[LLM Fallback] Falling back to Groq (Llama-3.3-70b)...")
        try:
            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_tokens,
                response_format={"type": "json_object"} if is_json else None
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"[Groq Fallback Error] Error calling Groq API: {e}")
            
    # Default error response
    return "{}" if is_json else "Xin lỗi, hệ thống AI đang gặp sự cố kết nối. Vui lòng thử lại sau."
