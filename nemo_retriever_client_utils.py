import aiohttp
import os 
import json
import re
import base64
import random
from typing import List

IPADDRESS = "rag-server" if os.environ.get("AI_WORKBENCH", "false") == "true" else "localhost" #Replace this with the correct IP address
RAG_SERVER_PORT = "8081"
RAG_BASE_URL = f"http://{IPADDRESS}:{RAG_SERVER_PORT}"  # Replace with your server URL


IPADDRESS = "ingestor-server" if os.environ.get("AI_WORKBENCH", "false") == "true" else "localhost" # Replace this with the correct IP address
INGESTOR_SERVER_PORT = "8082"
BASE_URL = f"http://{IPADDRESS}:{INGESTOR_SERVER_PORT}"  # Replace with your server URL

async def delete_collections(collection_names: List[str] = ""):
    url = f"{BASE_URL}/v1/collections"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.delete(url, json=collection_names) as response:
                await print_response(response)
        except aiohttp.ClientError as e:
            print(f"Error: {e}")


async def create_collection(
    collection_name: list = None,
    embedding_dimension: int = 2048,
    metadata_schema: list = []
):

    data = {
        "collection_name": collection_name,
        "embedding_dimension": embedding_dimension,
        "metadata_schema": metadata_schema
    }

    HEADERS = {"Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{BASE_URL}/v1/collection", json=data, headers=HEADERS) as response:
                await print_response(response)
        except aiohttp.ClientError as e:
            return 500, {"error": str(e)}


# [Optional]: Define schema for metadata fields
metadata_schema = [    
    {
        "name": "source_ref",
        "type": "string",
        "description": "Reference name to the source pdf document"
    }
]

async def upload_documents(collection_name: str = "", files_path_ls:list[str] = [], custom_metadata: list[dict] = []):
    
    print("Uploading files:", files_path_ls , "\n to collection:", collection_name , "\n in nemo retriever...   ")
    data = {
        "collection_name": collection_name,
        "blocking": False, # If True, upload is blocking; else async. Status API not needed when blocking
        "split_options": {
            "chunk_size": 512,
            "chunk_overlap": 150
        },
        "custom_metadata": custom_metadata,
        "generate_summary": True # Set to True to optionally generate summaries for all documents after ingestion
    }

    form_data = aiohttp.FormData()
    for file_path in files_path_ls:
        form_data.add_field("documents", open(file_path, "rb"), filename=os.path.basename(file_path), content_type="application/pdf")

    form_data.add_field("data", json.dumps(data), content_type="application/json")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{BASE_URL}/v1/documents", data=form_data) as response: # Replace with session.patch for reingesting
                await print_response(response)
        except aiohttp.ClientError as e:
            print(f"Error: {e}")

async def fetch_collections():
    url = f"{BASE_URL}/v1/collections"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                output = await print_response(response)
                output = json.dumps(output, indent=2)
                json_output = json.loads(output)
        except aiohttp.ClientError as e:
            json_output = {}
            print(f"Error: {e}")
        return json_output




async def upload_files_to_nemo_retriever(files_path_ls : str , username: str , CUSTOM_METADATA: list[dict] = []): 
        # Filepaths
    
    # [Optional]: Add filename specific custom metadata

    output=await upload_documents(username, files_path_ls, CUSTOM_METADATA)
    return output


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

async def fetch_health_status():
    """Fetch health status asynchronously."""
    url = f"{RAG_BASE_URL}/v1/health"
    print("Fetching RAG server health status with url = ", url)
    params = {"check_dependencies": "True"} # Check health of dependencies as well
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            await print_response(response)

# Run the async function
#await fetch_health_status()
## helpful function to quickly get documents
async def document_search(payload, url):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url=url, json=payload) as response:
                output = await print_response(response)
                flag = True
        except aiohttp.ClientError as e:
            print(f"Error: {e}")
            output="error"
            flag = False
    return flag, output
    
async def get_documents(query, username):
    url = f"{RAG_BASE_URL}/v1/search"
    payload={
      "query": query , # replace with your own query 
      "reranker_top_k": 5,
      "vdb_top_k": 20,
      "vdb_endpoint": "http://milvus:19530",
      "collection_names": [username], # Multiple collection retrieval can be used by passing multiple collection names
      "messages": [],
      "enable_query_rewriting": True,
      "enable_reranker": True,
      "embedding_model": "nvidia/llama-3.2-nv-embedqa-1b-v2",
      # Provide url of the model endpoints if deployed elsewhere
      #"embedding_endpoint": "",
      #"reranker_endpoint": "",
      "reranker_model": "nvidia/llama-3.2-nv-rerankqa-1b-v2",
    
    }
    
    flag, output=await document_search(payload, url)
    return flag, output

def is_base64(s):
    if not s or not isinstance(s, str):
        return False
    try:
        # Try decoding with validation
        decoded = base64.b64decode(s, validate=True)
        # Re-encode and compare without padding
        encoded = base64.b64encode(decoded).decode('utf-8')
        return encoded.rstrip('=') == s.rstrip('=')
    except Exception:
        return False


def is_base64_regex(s):
    pattern = re.compile(r'^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)?$')
    return bool(pattern.match(s))


def fetch_rag_context(output:str)-> str :
    context_ls=[]
    output_d=json.loads(output)
    source_ref_ls=[]
    i=1
    for o in output_d["results"]:
        #print("---"*10) 
        print(o["metadata"].keys())
        #print(o["content"])
        page_nr=o["metadata"]["page_number"]
        source_ref=o["metadata"]["content_metadata"]["source_ref"]
        source_ref_w_page= f"{source_ref} page:{str(page_nr)}"
        context=o["content"]
        if is_base64_regex(context) or is_base64(context):
            print("skipping base64 string, which is not actually text content....")
            try: 
                table_or_text=o["metadata"]["description"]                
                context_ls.append(f"extra_info:{table_or_text}")
            except :
                pass 
            
        else:
            context_ls.append(f"context:{context}"+'\n'+ f"source_ref:{source_ref_w_page}")
            try: 
                table_or_text=o["metadata"]["description"]                
                context_ls.append(f"extra_info:{table_or_text}")
            except :
                pass 
        
        i+=1
    n=len(context_ls)
    if n>=5:
        context_ls=ramdom.sample(context_ls,5)
    
    return 'n'.join(context_ls)

