import litellm

print(litellm.completion(
    "openai/models/ggml-model-Q4_K_M.gguf",
    messages=[{"content": "hello", "role": "user"}],
    api_key="sk-1234",
    base_url="http://localhost:8000",
))

# import openai
# client = openai.OpenAI(
#     api_key="sk-1234",             # pass litellm proxy key, if you're using virtual keys
#     base_url="http://localhost:8000" # litellm-proxy-base url
# )

# response = client.chat.completions.create(
#     model="my-model",
#     messages = [
#         {
#             "role": "user",
#             "content": "what llm are you"
#         }
#     ],
# )

# print(response)