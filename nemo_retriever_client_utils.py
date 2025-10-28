import aiohttp
import os 
import json
import re
import base64
import random
IPADDRESS = "rag-server" if os.environ.get("AI_WORKBENCH", "false") == "true" else "localhost" #Replace this with the correct IP address
RAG_SERVER_PORT = "8081"
BASE_URL = f"http://{IPADDRESS}:{RAG_SERVER_PORT}"  # Replace with your server URL

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
    url = f"{BASE_URL}/v1/health"
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
    
async def get_documents(query):
    url = f"{BASE_URL}/v1/search"
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

