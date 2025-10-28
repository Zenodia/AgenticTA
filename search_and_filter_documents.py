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



IPADDRESS = "rag-server" if os.environ.get("AI_WORKBENCH", "false") == "true" else "localhost" #Replace this with the correct IP address
RAG_SERVER_PORT = "8081"
BASE_RAG_URL = f"http://{IPADDRESS}:{RAG_SERVER_PORT}"  # Replace with your server URL

async def print_response(response):
    """Helper to print API response."""
    try:
        response_json = await response.json()
        output = json.dumps(response_json, indent=2)
        print(json.dumps(response_json, indent=2))
    except aiohttp.ClientResponseError:
        print(await response.text())
        output="error"
    return output

## helpful function to quickly get documents
async def document_seach(payload, url):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url=url, json=payload) as response:
                output = await print_response(response)
        except aiohttp.ClientError as e:
            print(f"Error: {e}")
            output="error"
    return output
# possible filter expression
#"filter_expr": '(content_metadata["manufacturer"] like "%ford%" and content_metadata["rating"] > 4.0 and content_metadata["created_date"] between "2020-01-01" and "2024-12-31" and content_metadata["is_public"] == true) or (content_metadata["model"] like "%edge%" and content_metadata["year"] >= 2020 and content_metadata["tags"] in ["technology", "safety", "latest"] and content_metadata["rating"] >= 4.0)'
async def get_documents(query:str = None, pdf_file_name:str = None, num_docs : int = 5):
    url = f"{BASE_RAG_URL}/v1/search"
    if pdf_file_name and query :
        pdf_file_name= pdf_file_name.lower()
        filter_expr_str=f'content_metadata["source_ref"]=="{pdf_file_name}"'
        payload={
        "query": query , # replace with your own query 
        "reranker_top_k": 5,
        "vdb_top_k": 20,
        "vdb_endpoint": "http://milvus:19530",
        "collection_names": ["zcharpy"], # Multiple collection retrieval can be used by passing multiple collection names
        "messages": [],
        "enable_query_rewriting": False,
        "enable_reranker": True,
        "embedding_model": "nvidia/llama-3.2-nv-embedqa-1b-v2",
        # Provide url of the model endpoints if deployed elsewhere
        #"embedding_endpoint": "",
        #"reranker_endpoint": "",
        "reranker_model": "nvidia/llama-3.2-nv-rerankqa-1b-v2",
        "filter_expr": filter_expr_str
        }
        output=await document_seach(payload, url)
    elif query :
        payload={
        "query": query , # replace with your own query 
        "reranker_top_k": 5,
        "vdb_top_k": 20,
        "vdb_endpoint": "http://milvus:19530",
        "collection_names": ["zcharpy"], # Multiple collection retrieval can be used by passing multiple collection names
        "messages": [],
        "enable_query_rewriting": True,
        "enable_reranker": True,
        "embedding_model": "nvidia/llama-3.2-nv-embedqa-1b-v2",
        # Provide url of the model endpoints if deployed elsewhere
        #"embedding_endpoint": "",
        #"reranker_endpoint": "",
        "reranker_model": "nvidia/llama-3.2-nv-rerankqa-1b-v2",
        "filter_expr": ""
        }
        output=await document_seach(payload, url)
    else:
        output=None
    
    return output


async def filter_documents_by_file_name(query,pdf_file,num_docs):        
    output = await get_documents(query, pdf_file, 3)
    if output :
        output_d=json.loads(output)
    output_ls =[]
    try :
        for o in output_d["results"]:
            print( o["document_name"], o["metadata"]["page_number"],'\n', o["metadata"]["description"])
        return output_d["results"]
    except:

        return []


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
    output = await filter_documents_by_file_name(sub_topic,pdf_file,num_docs)
    print("\n\n### output.keys=", "\n\n")
    detail_context='\n'.join([f"detail_context:{o["metadata"]["description"]}" for o in output])
    study_material_generation_prompt_formatted=study_material_gen_prompts.format(subject=subject, sub_topic=sub_topic, detail_context=detail_context)
    output=astra_llm_call(study_material_generation_prompt_formatted)
    if output:        
        print(Fore.BLUE + "using astra llm call > llm parsed relevent_chunks as context output=\n", output) 
        print("---"*10)
        output=strip_thinking_tag(output)
        print(Fore.BLUE + "stripped thinking tag output=\n", output, Fore.RESET) 
        print("---"*10)
        
        return output
    else:        
        print(Fore.BLUE + "using build.nvidia.com's llm call > llm parsed relevent_chunks as context output=\n", output) 
        print("---"*10)
        output=strip_thinking_tag(output)
        print(Fore.BLUE + "stripped thinking tag output=\n", output, Fore.RESET) 
        print("---"*10)
        
        output = llm.invoke(study_material_generation_prompt_formatted).content
        return output
    return output

if __name__ == "__main__":
    # Move top-level async calls into an async main to avoid 'await outside function'
    query = "fetch information on driving in highway/mortorway"
    pdf_file = "SwedenDrivingCourse_Motorway.pdf"
    
    
    asyncio.run(filter_documents_by_file_name(query,pdf_file,1))