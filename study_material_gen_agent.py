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
load_dotenv()
from openai import OpenAI
import os
from search_and_filter_documents import filter_documents_by_file_name
from dotenv import load_dotenv
load_dotenv()

API_KEY=os.environ["ASTRA_TOKEN"]
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {API_KEY}',
}

llm= ChatNVIDIA(model="meta/llama-3.1-405b-instruct")

def astra_llm_call(query):
    json_data = {
        'model': 'nvidia/llama-3.3-nemotron-super-49b-v1',
        'messages': [
            {
                'role': 'user',
                'content': query,
            },
        ],
        'max_tokens': 512,
        'stream': False,
    }

    response = requests.post(
        'https://datarobot.prd.astra.nvidia.com/api/v2/deployments/688e407ed8a8e0543e6d9b80/chat/completions',
        headers=headers,
        json=json_data,
    )
    try :
        output=response.json()
        output_str = output["choices"][0]["message"]["content"]
    except:
            output_str=None
    return output_str



def strip_thinking_tag(response):
    if "</think>" in response:
        end_index = response.index("</think>")+8
        output = response[end_index:]
        return output
    else:
        return response


study_material_gen_prompts= PromptTemplate(
    template=("""
    You are an expert pedagogical educator who specializes in designing high-quality study materials.  
    Your goal is to help learners achieve mastery in the main subject: {subject}.  
    
    Focus particularly on the sub-topic: {sub_topic}.  
    You will be given contextual details to guide the content creation: {detail_context}.  
    
    Your task is to create clear, engaging, and well-structured study material for the specified sub-topic.  
    Ensure the material:
    - Supports the learner’s progression toward mastering the main subject.  
    - Explains complex ideas in a simple and accessible manner.  
    - Includes examples, key definitions, and summaries where appropriate.  
    - Encourages critical thinking and retention.  
    
    Always maintain educational clarity, logical flow, and learner engagement.
    Begin""")
)

async def study_material_gen(subject,sub_topic,pdf_file_name, num_docs):
    output = await filter_documents_by_file_name(sub_topic,pdf_file_name,num_docs)
    
    
    if len(output)>0:      
        detail_context='\n'.join([f"detail_context:{o["metadata"]["description"]}" for o in output])
        study_material_generation_prompt_formatted=study_material_gen_prompts.format(subject=subject, sub_topic=sub_topic, detail_context=detail_context)
        output=astra_llm_call(study_material_generation_prompt_formatted)  
        print(Fore.BLUE + "using astra llm call > llm parsed relevent_chunks as context output=\n", output) 
        print("---"*10)
        output=strip_thinking_tag(output)
        print(Fore.BLUE + "stripped thinking tag output=\n", output, Fore.RESET) 
        print("---"*10)
        
        return output
    else:        
        print(Fore.BLUE + "using build.nvidia.com's llm call > llm parsed relevent_chunks as context output=\n", output) 
        print("---"*10)
        #output=strip_thinking_tag(output)
        output=""
        print(Fore.BLUE + "stripped thinking tag output=\n", output, Fore.RESET) 
        print("---"*10)
        
        #output = llm.invoke(study_material_generation_prompt_formatted).content
        return output
    return output

if __name__ == "__main__":
    # Move top-level async calls into an async main to avoid 'await outside function'
    query = "fetch information on driving in highway/mortorway"
    pdf_file = "SwedenDrivingCourse_Motorway.pdf"
    subject=pdf_file.split('.pdf')[0]
    sub_topic="0: Motorway Characteristics and Usage Restrictions"
    num_docs=5
    output=asyncio.run( study_material_gen(subject,sub_topic, pdf_file, num_docs))
    print(output)
    