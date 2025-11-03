# importing required modules
from pypdf import PdfReader
import tempfile
import shutil
from typing import List, Tuple
import sys
# Optional, more robust PDF handlers. Import lazily and handle absence.
try:
    import pikepdf
except Exception:
    pikepdf = None

try:
    import pdfplumber
except Exception:
    pdfplumber = None
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
from llm_call_utils import llm_call
import requests
import os
import re
from collections import OrderedDict
load_dotenv()

API_KEY=os.environ.get("ASTRA_TOKEN", "")
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


sub_topics_generation_prompt = """You are an expert in generation short chapter title to outline the studying curriculum.
        You will have access to one summary extracted from the a processed document which user uploaded previously.

        You will condense each summary and produce an appropriate title for that particular summary.
        <EXAMPLE>        
        document_summary:\nThis is a digital learning tool for driving license training. It is well-proven by students and driving schools. It is web-based and updated to most recent Swedish traffic regulations. This document includes basic variations of learning that are good to know before you practice driving.\n
        **chapter_title:**\n1: Intro to driving course - before driving practice.\n

        document_summary:\nThe document outlines essential safety practices for driving on country roads, emphasizing proactive scanning, speed control, and risk mitigation. Key strategies include maintaining a three-second following distance, regularly checking mirrors in a systematic pattern, and adjusting speed for conditions to avoid "speed blindness." It details proper positioning for turns (right edge for right turns, center for lefts) and highlights dangers of overtaking and abrupt maneuvers. Technical aspects cover reaction/braking distance calculations, the impact of kinetic energy in crashes, and using roadside reflectors (spaced 50m apart) for distance judgment. The text also addresses parking restrictions, hard shoulder usage, and the importance of avoiding left turns without clear visibility. Overall, it stresses defensive driving techniques to counter higher speeds and reduced friction on rural roads.
        **chapter_title:**\n 2: Driving essentials - dirving on Country roads.

        ...and so on
        </EXAMPLE>

        <RULEs>
        You will strictly follow below 3 rules, and in this order, when you produce the chapter titles :        
        1. you should always mark your response with '**chapter_title:**\n
        2. you will be given a chapter_nr, say 9, then add a prefix '9:' before the title
        3. you will condense the provided summary into one very short sentence appropriate for a title 
        4. return only the title, do not elaborate/explain anything else.
        </RULES>

        current input document_summary: {document_summary}        
        **chapter_title:**\n {chapter_nr}:"""

sub_topics_generation_prompt_template = ChatPromptTemplate.from_template(sub_topics_generation_prompt)


sub_topics_gen_chain = (
    RunnablePassthrough()    
    | sub_topics_generation_prompt_template
    | llm
)

def get_pdf_pages(pdf_file):
    # Use PdfReader with the file path and strict=False so PdfReader
    # manages the file lifecycle internally and avoids returning a
    # reader that relies on a closed file handle.
    try:
        reader = PdfReader(pdf_file, strict=False)
        n = len(reader.pages)
        print(type(n), n)
        return reader, n
    except Exception as e:
        print(f"Error opening/reading PDF '{pdf_file}': {e}")
        return None, 0

def title_generator(summary,chapter_nr):
    query=sub_topics_generation_prompt.format(document_summary=summary, chapter_nr=chapter_nr)    
    output=llm_call(query)
    if output :
        return output
    else:
        output=sub_topics_gen_chain.invoke({"document_summary":summary,"chapter_nr":chapter_nr})
        output = output.content
        return output

# creating a pdf reader object
def get_text_from_page(reader,i):
    # getting a specific page from the pdf file
    page = reader.pages[i]

    # extracting text from page
    try:
        text = page.extract_text()
    except Exception as e:
        print(f"Exception extracting text from page {i}: {e}")
        text = ""

    # if the extracted text is empty or very short, skip heavy LLM/title generation
    if not text or len(text.strip()) < 20:
        return ""

    try:
        output = title_generator(text, i)
        return output
    except Exception as e:
        print(f"Exception generating title for page {i}: {e}")
        return ""



def parallel_extract_pdf_page_and_text(path_to_pdf_file):
    reader, n = get_pdf_pages(path_to_pdf_file)
    if reader is None or n == 0:
        print("No pages to process.")
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Start the load operations and mark each future with its URL
        future_to_page_text = {executor.submit(get_text_from_page, reader, i): (i) for (i) in range(n)}
        outputs = []
        for future in concurrent.futures.as_completed(future_to_page_text):
            temp = future_to_page_text[future]
            try:
                data = future.result()
                outputs.append(data)
            except Exception as exc:
                print('generated an exception: %s' % (exc))
                outputs.append('')
            else:
                try:
                    print('page is %d bytes' % (len(data)))
                except Exception:
                    print('page result length unknown')
                #outputs.append
    #print("#### extracted future_to_page_text >>>> ", len(outputs), outputs)
    return outputs


def _extract_prefix(s: str) -> Tuple[int, int]:
    """Extract numeric prefix and return (num, tie_breaker).

    Tie breaker is unused in the key but returned here for possible debugging.
    If the prefix isn't a valid int, return a large number so it sorts at the end.
    """
    if not isinstance(s, str):
        return (10 ** 9, 0)
    parts = s.split(':', 1)
    if len(parts) < 2:
        # No colon - treat as very large (put at the end)
        return (10 ** 9, 0)
    prefix = parts[0].strip()
    try:
        num = int(prefix)
        return (num, 0)
    except ValueError:
        return (10 ** 9, 0)


def sort_list_by_prefix(items: List[str]) -> List[str]:
    """Return a new list sorted by ascending numeric prefix.

    The sort is stable for equal numeric prefixes. Non-parsable or missing prefixes
    are placed at the end in their original relative order.
    """
    # Enumerate to keep stability for non-unique keys when needed
    enumerated = list(enumerate(items))

    def key_fn(pair):
        idx, s = pair
        num, _ = _extract_prefix(s)
        return (num, idx)

    enumerated.sort(key=key_fn)
    return [s for idx, s in enumerated]



def post_process_extract_sub_chapters(output):
    sub_chapters=[]
    for o in output:
        if "**chapter_title:**" in o:
            strip_o=o.index("**chapter_title:**")+18
            sub_chapters.append(o[strip_o:])
    ordered_subchapters = sort_list_by_prefix(sub_chapters)
    return ordered_subchapters
"""
path_to_pdf_file="/workspace/mnt/pdfs/SwedenDriving_intro.pdf"
output = parallel_extract_pdf_page_and_text(path_to_pdf_file)

output = post_process_extract_sub_chapters(output)

i=0
for p_text in output:
    print(f" ---------------------- extracted page number: {str(i)} ---------------------------")
    print(p_text)
    i+=1
print('\n'.join(output))"""


