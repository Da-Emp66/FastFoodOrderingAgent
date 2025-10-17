import time
import litellm

start = time.time()
print(litellm.completion(
    "openai/models/ggml-model-Q4_K_M.gguf",
    messages=[{"content": "Who are you?", "role": "user"}],
    api_key="sk-1234",
    base_url="http://localhost:8000",
))
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
