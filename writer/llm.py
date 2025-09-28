import os
from openai import OpenAI

def call_openai(user_prompt, system_prompt):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    try:
        # Основной вызов модели gpt-5-mini
        resp = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content

    except Exception as e:
        # Фолбэк на gpt-5
        print(f"⚠️ gpt-5-mini failed: {e}, retrying with gpt-5...")
        resp = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content
