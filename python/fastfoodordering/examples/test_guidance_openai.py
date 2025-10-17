import os
import time
from typing import Literal
from guidance import gen, json, system, user, assistant
from guidance.models import OpenAI
from pydantic import BaseModel, Field

os.environ["MODEL"] = "openai/models/ggml-model-Q4_K_M.gguf"
os.environ["OPENAI_API_KEY"] = "sk-1234"
os.environ["OPENAI_BASE_URL"] = "http://localhost:8000"
os.environ["MODEL_SERVER"] = os.getenv("OPENAI_BASE_URL")

class BloodPressure(BaseModel):
    # systolic: int = Field(gt=300, le=400)
    # diastolic: int = Field(gt=0, le=20)
    # location: str = Field(max_length=50)
    other_StuFf: Literal["hello!", "yeyah", "whatever"]
    # model_config = dict(extra="forbid")

def main():
    lm = OpenAI(
        os.getenv("MODEL"),
        echo=True,
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )

    # with system():
    #     lm += "You only speak in ALL CAPS."

    # with user():
    #     lm += "Respond to the user"

    print(BloodPressure.model_json_schema())

    start = time.time()
    with assistant():
        lm += json('answer', schema=BloodPressure) # , max_tokens=20
    end = time.time()
    print(f"{end - start} seconds")

    print(lm["answer"])
    print(BloodPressure.model_validate_json(lm["answer"]))


if __name__ == "__main__":
    main()
