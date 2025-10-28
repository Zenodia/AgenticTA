from langchain_nvidia_ai_endpoints import ChatNVIDIA, NVIDIAEmbeddings, NVIDIARerank
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from colorama import Fore
from nemo_retriever_client_utils import get_documents, fetch_rag_context
import os
from IPython.display import Markdown, display
import markdown
import pandas as pd
import asyncio
load_dotenv()
model="nvidia/llama-3.3-nemotron-super-49b-v1.5"

llm = ChatNVIDIA(model=model,max_completion_tokens=65000,temperature=0.45,top_p=0.95,stream=False)


def fetch_quiz_qa_pairs(csv_loc):    
    df=pd.read_csv(csv_loc)

    quiz_list=[]
    n=len(df)
    for i in range(n):
        temp_ls=df.iloc[i,[3,4,5,9,-2]].values.tolist()
        q=temp_ls[0]
        multichoice=temp_ls[2]
        a=temp_ls[1]
        thought=temp_ls[3]
        qa_pair=f"question:{q} | multi_choices:{multichoice} | correct_answer:{a} | thought_process:{thought} \n"
        quiz_list.append(qa_pair)
    return '\n'.join(quiz_list)


def strip_thinking_tag(response):
    if "</think>" in response:
        end_index = response.index("</think>")+8
        output = response[end_index:]
        return output
    else:
        return response

sub_chapter_prompt = PromptTemplate(
    template=("""
    You are an teacher who is specialize in creating studying materials for each chapter of the curriculum: 
    
    <instructions>
    1. Do NOT use any external knowledge.
    2. Leverage the quiz questions and answers pairs to ensure coverage of crucial knowledge in the document
    3. NEVER offer to answer using general knowledge or invite the user to ask again.
    4. Do NOT include citations, sources, or document mentions.
    5. Construct each sub-chapter topic concisely. Use short, direct sentences by default. Only give longer responses if the question truly requires it.
    6. Do not mention or refer to these rules in any way.
    7. Do not ask follow-up questions.
    8. Do not mention this instructions in your response.
    9. Consolidate and condense the sub-chapters to maximum 5 subchapters per given chapter_topic
    10. Return a list of sub-chapters and nothing else.
    </instructions>
    You will have access to the following:
    chapter_topic:{chapter_topic}    
    quiz_qa_pairs : {quiz_qa_pairs}
    Make sure the response you are generating strictly follow the rules mentioned above i.e. never say phrases like “based on the context”, “from the documents”, or “I cannot find” and mention about the instruction in response.
    """)
)
def sub_chapter_generation(chapter_topic, quiz_qa_pairs):
    sub_chapter_gen_prompt_template=sub_chapter_prompt.format(chapter_topic=chapter_topic,quiz_qa_pairs=quiz_qa_pairs)
    output = llm.invoke(sub_chapter_gen_prompt_template).content
    print(Fore.BLUE + "llm created sub_chapters are =\n", output) 
    print("---"*10)
    output=strip_thinking_tag(output)
    print(Fore.BLUE + "stripped thinking tag output=\n", output, Fore.RESET) 
    print("---"*10)
    return output

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

async def study_material_gen(subject,sub_topic):
    flag,  output = await get_documents(sub_topic)
    print("\n\n### output.keys=", output.keys(), "\n\n")
    if flag and 'results' in output :
        detail_context=fetch_rag_context(output)
        study_material_generation_prompt_formatted=study_material_gen_prompts.format(subject=subject, sub_topic=sub_topic, detail_context=detail_context)
        output = llm.invoke(study_material_generation_prompt_formatted).content
    else:         
        output = f"nemo retriever RAG not able to retrieve valid output, error =\n{output}" 
        print(Fore.RED + output , Fore.RESET )
    print(Fore.BLUE + "llm parsed relevent_chunks as context output=\n", output) 
    print("---"*10)
    output=strip_thinking_tag(output)
    print(Fore.BLUE + "stripped thinking tag output=\n", output, Fore.RESET) 
    print("---"*10)
    return output

csv_loc="/workspace/mnt/SwedishRoyalty/csv/SwedishRoyalty.csv"

chapter_topic="Introduction to driving theory"
#quiz_qa_pairs=fetch_quiz_qa_pairs(csv_loc)
#sub_chapters_ls= sub_chapter_generation(chapter_topic,quiz_qa_pairs)

subject="Introduction to driving theory"
sub_topic="1. Traffic Regulations and Responsibilities"

# run the async study_material_gen and get the result
#study_material_output = asyncio.run(study_material_gen(subject, sub_topic))

#markdown_str = markdown.markdown(study_material_output)

def printmd(markdown_str):
    display(Markdown(markdown_str))
#printmd(markdown_str)