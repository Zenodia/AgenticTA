from openai import OpenAI
from self_refine import SelfLearner
from openai import OpenAI
from colorama import Fore
import os
import sys
from dotenv import load_dotenv
load_dotenv()



DETAILED_THINKING="off"

client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = os.environ["NVIDIA_API_KEY"],
_strict_response_validation=False
)

# Initialize a self-learner (no API key needed for miniLM)
learner = SelfLearner(embedding_model="miniLM")

# Define our task and original prompt
task = "Write a product description for a smartphone, elaborate it to full feature list and competitiveness of using this smart phone over other brand"
base_prompt = "You are a copywriter."

# Generate text without feedback
def generate_text(prompt, task):
    
    completion = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {"role": "system", "content": prompt},
        {"role":"user","content":task}],
    temperature=0.6,
    top_p=0.95,
    max_tokens=4096,
    stream=False
    )
    #print(Fore.YELLOW + "completion = \n", completion, Fore.RESET)
    output= completion.choices[0].message.content
    return output
# Generate original text
original = generate_text(base_prompt, task)
print("#######################Original output:\n", original)

# Save feedback for the task
feedback = "Keep it under 100 words and focus on benefits not features"
learner.save_feedback(task, feedback)
print("---"*20)
# Apply feedback to the prompt
enhanced_prompt = learner.apply_feedback(task, base_prompt)
enhanced = generate_text(enhanced_prompt, task)

print("######################Improved output:", enhanced)