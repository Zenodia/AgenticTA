from langchain_nvidia_ai_endpoints import ChatNVIDIA, NVIDIAEmbeddings, NVIDIARerank
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from operator import itemgetter
from colorama import Fore
import concurrent.futures
import os
import json
import requests
import argparse
from dotenv import load_dotenv
from extract_sub_chapters import parallel_extract_pdf_page_and_text, post_process_extract_sub_chapters
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



main_title_generation_prompt = """You are an expert in generation short chapter title to outline the studying curriculum.
        You will have access to sub_chapters extracted from each user uploaded documents

        You will analyze the sub_chapters and produce an appropriate main title for that particular document.
        <EXAMPLE>        
        sub_chapters:
        '0: Motorway Characteristics and Usage Restrictions\n1: Motorway Driving - Speeds, Entrances, and Exits\n2: Exiting Motorways & Adjusting to Lower-Speed Roads\n3: Motorway Driving Basics & Safe Overtaking Strategies\n4: Safe Driving in Traffic Queues\n5: Preparing for Post-Highway Driving: Hard Shoulder & Traffic Adjustments\n6: Best Practice for Speed Reduction when Exiting a Motorway\n7: Merging onto Motorway with Priority Considerations\n8: Driving on Expressways - Navigation & Safety Considerations\n10: Merging Lanes - Smooth Interweaving Techniques\n11: Understanding Road Sign Rules for Hard Shoulder Usage\n12: Interpreting Right-of-Way Road Signs\n13: Understanding Expressway Bans & Regulations'
        **chapter_title:**\nDriving on Motorway.\n
        

        ...and so on
        </EXAMPLE>

        <RULEs>
        You will strictly follow below 3 rules, and in this order, when you produce the chapter titles :        
        1. you should always mark your response with '**chapter_title:**\n        
        2. you will condense the provided summary into one very short sentence appropriate for a title 
        3. return only the title, do not elaborate/explain anything else.
        </RULES>
        
        current input sub_chapters: {sub_chapters}        
        **chapter_title:**\n {chapter_nr}:"""

chapter_generation_prompt_template = ChatPromptTemplate.from_template(main_title_generation_prompt)
updated_curriculum_example_1={"Chapter 1: Introduction to Driving":("merged","Chapter 1: Introduction to Driving and Basics"), 
        "Chapter 2: Before You Start Driving":("merged","Chapter 1: Introduction to Driving and Basics"), 
        "Chapter 3: Manual or automatic gearbox":("kept", None), 
        "Chapter 4: Different types of learning":("merged","Chapter 2: Learning Methods and Traffic Rules"),
        "Chapter 5: History of Car Traffic":("merged","Chapter 2: Learning Methods and Traffic Rules"),
        "Chapter 6: The ground rules for traffic":("merged","Chapter 2: Learning Methods and Traffic Rules"),
        "Chapter 7: Defensive Driving":("merged","Chapter 3: Safe Driving Practices"),
        "Chapter 8: Differnt types of Roads":("merged","Chapter 3: Safe Driving Practices"),
        "Chapter 9: Driving in Different Conditions":("merged","Chapter 3: Safe Driving Practices"),
        "Chapter 10: Safety Measures and Regulations":("merged","Chapter 3: Safe Driving Practices")}
updated_curriculum_example_2 = {"Chapter 1: Introduction to Python Programming":("split", ["Chapter 1: Basics of Python", "Chapter 2: Python Data Structures", "Chapter 3: Python Functions and Modules"])}
modify_chapter_prompt = """You are an expert in identifying and executing changes to provided chapter titles based on user feedback.
        You will have access to a curriculum made out of a list of chapter titles, each title is associated with a particular document user uploaded previously.
        Based on the user feedback, you will make necessary changes to the chapter titles. 
        <EXAMPLE>
        EXAMPLE 1: 
        ------------------------
        current_curriculum : 
        Chapter 1: Introduction to Driving, 
        Chapter 2: Before You Start Driving, 
        Chapter 3: Manual or automatic gearbox, 
        Chapter 4: Different types of learning, 
        Chapter 5: History of Car Traffic, 
        Chapter 6: The ground rules for traffic, 
        Chapter 7: Defensive Driving, 
        Chapter 8: Differnt types of Roads,
        Chapter 9: Driving in Different Conditions,
        Chapter 10: Safety Measures and Regulations

        user_feedback: there are too many chapters, it's just introduction concepts I am trying to learn, can you make it maximum 3 chapters only?
        updated_curriculum: 
        {updated_curriculum_example_1}

        EXAMPLE 2: 
        ------------------------
        current_curriculum :
        Chapter 1: Introduction to Python Programming,
        user_feedback: I think the chapter title is too broad, can you split it into more specific topics?
        updated_curriculum:
        {updated_curriculum_example_2}
        </EXAMPLE>

        <RULES>
        You will strictly follow below rules, and in this order, when you produce the updated curriculum :
        1. The updated curriculum must be in JSON format, where each key is the original chapter title, and the value is a tuple indicating the action taken ("kept", "modified", "merged", "removed") and the new title if applicable.
        2. For each chapter title in the current curriculum, you will decide either to keep it as is ("kept"), split this chapter to more chapters ("split") or merge it with another chapter ("merged")
        3. If a chapter is "kept", the new title should be None.
        4. If a chapter is "split", specify the new titles as a list of strings.
        5. If you choose "merged", specify the new title that combines the relevant chapters.
        6. You should NEVER remove a chapter title without merging it with another.
        7. You should return the updated JSON output only, without any additional explanations or text.
        8. You should always start your response with **updated_curriculum**
        </RULES>

        current_curriculum :{current_curriculum}
        user_feedback: {user_feedback}  
        updated_curriculum:
        """

modify_chapter_prompt_template = ChatPromptTemplate.from_template(modify_chapter_prompt)

modify_chapter_chain=(
    RunnablePassthrough()    
    | modify_chapter_prompt_template
    | llm
)


def parse_modified_curriculum(output):
    if '**updated_curriculum**' in output:
        output=output.replace("**updated_curriculum**","").strip()
        try :
            json_output=json.loads(output)
        except json.JSONDecodeError as e:
            print(Fore.RED + "JSONDecodeError: ", e, Fore.RESET)

            json_output= {}   
    else:
        json_output = output
    return json_output


def modify_curriculum(current_curriculum, user_feedback):
    if isinstance(current_curriculum, list):
        current_curriculum = ", ".join(current_curriculum)
    input_d={"current_curriculum":current_curriculum,"user_feedback":user_feedback, "updated_curriculum_example_1":json.dumps(updated_curriculum_example_1), "updated_curriculum_example_2":json.dumps(updated_curriculum_example_2)}
    output=modify_chapter_chain.invoke(input_d)
    final_output=parse_modified_curriculum(output.content)
    print(type(final_output), final_output.items())
    return final_output



def process_parallel_titles(summaries, chapter_nrs):
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Start the load operations and mark each future with its URL
        future_to_chapter_titles = {executor.submit(title_generator, summary, chapter_nr): (summary,chapter_nr) for (summary,chapter_nr) in zip(summaries,chapter_nrs)}
        outputs = []
        for future in concurrent.futures.as_completed(future_to_chapter_titles):
            temp = future_to_chapter_titles[future]
            try:
                data = future.result()
                outputs.append(data)
            except Exception as exc:
                print('generated an exception: %s' % (exc))
                outputs.append('')
            else:
                print('page is %d bytes' % (len(data)))
                #outputs.append
    print("#### the chapters >>>> ", len(outputs), outputs)
    return outputs




#output=title_generator(summary,chapter_nr)

def post_process_chapter_title(output_ls):
    processed_titles=[]
    for output in output_ls:
        print(Fore.BLUE + "raw output=\n\n", output, Fore.RESET)
        if '**chapter_title:**' in output: 
            out=output.replace("**chapter_title:**","").strip('\n')
            processed_titles.append(out)
        else:
            processed_titles.append(output.strip('\n'))
    return processed_titles


chapter_generation_prompt = """You are an expert in generation short chapter title to outline the studying curriculum.
    You will have access to user uploaded file names.

    You will analyze the file names and re-order them to make this list into a comprehensive study curriculum. 

    <RULEs>
    You will strictly follow below rules, and in this order, when you produce the chapter titles :        
    1. you should always mark the beginning of your response with '**curriculum:**\n        
    2. you will assume that user uploaded documents belong to one study theme
    3. you will number the re-ordered curriculum with 1., 2., 3. ... and so on.
    4. you will list the return the study curriculum in JSON format
        example of JSON format curriculum :
        1. {{"title": "chapter 1 title" , "file_loc" : "path_to_chapter_1_pdf_file" }}\n\n
        2. {{"title": "chapter 2 title" , "file_loc" : "path_to_chapter_2_pdf_file" }}\n\n
    5. return only the curriculum and do not elaborate/explain anything else.
    </RULES>
    
    pdf_file_names: {pdf_file_names}
    **curriculum:**\n"""

chapter_generation_prompt_template = ChatPromptTemplate.from_template(chapter_generation_prompt)


chapter_gen_chain = (
    RunnablePassthrough()    
    | chapter_generation_prompt_template
    | llm
)


def chapter_gen_from_pdfs(pdf_files_loc):
    pdf_file_names = [f for f in os.listdir(pdf_files_loc) if f.endswith('.pdf')]
    ordered_chapters_prompt=chapter_generation_prompt.format(pdf_file_names=pdf_file_names)
    output = astra_llm_call(ordered_chapters_prompt)
    if output :
        return output
    else:
        output=chapter_gen_chain.invoke({"pdf_file_names":pdf_file_names})
        output = output.content
        return output

def parse_output_from_chapters(output:str) -> list[dict]:
    output = output.replace("**curriculum:**", "").replace("1. ", "").replace("2. ", "").split('\n\n')
    print(type(output), output)

    # Safely attempt to parse each block into JSON. Skip blank/whitespace blocks and log parse errors.
    parsed_outputs = []
    for idx, out in enumerate(output):
        if not out or not out.strip():
            continue
        try:
            parsed = json.loads(out)
            parsed_outputs.append(parsed)
        except json.JSONDecodeError as e:
            print(Fore.RED + f"JSONDecodeError parsing block {idx}: {e}" + Fore.RESET)
            print(Fore.RED + "Offending block:\n" + out + Fore.RESET)
            # continue without aborting; append nothing for this 
            
            continue

    print(type(parsed_outputs), parsed_outputs)
    return parsed_outputs
#### test examples 
"""
summary_1="The document outlines essential safety practices for driving on country roads, emphasizing proactive scanning, speed control, and risk mitigation. Key strategies include maintaining a three-second following distance, regularly checking mirrors in a systematic pattern, and adjusting speed for conditions to avoid ,speed blindness, It details proper positioning for turns (right edge for right turns, center for lefts) and highlights dangers of overtaking and abrupt maneuvers. Technical aspects cover reaction/braking distance calculations, the impact of kinetic energy in crashes, and using roadside reflectors (spaced 50m apart) for distance judgment. The text also addresses parking restrictions, hard shoulder usage, and the importance of avoiding left turns without clear visibility. Overall, it stresses defensive driving techniques to counter higher speeds and reduced friction on rural roads."
chapter_r=2

summary_2="The document outlines critical safety considerations for driving in darkness and low-visibility conditions. It emphasizes heightened risks at night, including reduced visibility (e.g., dark-clothed pedestrians seen only at 25-30 meters with low beams) and statistics showing 2-3x higher accident rates. Key practices include strategic use of headlights (high beams for maximum visibility, low beams to avoid dazzling others), positioning vehicles closer to the center-left lane, and adjusting speed to account for reaction distances. Special guidance addresses fog/snowstorms white wall effect, wildlife risks during dawn/dusk months, and legal lighting requirements (e.g., fog lights, parking lights). The text also highlights the importance of reflectors, avoiding distractions from oncoming headlights, and proper lighting combinations for different scenarios."

summaries=[summary_1 , summary_2]
chapters=[1,2]
output = process_parallel_titles(summaries, chapters)
print(type(output), output)"""
pdf_files_loc="/workspace/mnt/pdfs/"
output = chapter_gen_from_pdfs(pdf_files_loc)
chapter_output=parse_output_from_chapters(output)
for c in chapter_output:
    print("---"*10)
    print(type(c), c)