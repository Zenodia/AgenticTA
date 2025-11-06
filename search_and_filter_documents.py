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
API_KEY=os.environ.get("ASTRA_TOKEN", "")
if API_KEY:
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_KEY}',
    }
else:
    headers = None

llm= ChatNVIDIA(model="meta/llama-3.1-405b-instruct")

def printmd(markdown_str):
    display(Markdown(markdown_str))


def astra_llm_call(query):
    if not headers:
        # Fall back to LangChain LLM if ASTRA is not configured
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        prompt = ChatPromptTemplate.from_messages([("user", "{query}")])
        chain = prompt | llm | StrOutputParser()
        try:
            output_str = chain.invoke({"query": query})
        except Exception as e:
            from colorama import Fore
            print(Fore.RED + f"LLM fallback error: {e}" + Fore.RESET)
            output_str = None
        return output_str
    
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
    vdb_top_k=int(num_docs*3)
    if pdf_file_name and query :
        # Use 'like' operator for filename matching (exact == doesn't work with the RAG server)
        filter_expr_str=f'content_metadata["filename"] like "%{pdf_file_name}%"'
        payload={
        "query": query , # replace with your own query 
        "reranker_top_k": num_docs,
        "vdb_top_k": vdb_top_k ,
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
        "vdb_top_k": 10,
        "vdb_endpoint": "http://milvus:19530",
        "collection_names": ["zcharpy"], # Multiple collection retrieval can be used by passing multiple collection names
        "messages": [],
        "enable_query_rewriting": True,
        "enable_reranker": False,
        "embedding_model": "nvidia/llama-3.2-nv-embedqa-1b-v2",
        # Provide url of the model endpoints if deployed elsewhere
        #"embedding_endpoint": "",
        #"reranker_endpoint": "",        
        "filter_expr": ""
        }
        output=await document_seach(payload, url)
    else:
        output=None
    
    return output


async def filter_documents_by_file_name(query,pdf_file,num_docs):    
    if ":" in query[:5]:
        query=query.split(":")[-1]
    output = await get_documents(query, pdf_file, 3)
    try:
        output_d=json.loads(output)
        if len(output_d["results"])>0:
            flag=True
        else:
            flag=False
        for o in output_d["results"]:
            print( o["document_name"], o["metadata"]["page_number"],'\n', o["metadata"]["description"])
        return flag, output_d["results"]
    except:
        return False, []

if __name__ == "__main__":
    # Test document search with file filter
    query = "motorway access and restrictions"
    pdf_file = "SwedenDrivingCourse_Motorway.pdf"    
    
    flag, results = asyncio.run(filter_documents_by_file_name(query, pdf_file, 3))
    print("---"*10)
    
    if flag and results:
        # Convert results to markdown string
        markdown_str = "## Search Results\n\n"
        for idx, result in enumerate(results):
            markdown_str += f"### Result {idx + 1}\n"
            markdown_str += f"**Document:** {result.get('document_name', 'N/A')}\n\n"
            markdown_str += f"**Page:** {result.get('metadata', {}).get('page_number', 'N/A')}\n\n"
            markdown_str += f"**Content:**\n\n{result.get('content', 'N/A')}\n\n"
            markdown_str += "---\n\n"
        print(markdown_str)
    else:
        print("No results found or search failed.")
