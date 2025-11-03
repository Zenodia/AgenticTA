import os
import asyncio
import aiohttp
import json
import requests
from langchain_nvidia_ai_endpoints import ChatNVIDIA, NVIDIAEmbeddings, NVIDIARerank
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnablePassthrough
import concurrent.futures
from colorama import Fore
import os,json
import argparse
from dotenv import load_dotenv
from openai import OpenAI
import os
import base64
from PIL import Image
import io
from IPython.display import Markdown, display
import markdown
from dotenv import load_dotenv
load_dotenv()


API_KEY=os.environ["ASTRA_TOKEN"]
if API_KEY:
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_KEY}',
    }
else:
    headers=None
    client = OpenAI(
        base_url = "https://integrate.api.nvidia.com/v1",
        api_key = os.environ["NVIDIA_API_KEY"]
        )

        
    if os.environ.get("NVIDIA_API_KEY", "").startswith("nvapi-"):
        
        llm =  ChatNVIDIA(model="meta/llama-3.1-405b-instruct")
    else:
        nvapi_key = getpass.getpass("NVAPI Key (starts with nvapi-): ")
        assert nvapi_key.startswith("nvapi-"), f"{nvapi_key[:5]}... is not a valid key"
client = OpenAI(
        base_url = "https://integrate.api.nvidia.com/v1",
        api_key = os.environ["NVIDIA_API_KEY"]
        )

def llm_call(query):
    
    try:
        if headers:
            json_data = {
                'model': 'nvidia/llama-3.3-nemotron-super-49b-v1',
                'messages': [
                    {
                        'role': 'user',
                        'content': query,
                    },
                ],
                'max_tokens': 65000,
                'stream': False,
            }

            response = requests.post(
                'https://datarobot.prd.astra.nvidia.com/api/v2/deployments/688e407ed8a8e0543e6d9b80/chat/completions',
                headers=headers,
                json=json_data,
            )
            output=response.json()
            output_str=output["choices"][0]["message"]["content"]
            print("using astra_llm call , output =", output)
        else:
            print("using build.nvidia.com llm instead, with NVIDIA_API_KEY:", os.environ["NVIDIA_API_KEY"][-4:])            
            output = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": f"detailed thinking off"},
                {"role":"user","content":query}],
            temperature=0.6,
            top_p=0.95,
            max_tokens=65000,
            stream=False
            )
            output_str=output.choices[0].message.content
    
    except:
            output_str=None
    return output_str

#output_str=llm_call("hi")
#print(output_str)