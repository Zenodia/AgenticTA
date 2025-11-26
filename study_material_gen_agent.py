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
from openai import OpenAI
from llm import LLMClient  # This automatically loads dotenv

# Initialize the new LLM client (automatically loads dotenv)
llm_client = LLMClient()

import base64
from PIL import Image
import io
from IPython.display import Markdown, display
import markdown
#from search_and_filter_documents import filter_documents_by_file_name
from search_and_filter_docs_streaming import filter_documents_by_file_name

def printmd(markdown_str):
    display(Markdown(markdown_str))

def strip_thinking_tag(response):
    # Handle None or empty responses
    if response is None or not response:
        print(Fore.RED + "ERROR: Received None or empty response in strip_thinking_tag" + Fore.RESET)
        return ""
    
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

async def study_material_gen(username,subject,sub_topic,pdf_file_name, num_docs):
    valid_flag=False
    cnt=0
    num_docs=3
    while valid_flag==False or cnt <= 3: # allow re-trial 3 times 
        valid_flag , output, img_str = await filter_documents_by_file_name(username,sub_topic,pdf_file_name,num_docs)
        print("got valid output =" , valid_flag , valid_flag == False ) 
        if valid_flag:
            break   
        elif cnt >=1:
            break     
        cnt += 1
    if not valid_flag :
        valid_flag , output, img_str = await filter_documents_by_file_name(username,sub_topic,None,num_docs)
    if isinstance(output,str):
        detail_context=output
        study_material_generation_prompt_formatted=study_material_gen_prompts.format(subject=subject, sub_topic=sub_topic, detail_context=detail_context)
        
        # Use the new LLM client with proper use case
        llm_parsed_output = await llm_client.call(
            prompt=study_material_generation_prompt_formatted,
            use_case="study_material_generation"
        )
        #print(Fore.BLUE + "using new LLM client > llm parsed relevent_chunks as context output=\n", llm_parsed_output) 
        #print("---"*10)
        study_material_str=strip_thinking_tag(llm_parsed_output)        
        if img_str:
            
            markdown_str = markdown.markdown(f'''                
                {study_material_str}

                <br/><br/>
                Reference_document:{pdf_file_name}
                <br/><br/>
                Reference_images :
                {img_str}               
                ''')
        else:
            markdown_str = markdown.markdown(f'''                
                {study_material_str}
                
                <br/><br/>
                Reference_document:{pdf_file_name}
                ''')

        print(Fore.BLUE + "stripped thinking tag output=\n", study_material_str, Fore.RESET) 
        print("---"*10)
        return study_material_str, markdown_str
    elif isinstance(output,ls) :   
        if len(output)>0:
            detail_context='\n'.join([f"detail_context:{o["metadata"]["description"]}" for o in output if o["document_type"]=="text"])
        study_material_generation_prompt_formatted=study_material_gen_prompts.format(subject=subject, sub_topic=sub_topic, detail_context=detail_context)
        
        # Use the new LLM client with proper use case
        llm_parsed_output = await llm_client.call(
            prompt=study_material_generation_prompt_formatted,
            use_case="study_material_generation"
        )
        #print(Fore.BLUE + "using new LLM client > llm parsed relevent_chunks as context output=\n", llm_parsed_output) 
        #print("---"*10)
        study_material_str=strip_thinking_tag(llm_parsed_output)
        
        reference_images_base64_str='\n'.join([f"""<br><p align='center'><img src='data:image/png;base64,{o["content"]}'/></p></br>""" for o in output if o["document_type"] in ["image", "table", "chart"] ])
        markdown_str = markdown.markdown(f'''                
            {study_material_str}
            
            
            Reference_document:{pdf_file_name}
            
            Reference_images :
            {reference_images_base64_str}               
            ''')

        print(Fore.BLUE + "stripped thinking tag output=\n", study_material_str, Fore.RESET) 
        print("---"*10)
        
        return study_material_str , markdown_str
    else:        
        print(Fore.BLUE + "using build.nvidia.com's llm call > llm parsed relevent_chunks as context output=\n", output) 
        print("---"*10)
        #output=strip_thinking_tag(output)
        output=""
        print(Fore.BLUE + "stripped thinking tag output=\n", output, Fore.RESET) 
        print("---"*10)
        
        return output, ""
if __name__ == "__main__":
    # Move top-level async calls into an async main to avoid 'await outside function'
    #query = "fetch information on driving in highway/mortorway"
    query = "\n1: Learning Techniques for Driving - Awareness, Overlearning, and Deep Insight."
    pdf_file = "SwedenDriving_intro.pdf"
    subject=pdf_file.split('.pdf')[0]
    sub_topic="**chapter_title:**18: Driving License Regulations, Requirements & Exceptions"
    num_docs=5
    output, markdown_str =asyncio.run( study_material_gen(subject,sub_topic, pdf_file, num_docs))
    print(type(output), Fore.GREEN + "output=\n\n",output)
    