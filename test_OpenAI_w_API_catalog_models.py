from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()
print(os.environ["NVIDIA_API_KEY"][-4:])
client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = os.environ["NVIDIA_API_KEY"]
)

DETAILED_THINKING="off"

completion = client.chat.completions.create(
  model="openai/gpt-oss-120b",
  messages=[
      {"role": "system", "content": f"detailed thinking {DETAILED_THINKING}"},
      {"role":"user","content":"tell me a joke"}],
  temperature=0.6,
  top_p=0.95,
  max_tokens=4096,
  stream=False
)
print(completion.choices[0].message.content)