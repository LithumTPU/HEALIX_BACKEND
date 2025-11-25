import sys
import traceback
from groq import Groq

def run_chatbot(prompt_text: str):
    print("=== Chatbot start ===")
    print(f"[Main] Processing prompt: {prompt_text}")

    try:
        client = Groq(api_key="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")

        completion = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[
                {
                    "role": "system",
                    "content": "You MUST answer in only 1–3 sentences. Never exceed 3 sentences. Never produce long explanations."
                },
                {
                    "role": "user",
                    "content": prompt_text
                }
            ],
            temperature=1,
            max_completion_tokens=80,
            top_p=0.2,
            stream=True,
            stop=None
        )

        response_text = ""
        for chunk in completion:
            response_text += chunk.choices[0].delta.content or ""

        print(f"[Main] Chatbot responded: {response_text[:300]}...")
        print("=== Chatbot finished ===")

        if not response_text.strip():
            response_text = "I received your message but couldn't generate a response. Please try again."

        return response_text

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[Main][ERROR] Chatbot failed: {str(e)}")
        print(f"[Main][TRACEBACK] {tb}")
        return "I'm experiencing some technical difficulties. Please try again in a moment."

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        prompt_text = " ".join(sys.argv[1:])
    else:
        prompt_text = sys.stdin.read().strip()

    if not prompt_text:
        print("Usage: python chatbot_web.py <prompt_text>  OR provide prompt via stdin")
        sys.exit(1)

    response = run_chatbot(prompt_text)
    if response:
        print("\n[Response]:\n", response)