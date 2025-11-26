import aiohttp
import httpx
import json
import base64
import os
import asyncio
import requests
from colorama import Fore
import argparse
import io
import markdown
from PIL import Image as PILImage
from IPython.display import Image as IPythonImage, display, Markdown
import base64
from io import BytesIO
# Import new LLM module and error handling
from llm import LLMClient
from errors import RAGConnectionError, LLMAPIError
from logging_config import get_logger
from vllm_client_multimodal_requests import query_qwen_vllm_served
from PIL import Image as PILImage
from IPython.display import Image as IPythonImage, display, Markdown
import base64
from io import BytesIO
from colorama import Fore
# Initialize logger
logger = get_logger(__name__)

IPADDRESS = "rag-server" if os.environ.get("AI_WORKBENCH", "false") == "true" else "localhost" #Replace this with the correct IP address
INGESTOR_SERVER_PORT = "8082"
INGESTOR_BASE_URL = f"http://{IPADDRESS}:{INGESTOR_SERVER_PORT}"  # Replace with your server URL if required

async def print_response(response, to_print=True):
    """Helper to print API response."""
    try:
        response_json = await response.json()
        if to_print:
            print(json.dumps(response_json, indent=2))
        return response_json
    except aiohttp.ClientResponseError:
        print(await response.text())


RAG_SERVER_PORT = "8081"
RAG_BASE_URL = f"http://{IPADDRESS}:{RAG_SERVER_PORT}"  # Replace with your server URL

rag_url = f"{RAG_BASE_URL}/v1/generate"


async def print_streaming_response_and_citations(response_generator):
    first_chunk_data = None
    text_string = ""  # Collect the complete text here
    markdown_str = ""  # Build complete markdown string with images

    async for chunk in response_generator:
        if chunk.startswith("data: "):
            chunk = chunk[len("data: "):].strip()

        if not chunk:
            continue

        try:
            data = json.loads(chunk)
        except Exception as e:
            print(f"JSON decode error: {e}")
            print(f"⚠️ Raw chunk content: {repr(chunk)}")
            continue

        choices = data.get("choices", [])
        if not choices:
            continue

        # Capture first chunk with citations (if any)
        if first_chunk_data is None and data.get("citations"):
            first_chunk_data = data

        # Stream the content
        delta = choices[0].get("delta", {})
        text = delta.get("content")
        if not text:
            message = choices[0].get("message", {})
            text = message.get("content", "")
        
        if text:
            text_string += text  # Accumulate the text
            print(text, end='', flush=True)

    print()  # Newline after completion

    # Start building markdown string with the main response
    markdown_str = text_string + "\n\n"

    # Display and add citations to markdown if any
    if first_chunk_data and first_chunk_data.get("citations"):
        citations = first_chunk_data["citations"]
        markdown_str += "---\n\n## Citations\n\n"
        img_str=None
        for idx, citation in enumerate(citations.get("results", [])):
            doc_type = citation.get("document_type", "text")
            content = citation.get("content", "")
            doc_name = citation.get("document_name", f"Citation {idx+1}")

            display(Markdown(f"\n**Citation {idx+1}: {doc_name}**"))
            markdown_str += f"### source: {idx+1}\n\n"

            # Handle different content types properly
            if doc_type in ["image", "chart", "table"]:
                try:
                    # Try to decode as base64 and display as image
                    image_bytes = base64.b64decode(content)
                    image = PILImage.open(BytesIO(image_bytes))
                    print(Fore.GREEN + "image in document type ", type(image), Fore.RESET)
                    display(IPythonImage(data=image_bytes))
                    query="this image is embedded in a page, describe this image take into consideration of other relevant parts in this pdf"
                    image_file_loc=content
                    audio_path = None
                    sys_prompt=f"pdf title:{doc_name}, and retrieved relevant parts of this pdf page are:{markdown_str}. Be short and concise in your response"
                    
                    vlm_output=query_qwen_vllm_served(query,image_file_loc, sys_prompt, None)
                    if vlm_output:
                        markdown_str += f"\n{vlm_output}\n"                        
                    print(Fore.BLUE + "VLM parsed image output =\n", vlm_output)
                    
                    # Determine image format
                    image_format = image.format.lower() if image.format else "png"
                    
                    # Add base64 image to markdown string
                    img_str += f"![{doc_name}](data:image/{image_format};base64,{content})\n\n"
                    
                    
                except Exception as e:
                    display(Markdown(f"⚠️ Could not decode {doc_type} content. Error: {e}"))
                    display(Markdown(f"```\nContent preview: {content[:200]}...\n```"))
                    markdown_str += f"⚠️ Could not decode {doc_type} content. Error: {e}\n\n"
                    markdown_str += f"```\nContent preview: {content[:200]}...\n```\n\n"
                    
            elif doc_type == "text":
                display(Markdown(f"```\n{content}\n```"))
                markdown_str += f"\n{content}\n\n\n"
            else:
                # Unknown content type - display as text with warning
                content_preview = content[:500] + ('...' if len(content) > 500 else '')
                display(Markdown(f"⚠️ Unknown content type '{doc_type}':\n```\n{content_preview}\n```"))
                markdown_str += f"⚠️ Unknown content type '{doc_type}':\n```\n{content_preview}\n```\n\n"
    
    return markdown_str, img_str  # Return the complete markdown string with embedded images


async def generate_answer(payload):
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream('POST', url=rag_url, json=payload) as response:
                async for line in response.aiter_lines():
                    yield line.strip()
        except httpx.HTTPError as e:
            print(f"Error: {e}")

async def filter_documents_by_file_name(username, query,pdf_file,num_docs):    
    if ":" in query[:5]:
        query=query.split(":")[-1]    
    
    vdb_top_k=int(num_docs*3)
    try:
        if pdf_file and query :
            # Use 'like' operator for filename matching (exact == doesn't work with the RAG server)
            filter_expr_str=f'content_metadata["filename"] like "%{pdf_file}%"'
            payload = {
            "messages": [
                {
                "role": "user",
                "content": query
                }
            ],
            "use_knowledge_base": True,
            "temperature": 0.2,
            "top_p": 0.7,
            "max_tokens": 1024,
            "reranker_top_k": 10,
            "vdb_top_k": 100,
            "vdb_endpoint": "http://milvus:19530",
            "collection_names": [username],
            "enable_query_rewriting": True,
            "enable_reranker": True,
            "enable_citations": True,
            "model": "nvidia/llama-3.3-nemotron-super-49b-v1.5",
            "reranker_model": "nvidia/llama-3.2-nv-rerankqa-1b-v2",
            "embedding_model": "nvidia/llama-3.2-nv-embedqa-1b-v2",
            # Provide url of the model endpoints if deployed elsewhere
            # "llm_endpoint": "",
            #"embedding_endpoint": "",
            #"reranker_endpoint": "",
            "stop": [],
            "filter_expr": filter_expr_str
            }    
        elif query :
            payload = {
            "messages": [
                {
                "role": "user",
                "content": query
                }
            ],
            "use_knowledge_base": True,
            "temperature": 0.2,
            "top_p": 0.7,
            "max_tokens": 1024,
            "reranker_top_k": 10,
            "vdb_top_k": 100,
            "vdb_endpoint": "http://milvus:19530",
            "collection_names": [COLLECTION_NAME],
            "enable_query_rewriting": True,
            "enable_reranker": True,
            "enable_citations": True,
            "model": "nvidia/llama-3.3-nemotron-super-49b-v1.5",
            "reranker_model": "nvidia/llama-3.2-nv-rerankqa-1b-v2",
            "embedding_model": "nvidia/llama-3.2-nv-embedqa-1b-v2",
            # Provide url of the model endpoints if deployed elsewhere
            # "llm_endpoint": "",
            #"embedding_endpoint": "",
            #"reranker_endpoint": "",
            "stop": [],
            "filter_expr": ""
            }
        else:
            print(username, query, pdf_file)
        print(payload)
        markdown_str, img_str = await print_streaming_response_and_citations(generate_answer(payload))
        if markdown_str:
            flag=True
        else:
            flag=False
    except Exception as exc:
            print('generated an exception: %s' % (exc))
            markdown_str=""
            flag=False
    return flag, markdown_str, img_str
    
    

if __name__ == "__main__":
    # Test document search with file filter
    #query = "motorway access and restrictions"
    #pdf_file = "SwedenDrivingCourse_Motorway.pdf"    
    
    query="what is the Merging lanes sign look like?"
    pdf_file="SwedenDrivingCourse_Motorway.pdf"
    username="test"
    flag, markdown_str , img_str = asyncio.run(filter_documents_by_file_name(username,query, pdf_file, 3))
    print("---"*10)
    
    if flag and markdown_str:
        if img_str:
            
            formatted_markdown_str = markdown.markdown(f'''                
                {markdown_str}

                <br/><br/>
                Reference_document:{pdf_file}
                <br/><br/>
                Reference_images :
                {img_str}               
                ''')
        else:
            formatted_markdown_str = markdown.markdown(f'''                
                {markdown_str}

                <br/><br/>
                Reference_document:{pdf_file}
                           
                ''')
        print(formatted_markdown_str)
    else:
        print("No results found or search failed.")
