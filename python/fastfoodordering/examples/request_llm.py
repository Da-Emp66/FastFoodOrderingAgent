import time
import litellm

start = time.time()
response = litellm.completion(
    "openai/models/ggml-model-Q4_K_M.gguf",
    messages=[{"content": "What are you doing here and who are you?", "role": "user"}],
    api_key="sk-1234",
    base_url="http://localhost:8000",
    stream=True,
)
text_response = ""
for chunk in response:
    # Each chunk is a partial delta
    if chunk and chunk.choices:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            print(delta.content, end="", flush=True)
            text_response += delta.content
print()
print(text_response)
end = time.time()
print(f"{end - start} seconds")

import openai

client = openai.OpenAI(
    api_key="sk-1234",             # pass litellm proxy key, if you're using virtual keys
    base_url="http://localhost:8000" # litellm-proxy-base url
)

start = time.time()
response = client.chat.completions.create(
    model="my-model",
    messages = [
        {
            "role": "user",
            "content": "Who are you?"
        }
    ],
)
print(response)
end = time.time()
print(f"{end - start} seconds")
