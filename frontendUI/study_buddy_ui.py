"""
Study Buddy UI components and logic.
"""
import sys
from pathlib import Path
# Add parent directory to path so we can import from root-level modules
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
import os, json, sys
import gradio as gr
import time
import random
import re
from config import  MAX_FILES, MAX_FILE_SIZE_GB, MAX_PAGES_PER_FILE
from utils import validate_pdf_files
import shutil
import yaml
import os
from colorama import Fore
from nemo_retriever_client_utils import delete_collections,fetch_collections, create_collection, upload_files_to_nemo_retriever, get_documents,fetch_rag_context
from nodes import init_user_storage,user_exists,load_user_state,save_user_state, _save_store, _load_store
from nodes import update_and_save_user_state, move_to_next_chapter, update_subtopic_status,add_quiz_to_subtopic, build_next_chapter, run_for_first_time_user
from standalone_study_buddy_response import study_buddy_response, query_routing, inference_call
from tool_youtube import fetch_most_relevant_youtube_video
from calendar_assistant import create_event_with_ai
import asyncio
from states import Chapter, StudyPlan, Curriculum, User, GlobalState, Status, SubTopic, printmd
from agent_memory import get_memory_ops
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
from typing import TypedDict, Annotated, Union
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.messages import BaseMessage
import operator
from typing import TypedDict, Annotated, List ,  Any
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.messages import BaseMessage
import operator
from markdown import Markdown
import asyncio
import random
from colorama import Fore
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from standalone_quizes_gen import get_quiz, quiz_output_parser
# Use MNT_FOLDER environment variable if set, otherwise fallback to reading docker-compose.yml
global mnt_folder
mnt_folder = os.environ.get("MNT_FOLDER", None)
if not mnt_folder:
    # Fallback: try to read from docker-compose.yml (for backward compatibility)
    try:
        f = open("/workspace/docker-compose.yml", "r")
        yaml_f = yaml.safe_load(f)
        mnt_folder = yaml_f["services"]["agenticta"]["volumes"][-1].split(":")[-1]
        f.close()
    except (FileNotFoundError, KeyError, IndexError) as e:
        # Default fallback if docker-compose.yml doesn't exist or is malformed
        mnt_folder = "/workspace/mnt"
        print(Fore.YELLOW + f"Warning: Could not determine mnt_folder from docker-compose.yml, using default: {mnt_folder}", Fore.RESET)

start_fresh=False

def get_curriculum_from_user_state(username:str):
    """
    Load and convert curriculum from user state JSON file to SAMPLE_CURRICULUM format.
    Returns a list in the format expected by the UI functions.
    """
    try:
        user_state = load_user_state(username)
        if not user_state or "curriculum" not in user_state or len(user_state["curriculum"]) == 0:
            return []
        
        curriculum_data = user_state["curriculum"][0]
        if "study_plan" not in curriculum_data:
            return []
        
        study_plan = curriculum_data["study_plan"]
        active_chapter = curriculum_data.get("active_chapter")
        
        # Handle both dict and StudyPlan object
        if isinstance(study_plan, dict) and "study_plan" in study_plan:
            chapters = study_plan["study_plan"]
        elif isinstance(study_plan, StudyPlan):
            chapters = study_plan.study_plan
        else:
            return []
        
        # Get active chapter number and subtopics
        if active_chapter:
            if isinstance(active_chapter, dict):
                active_chapter_num = active_chapter.get("number", -1)
                active_chapter_subtopics = active_chapter.get("sub_topics", [])
            else:
                active_chapter_num = active_chapter.number
                active_chapter_subtopics = active_chapter.sub_topics
        else:
            active_chapter_num = -1
            active_chapter_subtopics = []
        
        # Convert to SAMPLE_CURRICULUM format
        result = []
        for chapter in chapters:
            # Handle both dict and Chapter object
            if isinstance(chapter, dict):
                chapter_num = chapter.get("number", 0)
                chapter_name = chapter.get("name", "")
                sub_topics = chapter.get("sub_topics", [])
            else:
                chapter_num = chapter.number
                chapter_name = chapter.name
                sub_topics = chapter.sub_topics
            
            # If this is the active chapter and study_plan has no subtopics, use active_chapter's subtopics
            if chapter_num == active_chapter_num and (not sub_topics or len(sub_topics) == 0):
                sub_topics = active_chapter_subtopics
            
            # Build chapter label with number
            chapter_label = f"{chapter_num}:{chapter_name}"
            
            # If chapter has subtopics, create hierarchical structure
            if sub_topics and len(sub_topics) > 0:
                subtopic_names = []
                for st in sub_topics[:10]:  # Max 10 subtopics
                    if isinstance(st, dict):
                        subtopic_text = st.get("sub_topic", "").strip()
                    else:
                        subtopic_text = st.sub_topic.strip()
                    # Strip numbering
                    subtopic_text = re.sub(r'^\n?\d+:\s*', '', subtopic_text).strip()
                    subtopic_names.append(subtopic_text)
                
                result.append({
                    "topic": chapter_label,
                    "subtopics": subtopic_names
                })
            else:
                # Simple chapter without subtopics
                result.append(chapter_label)
        
        return result
    except Exception as e:
        print(Fore.RED + f"Error loading curriculum from user state: {e}", Fore.RESET)
        import traceback
        traceback.print_exc()
        return []

def generate_curriculum(file_obj, validation_msg , username , preference, study_buddy_name="Ollie",progress=gr.Progress()):
    """Generate curriculum from uploaded PDF or use sample data"""
    global mnt_folder  
    pdf_loc = os.path.join(mnt_folder, "pdfs", username)
    nemo_retriever_processed_pdf_files = os.listdir(pdf_loc)
    save_to = mnt_folder 
    print(Fore.BLUE + "generate_curriculum called with username =", username,"preference=",preference, Fore.RESET)
    _preference = preference if preference and preference.strip() else "someone who has patience, a good sense of humor, can make boring subject fun." 
    _study_buddy_name= study_buddy_name if study_buddy_name and study_buddy_name.strip() else "Ollie"
    u: User = {
        "user_id": username,
        "study_buddy_preference": _preference,
        "study_buddy_name": _study_buddy_name,
        "study_buddy_persona": None,
        "curriculum": None,
        "uploaded_files": nemo_retriever_processed_pdf_files,
    }
    store_path, user_store_dir = init_user_storage(save_to, username)
    user_exist_flag=user_exists(username)
    print(Fore.LIGHTBLUE_EX + f"user_exist_flag={user_exist_flag} for username={username}" , Fore.RESET)
    print(Fore.LIGHTBLUE_EX + f"store_path={store_path} for user_store_dir={user_store_dir}" , Fore.RESET)
    if user_exist_flag :    
        print("return user detected , loading existing state...", Fore.RESET)    
        u=load_user_state(username)
        study_plan =u["curriculum"][0]["study_plan"]
        print(type(study_plan), study_plan)
        # Load full chapter structure with subtopics
        if isinstance(study_plan, StudyPlan):
            chapters_ls = []
            for chapter in study_plan.study_plan:
                chapters_ls.append(f"{str(chapter.number)}:{chapter.name}")
        else:
            chapters_ls = []
            if isinstance(study_plan, dict) and "study_plan" in study_plan:
                for chapter in study_plan["study_plan"]:
                    chapter_name = f"{chapter['number']}:{chapter['name']}"
                    chapters_ls.append(chapter_name)
    else: 
        print(Fore.LIGHTYELLOW_EX + "New user detected, running first time setup..." , Fore.RESET)       
        global_state: GlobalState = asyncio.run(run_for_first_time_user(u, pdf_loc, save_to, preference, store_path, user_store_dir))
        u=load_user_state(username)
        study_plan =u["curriculum"][0]["study_plan"]
        print(type(study_plan), study_plan)
        if isinstance(study_plan, StudyPlan):
            chapters_ls = []
            for chapter in study_plan.study_plan:
                chapters_ls.append(f"{str(chapter.number)}:{chapter.name}")
        else:
            chapters_ls = []
            if isinstance(study_plan, dict) and "study_plan" in study_plan:
                for chapter in study_plan["study_plan"]:
                    chapter_name = f"{chapter['number']}:{chapter['name']}"
                    chapters_ls.append(chapter_name)
        
    print(Fore.BLUE + "Generated curriculum chapters_ls:", chapters_ls, Fore.RESET)
    # Check if there's a validation error
    if validation_msg and validation_msg.startswith("❌"):
        # Return current state without changes if validation failed
        outputs = [gr.Column(visible=False)]
        for i in range(10):
            outputs.append(gr.Button(visible=False))
        outputs.append([])  # Empty unlocked topics
        outputs.append([])  # Empty expanded topics
        return outputs
    
    # Get active chapter from user state for display purposes
    active_chapter = u["curriculum"][0]["active_chapter"]
    print(type(active_chapter), active_chapter)

    # Build curriculum_formatted from study_plan (which has ALL chapters with their subtopics)
    # NOT from active_chapter
    curriculum_formatted = []
    
    # Get study_plan structure
    study_plan_obj = u["curriculum"][0]["study_plan"]
    if isinstance(study_plan_obj, dict) and "study_plan" in study_plan_obj:
        all_chapters = study_plan_obj["study_plan"]
    elif isinstance(study_plan_obj, StudyPlan):
        all_chapters = study_plan_obj.study_plan
    else:
        all_chapters = []
    
    print(Fore.YELLOW + f"Building curriculum from {len(all_chapters)} chapters in study_plan", Fore.RESET)
    
    # Get active chapter number to check if we need to use its subtopics
    if isinstance(active_chapter, dict):
        active_chapter_num = active_chapter.get("number", -1)
        active_chapter_subtopics = active_chapter.get("sub_topics", [])
    else:
        active_chapter_num = active_chapter.number
        active_chapter_subtopics = active_chapter.sub_topics
    
    # Iterate through each chapter in study_plan and extract its subtopics
    for chapter in all_chapters:
        # Handle both dict and object formats
        if isinstance(chapter, dict):
            chapter_num = chapter.get("number", 0)
            chapter_name = chapter.get("name", "Unknown")
            chapter_subtopics = chapter.get("sub_topics", [])
        else:
            chapter_num = chapter.number
            chapter_name = chapter.name
            chapter_subtopics = chapter.sub_topics
        
        # If this is the active chapter and study_plan has no subtopics, use active_chapter's subtopics
        if chapter_num == active_chapter_num and (not chapter_subtopics or len(chapter_subtopics) == 0):
            chapter_subtopics = active_chapter_subtopics
            print(Fore.YELLOW + f"Using active_chapter subtopics for chapter {chapter_num}", Fore.RESET)
        
        # Extract subtopic texts
        subtopic_texts = []
        for subtopic in chapter_subtopics:
            if isinstance(subtopic, dict):
                subtopic_text = subtopic.get("sub_topic", "").strip()
            else:
                subtopic_text = subtopic.sub_topic.strip()
            # Strip numbering
            subtopic_text = re.sub(r'^\n?\d+:\s*', '', subtopic_text).strip()
            subtopic_texts.append(subtopic_text)
        
        # Add to curriculum_formatted
        chapter_label = f"{chapter_num}:{chapter_name}"
        if subtopic_texts and len(subtopic_texts) > 0:
            curriculum_formatted.append({
                "topic": chapter_label,
                "subtopics": subtopic_texts[:10]  # Max 10 subtopics
            })
            print(Fore.CYAN + f"Chapter {chapter_num}: {chapter_name} with {len(subtopic_texts)} subtopics", Fore.RESET)
        else:
            curriculum_formatted.append(chapter_label)
            print(Fore.CYAN + f"Chapter {chapter_num}: {chapter_name} (no subtopics)", Fore.RESET)
    
    # Build response display from active_chapter
    active_subtopics = active_chapter.get("sub_topics") if isinstance(active_chapter, dict) else active_chapter.sub_topics
    
    # Find the current subtopic (first incomplete one, or first one if all completed/new)
    current_subtopic = None
    current_subtopic_idx = 0
    
    if active_subtopics:
        # First, try to find a subtopic that's NA or STARTED
        for idx, subtopic in enumerate(active_subtopics):
            if isinstance(subtopic, dict):
                status = subtopic.get("status", Status.NA.value)
                if isinstance(status, Status):
                    status_value = status.value
                else:
                    status_value = status
            else:
                status = getattr(subtopic, "status", Status.NA)
                if isinstance(status, Status):
                    status_value = status.value
                else:
                    status_value = status
            
            # If this subtopic is not completed, use it
            if status_value != Status.COMPLETED.value:
                current_subtopic = subtopic
                current_subtopic_idx = idx
                print(Fore.GREEN + f"Found current subtopic at index {idx}: status={status_value}", Fore.RESET)
                break
        
        # If all are completed or none found, use the first one
        if current_subtopic is None:
            current_subtopic = active_subtopics[0]
            current_subtopic_idx = 0
            print(Fore.YELLOW + f"All subtopics completed or none found, using first subtopic", Fore.RESET)
    
    if isinstance(active_chapter, dict):
        chapter_number = active_chapter.get("number", 0)
        chapter_name = active_chapter.get("name", "Unknown")
        if current_subtopic:
            current_subtopic_name = current_subtopic.get("sub_topic", "N/A") if isinstance(current_subtopic, dict) else current_subtopic.sub_topic
            current_study_material = current_subtopic.get("study_material", "No material available") if isinstance(current_subtopic, dict) else current_subtopic.study_material
        else:
            current_subtopic_name = "N/A"
            current_study_material = "No material available"
    else:
        chapter_number = active_chapter.number
        chapter_name = active_chapter.name
        if current_subtopic:
            current_subtopic_name = current_subtopic.sub_topic if current_subtopic else "N/A"
            current_study_material = current_subtopic.study_material if current_subtopic else "No material available"
        else:
            current_subtopic_name = "N/A"
            current_study_material = "No material available"
    
    response = f"""
            ### Chapter {str(chapter_number)}: {chapter_name}

            #### Study Topic #{current_subtopic_idx + 1}: {current_subtopic_name}

            **Study Material:**

            {current_study_material}"""


    # In a real app, you would extract content from PDF here
    # For demo, we'll just return sample curriculum
    # curriculum = [f"Chapter {i+1}: Extracted Topic {i+1}" for i in range(5)]
    # Flatten the hierarchical curriculum structure
    _curriculum = []
    for item in curriculum_formatted:
        if isinstance(item, dict):
            # Add main topic
            _curriculum.append(item["topic"])
            # Add subtopics with indentation (max 10 subtopics)
            subtopics_to_add = item["subtopics"][:10]  # Limit to 10 subtopics
            for subtopic in subtopics_to_add:
                _curriculum.append(f"  ↳ {subtopic}")
        else:
            # Add regular topic
            _curriculum.append(item)

    # Initialize unlocked topics - only first subtopic under each main topic is unlocked
    unlocked_topics = set()
    for i, topic in enumerate(_curriculum):
        # Main topics and non-subtopic items are always unlocked
        if not topic.startswith("  ↳ "):
            unlocked_topics.add(topic)
        # First subtopic after a main topic is unlocked
        elif i > 0 and not _curriculum[i-1].startswith("  ↳ "):
            unlocked_topics.add(topic)
    
    # Debug output
    print(Fore.CYAN + "Generated curriculum_formatted:", curriculum_formatted, Fore.RESET)
    print(Fore.MAGENTA + "Generated _curriculum (flattened):", _curriculum, Fore.RESET)
    print(Fore.GREEN + "Unlocked topics:", list(unlocked_topics), Fore.RESET)
    
    # Auto-expand all topics with subtopics
    expanded_topics_set = set()
    for item in curriculum_formatted:
        if isinstance(item, dict) and "subtopics" in item and len(item["subtopics"]) > 1:
            # Strip numbering for consistency
            topic_stripped = re.sub(r'^\d+:', '', item['topic']).strip()
            expanded_topics_set.add(topic_stripped)
            print(Fore.MAGENTA + f"Auto-expanding: '{topic_stripped}'", Fore.RESET)
    
    # Create checkboxes and buttons (10 max) - all visible, no hiding
    outputs = [gr.Column(visible=True)]
    
    # First add all checkboxes - all visible from the start
    for i in range(10):
        if i < len(_curriculum):
            button_text = _curriculum[i]
            # All checkboxes visible
            outputs.append(gr.Checkbox(visible=True, value=False))
        else:
            outputs.append(gr.Checkbox(visible=False))
    
    # Then add all buttons - non-interactive (not clickable)
    for i in range(10):
        if i < len(_curriculum):
            button_text = _curriculum[i]
            is_subtopic = button_text.startswith("  ↳ ")
            # All buttons visible but NOT clickable
            print(Fore.YELLOW + f"Button {i}: text='{button_text}', visible=True, interactive=False", Fore.RESET)
            outputs.append(gr.Button(button_text, visible=True, interactive=False))
        else:
            outputs.append(gr.Button(visible=False))
    
    # Return outputs + study material section + unlocked topics + expanded topics + completed topics
    outputs.append(gr.Accordion(visible=True))  # Show study material section
    outputs.append(gr.Markdown(value=response))  # Display first subtopic's study material
    outputs.append(list(unlocked_topics))
    outputs.append(list(expanded_topics_set))  # All topics with subtopics are expanded
    outputs.append([])  # No topics completed initially
    return outputs


def handle_file_upload(files, username, progress=gr.Progress()):
    """Handle file upload and validate"""
    if files is None or len(files) == 0:
        return ""
    
    global mnt_folder  

    print(Fore.BLUE + "mnt_folder =", mnt_folder, "username=", username, Fore.RESET)
    pdf_dir = os.path.join(mnt_folder, "pdfs", username)
    user_name_folder=os.path.join(mnt_folder,username)
    os.makedirs(pdf_dir, exist_ok=True)
    os.makedirs(user_name_folder, exist_ok=True)
    new_ls=[shutil.copy(f, pdf_dir) for f in files]
    # Call create collection method
    print(Fore.YELLOW + "new_ls=\n", new_ls, Fore.RESET)
    
    processed_files = os.path.join(mnt_folder,f"{username}_files.txt")
    my_file = Path(processed_files)
    exist_processed_files_flag=my_file.is_file()
    if exist_processed_files_flag:
        f=open(processed_files,"r+")
        processed_files_ls= f.readlines()
        processed_files_ls=[f for f in processed_files_ls if f.endswith(".pdf")]
        print(Fore.CYAN + " !! skip already processed files  =\n", processed_files_ls)
        new_files_ls = [ os.path.join(pdf_dir, f) for f in files if f not in processed_files_ls]
        print("+ = new added files =\n ", new_files_ls, "append to processed files", Fore.RESET)
        _=[f.write(file) for file in new_files_ls] # python will convert \n to os.linesep
        f.close()
    else:
        f=open(processed_files,"w")
        _=[f.write(f'{os.path.join(pdf_dir,pdf_file)}\n') for pdf_file in os.listdir(pdf_dir) if pdf_file.endswith(".pdf")] # python will convert \n to os.linesep
        new_files_ls=[os.path.join(pdf_dir,pdf_file) for pdf_file in os.listdir(pdf_dir) if pdf_file.endswith(".pdf")] # python will convert \n to os.linesep
        print(Fore.CYAN+" >> newl yadded files =\n ", new_files_ls, "append to processed files")
        f.close()
    
    
    # [Optional]: Define schema for metadata fields
    metadata_schema = [    
        {
            "name": "source_ref",
            "type": "string",
            "description": "Reference name to the source pdf document"
        }
    ]
    if start_fresh :
        asyncio.run(delete_collections([username,"metadata_schema","meta"]))        
        time.sleep(10)  # Make loading visible
    output_collection = asyncio.run(fetch_collections())
    print(type(output_collection), output_collection)
    if isinstance(output_collection, str):
        output_collection = json.loads(output_collection)        
        output_collection_ls = [c["collection_name"] for c in output_collection["collections"] if c["collection_name"]==username]
        #print(Fore.YELLOW + f"output_collection_ls for user {username} =", output_collection_ls , Fore.RESET)
        if len(output_collection_ls) > 0:
            print(Fore.YELLOW + f"Collection for user {username} already exists." , Fore.RESET)
        #delete_output=asyncio.run(delete_user_nemo_collection([username]))
        #print(Fore.YELLOW + f"Deleted existing collection for user {username}: {delete_output}" , Fore.RESET)
        else:
            print(Fore.YELLOW + f"creating new collection with collectio name = {username}" , Fore.RESET)
            # Call create collection method
            asyncio.run(create_collection(
                collection_name=username,
                metadata_schema=metadata_schema # Optional argument, can be commented if metadata is not to be inserted
            ))
            time.sleep(10)
    if len(new_files_ls)>0:
        nemo_retriever_files_upload_output = asyncio.run(upload_files_to_nemo_retriever(new_files_ls , username,[]))
    else:
        print("already processed these files, skipping ... ")
    time.sleep(20)
    print(Fore.BLUE + "Copied files to pdf_dir =", '\n'.join(new_ls), Fore.RESET)
    print(Fore.BLUE + "\n nemo_retriever_files_upload_output =", nemo_retriever_files_upload_output, Fore.RESET)
    progress(0, desc="📤 Uploading files...")
    time.sleep(0.8)  # Make loading visible
    
    progress(0.2, desc="📋 Validating file count...")
    time.sleep(0.6)
    
    progress(0.4, desc="📏 Checking file sizes...")
    time.sleep(0.6)
    
    progress(0.6, desc="📄 Verifying PDF format...")
    time.sleep(0.6)
    
    progress(0.8, desc="🔍 Checking page counts...")
    is_valid, message = validate_pdf_files(files)
    time.sleep(0.5)
    
    progress(1.0, desc="✅ Validation complete!")
    time.sleep(0.3)
    
    return message


# Note: show_chapter_content removed - buttons are now non-clickable


def mark_topic_complete(checkbox_value, checkbox_index, unlocked_topics, expanded_topics, completed_topics, username, *button_values):
    """Mark a topic as complete/incomplete based on checkbox change"""
    global mnt_folder  
    save_to=mnt_folder
    print(Fore.BLUE + f"mark_topic_complete called: checkbox_{checkbox_index}={checkbox_value}, username={username}, save_to={save_to}", Fore.RESET)
    print(Fore.BLUE + f"unlocked_topics={unlocked_topics}, expanded_topics={expanded_topics}, completed_topics={completed_topics}","\n", Fore.RESET)
    print(button_values)
    
    # Load curriculum from user state
    CURRICULUM = get_curriculum_from_user_state(username)
    
    # Flatten curriculum to get topic order
    curriculum = []
    for item in CURRICULUM:
        if isinstance(item, dict):
            curriculum.append(item["topic"])
            for subtopic in item["subtopics"]:
                curriculum.append(f"  ↳ {subtopic}")
        else:
            curriculum.append(item)
    
    # Get the topic name for this checkbox
    if checkbox_index >= len(curriculum):
        print(Fore.RED + f"Checkbox index {checkbox_index} out of range", Fore.RESET)
        # Return current state unchanged
        return ([gr.update() for _ in range(10)] + [gr.update() for _ in range(10)] + 
                [unlocked_topics, completed_topics])
    
    topic_name = curriculum[checkbox_index]
    print(Fore.CYAN + f"Topic for checkbox {checkbox_index}: '{topic_name}'", Fore.RESET)
    
    # Update completed topics based on checkbox state
    new_completed = set(completed_topics)
    new_unlocked = set(unlocked_topics)
    
    # Variable to store generated quiz for immediate use
    generated_quiz_data = None
    generated_subtopic_name = None
    
    # Variable to store study material for display update
    study_material_markdown = None
    
    if checkbox_value:
        # Mark as complete
        new_completed.add(topic_name)
        print(Fore.GREEN + f"Marking '{topic_name}' as completed", Fore.RESET)
        
        # Update study material display if this is a subtopic
        if topic_name.startswith("  ↳ "):
            try:
                # Load user state
                u = load_user_state(username)
                
                if u and "curriculum" in u and len(u["curriculum"]) > 0:
                    active_chapter = u["curriculum"][0]["active_chapter"]
                    
                    # Strip numbering and arrow from topic name
                    subtopic_name = topic_name.replace("  ↳ ", "").strip()
                    subtopic_name = re.sub(r'^\d+:\s*', '', subtopic_name).strip()
                    
                    # Get chapter info for display
                    if isinstance(active_chapter, dict):
                        chapter_number = active_chapter.get("number", 0)
                        chapter_name = active_chapter.get("name", "Unknown")
                    else:
                        chapter_number = active_chapter.number
                        chapter_name = active_chapter.name
                    
                    # Find the matching subtopic to get its study material
                    for idx, subtopic in enumerate(active_chapter.sub_topics if isinstance(active_chapter, dict) else active_chapter.sub_topics):
                        # Handle both dict and object formats
                        if isinstance(subtopic, dict):
                            raw_subtopic = subtopic.get("sub_topic", "")
                            subtopic_study_material = subtopic.get("display_markdown", "No study material available.")
                        else:
                            raw_subtopic = subtopic.sub_topic
                            # Try display_markdown first, fallback to study_material
                            subtopic_study_material = getattr(subtopic, 'display_markdown', None) or getattr(subtopic, 'study_material', "No study material available.")
                        
                        subtopic_text = re.sub(r'^\n?\d+:\s*', '', raw_subtopic.strip()).strip()
                        
                        if subtopic_name in subtopic_text or subtopic_text in subtopic_name:
                            print(Fore.CYAN + f"Found matching subtopic at index {idx} for study material display", Fore.RESET)
                            
                            # Format the study material markdown
                            study_material_markdown = f"""
### Chapter {str(chapter_number)}: {chapter_name}

#### Study Topic #{idx + 1}: {subtopic_text}

**Study Material:**

{subtopic_study_material}"""
                            print(Fore.GREEN + f"✓ Study material display updated for subtopic '{subtopic_name}'", Fore.RESET)
                            break
            except Exception as e:
                print(Fore.RED + f"Error updating study material display: {e}", Fore.RESET)
                import traceback
                traceback.print_exc()
        
        # Generate quiz if this is a subtopic
        if topic_name.startswith("  ↳ "):
            print(Fore.MAGENTA + f"## Generating quiz for subtopic: '{topic_name}'", Fore.RESET)
            
            try:
                # Load user state
                u = load_user_state(username)
                
                if u and "curriculum" in u and len(u["curriculum"]) > 0:
                    active_chapter = u["curriculum"][0]["active_chapter"]
                    
                    # Strip numbering and arrow from topic name
                    subtopic_name = topic_name.replace("  ↳ ", "").strip()
                    subtopic_name = re.sub(r'^\d+:\s*', '', subtopic_name).strip()
                    
                    print(Fore.CYAN + f"Looking for subtopic: '{subtopic_name}'", Fore.RESET)
                    
                    # Find the matching subtopic
                    for idx, subtopic in enumerate(active_chapter.sub_topics):
                        # Handle both dict and object formats
                        if isinstance(subtopic, dict):
                            raw_subtopic = subtopic.get("sub_topic", "")
                        else:
                            raw_subtopic = subtopic.sub_topic
                        
                        subtopic_text = re.sub(r'^\n?\d+:\s*', '', raw_subtopic.strip()).strip()
                        
                        print(Fore.YELLOW + f"  Comparing idx={idx}: '{subtopic_name}' vs '{subtopic_text}'", Fore.RESET)
                        
                        if subtopic_name in subtopic_text or subtopic_text in subtopic_name:
                            print(Fore.GREEN + f"Found matching subtopic at index {idx}", Fore.RESET)
                            
                            # Check if quiz already exists
                            existing_quizzes = subtopic.get("quizzes") if isinstance(subtopic, dict) else getattr(subtopic, 'quizzes', None)
                            
                            if existing_quizzes and isinstance(existing_quizzes, list) and len(existing_quizzes) > 0:
                                # Check if quizzes is a valid list with dict items
                                if isinstance(existing_quizzes[0], dict):
                                    print(Fore.CYAN + f"✓ Quiz already exists for this subtopic ({len(existing_quizzes)} questions), skipping generation", Fore.RESET)
                                    # Use existing quiz data
                                    generated_quiz_data = existing_quizzes
                                    generated_subtopic_name = subtopic_name
                                    
                                    # Update subtopic status to COMPLETED (checkbox was marked)
                                    if isinstance(subtopic, dict):
                                        subtopic["status"] = Status.COMPLETED.value
                                    else:
                                        subtopic.status = Status.COMPLETED
                                    
                                    # Also update status and quizzes in study_plan to keep both locations in sync
                                    if "study_plan" in u["curriculum"][0]:
                                        study_plan = u["curriculum"][0]["study_plan"]
                                        # Get active chapter number (handle both dict and object)
                                        if isinstance(active_chapter, dict):
                                            active_chapter_num = active_chapter.get("number", -1)
                                        else:
                                            active_chapter_num = active_chapter.number
                                        
                                        if isinstance(study_plan, dict) and "study_plan" in study_plan:
                                            chapters = study_plan["study_plan"]
                                            for chapter in chapters:
                                                if isinstance(chapter, dict) and chapter.get("number") == active_chapter_num:
                                                    if "sub_topics" in chapter and idx < len(chapter["sub_topics"]):
                                                        chapter["sub_topics"][idx]["status"] = Status.COMPLETED.value
                                                        chapter["sub_topics"][idx]["quizzes"] = existing_quizzes
                                                    break
                                        elif hasattr(study_plan, 'study_plan'):
                                            # Handle BaseModel StudyPlan
                                            chapters = study_plan.study_plan
                                            for chapter in chapters:
                                                if hasattr(chapter, 'number') and chapter.number == active_chapter_num:
                                                    if hasattr(chapter, 'sub_topics') and idx < len(chapter.sub_topics):
                                                        chapter.sub_topics[idx].status = Status.COMPLETED
                                                        chapter.sub_topics[idx].quizzes = existing_quizzes
                                                    break
                                    
                                    # Save the updated status and quizzes
                                    save_user_state(username, u)
                                    print(Fore.GREEN + f"✓ Status=COMPLETED and quizzes saved for existing quiz subtopic '{subtopic_name}'", Fore.RESET)
                                    break
                            
                            # Generate quiz if it doesn't exist
                            print(Fore.YELLOW + f"No existing quiz found, generating new quiz...", Fore.RESET)
                            
                            # Get subtopic properties (handle both dict and object)
                            if isinstance(active_chapter, dict):
                                title = active_chapter.get("name", "")
                            else:
                                title = active_chapter.name
                            
                            if isinstance(subtopic, dict):
                                summary = subtopic.get("sub_topic", "")
                                text_chunk = subtopic.get("study_material", "")
                            else:
                                summary = subtopic.sub_topic
                                text_chunk = subtopic.study_material
                            
                            print(Fore.YELLOW + f"Generating quiz with title='{title}', summary='{summary[:50]}...'", Fore.RESET)
                            
                            quizes_ls = get_quiz(title, summary, text_chunk, "")
                            print(type(quizes_ls), quizes_ls)
                            quizzes_d_ls = quiz_output_parser(quizes_ls)
                            
                            print(Fore.GREEN + f"Generated {len(quizzes_d_ls)} quizzes", Fore.RESET)
                            
                            # Store the generated quiz data for immediate UI use
                            generated_quiz_data = quizzes_d_ls
                            generated_subtopic_name = subtopic_name
                            
                            # Update the subtopic with the quiz 
                            if isinstance(subtopic, dict):
                                subtopic["quizzes"] = quizzes_d_ls
                                
                            else:
                                subtopic.quizzes = quizzes_d_ls
                                
                            
                            # Also update status and quizzes in study_plan to keep both locations in sync
                            if "study_plan" in u["curriculum"][0]:
                                study_plan = u["curriculum"][0]["study_plan"]
                                # Get active chapter number (handle both dict and object)
                                if isinstance(active_chapter, dict):
                                    active_chapter_num = active_chapter.get("number", -1)
                                else:
                                    active_chapter_num = active_chapter.number
                                
                                if isinstance(study_plan, dict) and "study_plan" in study_plan:
                                    chapters = study_plan["study_plan"]
                                    for chapter in chapters:
                                        if isinstance(chapter, dict) and chapter.get("number") == active_chapter_num:
                                            if "sub_topics" in chapter and idx < len(chapter["sub_topics"]):
                                                chapter["sub_topics"][idx]["status"] = Status.COMPLETED.value
                                                chapter["sub_topics"][idx]["quizzes"] = quizzes_d_ls
                                            break
                                elif hasattr(study_plan, 'study_plan'):
                                    # Handle BaseModel StudyPlan
                                    chapters = study_plan.study_plan
                                    for chapter in chapters:
                                        if hasattr(chapter, 'number') and chapter.number == active_chapter_num:
                                            if hasattr(chapter, 'sub_topics') and idx < len(chapter.sub_topics):
                                                chapter.sub_topics[idx].status = Status.COMPLETED
                                                chapter.sub_topics[idx].quizzes = quizzes_d_ls
                                            break
                            
                            # Save the user state with updated quizzes AND status back to json file
                            save_user_state(username, u)
                            print(Fore.GREEN + f"✓ Quiz generated, status=COMPLETED, and study_plan updated for subtopic '{subtopic_name}'", Fore.RESET)
                            print(Fore.CYAN + f"✓ Quiz data stored in memory for immediate UI display", Fore.RESET)
                            break
                    else:
                        print(Fore.RED + f"Warning: Could not find matching subtopic for '{subtopic_name}'", Fore.RESET)
                else:
                    print(Fore.RED + f"Warning: User state not found or empty", Fore.RESET)
            except Exception as e:
                print(Fore.RED + f"Error generating quiz: {e}", Fore.RESET)
                import traceback
                traceback.print_exc()
            
            # Find next item in curriculum
            if checkbox_index + 1 < len(curriculum):
                next_topic = curriculum[checkbox_index + 1]
                # Only unlock if it's also a subtopic (within same chapter)
                if next_topic.startswith("  ↳ "):
                    new_unlocked.add(next_topic)
                    print(Fore.GREEN + f"Unlocking next subtopic: '{next_topic}'", Fore.RESET)
    else:
        # Unmark as complete
        if topic_name in new_completed:
            new_completed.remove(topic_name)
            print(Fore.YELLOW + f"Unmarking '{topic_name}' as completed", Fore.RESET)
            
            # If this is a subtopic, also update the status in user state
            if topic_name.startswith("  ↳ "):
                try:
                    # Load user state
                    u = load_user_state(username)
                    
                    if u and "curriculum" in u and len(u["curriculum"]) > 0:
                        active_chapter = u["curriculum"][0]["active_chapter"]
                        
                        # Strip numbering and arrow from topic name
                        subtopic_name = topic_name.replace("  ↳ ", "").strip()
                        subtopic_name = re.sub(r'^\d+:\s*', '', subtopic_name).strip()
                        
                        print(Fore.CYAN + f"Unmarking subtopic in user state: '{subtopic_name}'", Fore.RESET)
                        
                        # Find the matching subtopic
                        for idx, subtopic in enumerate(active_chapter.sub_topics):
                            # Handle both dict and object formats
                            if isinstance(subtopic, dict):
                                raw_subtopic = subtopic.get("sub_topic", "")
                            else:
                                raw_subtopic = subtopic.sub_topic
                            
                            subtopic_text = re.sub(r'^\n?\d+:\s*', '', raw_subtopic.strip()).strip()
                            
                            if subtopic_name in subtopic_text or subtopic_text in subtopic_name:
                                print(Fore.GREEN + f"Found matching subtopic at index {idx} to unmark", Fore.RESET)
                                
                                # Update the subtopic status back to NA or STARTED
                                if isinstance(subtopic, dict):
                                    subtopic["status"] = Status.NA.value
                                else:
                                    subtopic.status = Status.NA
                                
                                # Also update status in study_plan to keep both locations in sync
                                if "study_plan" in u["curriculum"][0]:
                                    study_plan = u["curriculum"][0]["study_plan"]
                                    # Get active chapter number (handle both dict and object)
                                    if isinstance(active_chapter, dict):
                                        active_chapter_num = active_chapter.get("number", -1)
                                    else:
                                        active_chapter_num = active_chapter.number
                                    
                                    if isinstance(study_plan, dict) and "study_plan" in study_plan:
                                        chapters = study_plan["study_plan"]
                                        for chapter in chapters:
                                            if isinstance(chapter, dict) and chapter.get("number") == active_chapter_num:
                                                if "sub_topics" in chapter and idx < len(chapter["sub_topics"]):
                                                    chapter["sub_topics"][idx]["status"] = Status.NA.value
                                                break
                                    elif hasattr(study_plan, 'study_plan'):
                                        # Handle BaseModel StudyPlan
                                        chapters = study_plan.study_plan
                                        for chapter in chapters:
                                            if hasattr(chapter, 'number') and chapter.number == active_chapter_num:
                                                if hasattr(chapter, 'sub_topics') and idx < len(chapter.sub_topics):
                                                    chapter.sub_topics[idx].status = Status.NA
                                                break
                                
                                # Save the updated status
                                save_user_state(username, u)
                                print(Fore.GREEN + f"✓ Status=NA saved for unmarked subtopic '{subtopic_name}'", Fore.RESET)
                                break
                except Exception as e:
                    print(Fore.RED + f"Error unmarking subtopic: {e}", Fore.RESET)
                    import traceback
                    traceback.print_exc()
    
    # Generate checkbox updates - all visible
    checkbox_updates = []
    for i in range(10):
        if i < len(curriculum):
            topic = curriculum[i]
            is_checked = topic in new_completed
            # All checkboxes always visible
            checkbox_updates.append(gr.Checkbox(visible=True, value=is_checked))
        else:
            checkbox_updates.append(gr.Checkbox(visible=False))
    
    # Generate button updates - all visible, non-interactive
    button_updates = []
    for i in range(10):
        if i < len(curriculum):
            topic = curriculum[i]
            # All buttons always visible but NOT clickable
            button_updates.append(gr.Button(value=topic, visible=True, interactive=False))
        else:
            button_updates.append(gr.Button(visible=False))
    
    # Generate quiz UI components if a subtopic was just checked
    quiz_components = []
    quiz_accordion_visible = False
    score_visible = False
    submit_visible = False
    current_subtopic_name = ""
    total_questions = 0
    
    # Use the generated quiz data directly (from memory, not from file reload)
    if checkbox_value and topic_name.startswith("  ↳ ") and generated_quiz_data:
        print(Fore.CYAN + f"Using generated quiz data from memory for UI display", Fore.RESET)
        try:
            quiz_list = generated_quiz_data
            print(Fore.GREEN + f"Loading {len(quiz_list)} quizzes for display", Fore.RESET)
            
            # Create quiz UI components
            for i in range(10):
                if i < len(quiz_list):
                    q = quiz_list[i]
                    # Quiz format: 'question', 'choices' (list of 4 items), 'answer' (A/B/C/D), 'citations'
                    question_text = q.get('question', f"Question {i+1}")
                    choices = q.get('choices', [])
                    answer = q.get('answer', '')
                    citations = q.get('citations', [])
                    
                    # Create explanation from citations
                    if citations:
                        explanation_text = f"**Correct Answer:** {answer}\n\n**Supporting Citations:**\n" + "\n".join(f"- {c}" for c in citations)
                    else:
                        explanation_text = f"**Correct Answer:** {answer}"
                    
                    radio = gr.Radio(
                        choices=choices,
                        label=f"Q{i+1}: {question_text}",
                        interactive=True,
                        visible=True,
                        value=None
                    )
                    explanation = gr.Markdown(
                        explanation_text,
                        visible=False
                    )
                    quiz_components.extend([radio, explanation])
                else:
                    quiz_components.extend([
                        gr.Radio(visible=False, value=None),
                        gr.Markdown(visible=False)
                    ])
            
            quiz_accordion_visible = True
            score_visible = True
            submit_visible = True
            current_subtopic_name = generated_subtopic_name
            total_questions = len(quiz_list)
            print(Fore.GREEN + f"✓ Quiz UI populated with {total_questions} questions", Fore.RESET)
            
        except Exception as e:
            print(Fore.RED + f"Error creating quiz UI: {e}", Fore.RESET)
            import traceback
            traceback.print_exc()
    
    # If no quiz loaded, create empty components
    if not quiz_components:
        for _ in range(10):
            quiz_components.extend([
                gr.Radio(visible=False, value=None),
                gr.Markdown(visible=False)
            ])
    
    # Prepare study material display update
    if study_material_markdown:
        study_material_update = gr.Markdown(value=study_material_markdown)
    else:
        study_material_update = gr.update()  # No change
    
    return (checkbox_updates + button_updates + 
            [study_material_update,  # study_material_display
             gr.Accordion(visible=quiz_accordion_visible),  # quiz_accordion
             gr.Textbox(value=f"0/{total_questions}" if total_questions > 0 else "0/0", visible=score_visible),  # score_counter
             current_subtopic_name,  # current_chapter
             total_questions]  # total_questions_state
            + quiz_components +  # 20 components (10 radio + 10 markdown)
            [list(new_unlocked), expanded_topics, list(new_completed),
             gr.Button(visible=submit_visible),  # submit_btn
             gr.Button(visible=False, interactive=False)])  # next_chapter_btn (not used)


def go_to_next_chapter(unlocked_topics, expanded_topics, completed_topics, username):
    """Load and display the next chapter after user passes the quiz.
    
    This function:
    1. Reloads the user state (which was updated by move_to_next_chapter in check_answers)
    2. Extracts the new active chapter and its subtopics
    3. Updates the curriculum UI to show the new chapter
    4. Resets quiz components
    """
    global mnt_folder
    save_to = mnt_folder
    
    print(Fore.BLUE + f"go_to_next_chapter called for username={username}", Fore.RESET)
    
    try:
        # Reload user state to get the updated active chapter
        u = load_user_state(username)
        
        if not u or "curriculum" not in u or len(u["curriculum"]) == 0:
            print(Fore.RED + "Error: No curriculum found", Fore.RESET)
            # Return current state unchanged
            return ([gr.update() for _ in range(10)] + [gr.update() for _ in range(10)] + 
                    [gr.Accordion(visible=True), gr.Markdown(), unlocked_topics, expanded_topics, completed_topics,
                     gr.Button(visible=False), gr.Button(visible=False)])
        
        active_chapter = u["curriculum"][0]["active_chapter"]
        print(Fore.CYAN + f"Active chapter: {active_chapter.name}", Fore.RESET)
        
        # Extract subtopics
        sub_topics = []
        for subtopic in active_chapter.sub_topics:
            subtopic_text = subtopic.sub_topic.strip()
            subtopic_text = re.sub(r'^\n?\d+:\s*', '', subtopic_text).strip()
            sub_topics.append(subtopic_text)
        
        print(Fore.CYAN + f"Extracted sub_topics: {sub_topics}", Fore.RESET)
        
        # Get the full curriculum structure
        study_plan = u["curriculum"][0]["study_plan"]
        if isinstance(study_plan, StudyPlan):
            chapters_ls = [f"{str(chapter.number)}:{chapter.name}" for chapter in study_plan.study_plan]
        else:
            chapters_ls = []
        
        # Build curriculum_formatted similar to generate_curriculum
        curriculum_formatted = []
        for i, chapter in enumerate(chapters_ls):
            # Check if this is the active chapter
            chapter_num = int(chapter.split(":")[0])
            if chapter_num == active_chapter.number:
                temp = {
                    "topic": chapter,
                    "subtopics": sub_topics
                }
                curriculum_formatted.append(temp)
            else:
                curriculum_formatted.append(chapter)
        
        # Flatten curriculum
        _curriculum = []
        for item in curriculum_formatted:
            if isinstance(item, dict):
                _curriculum.append(item["topic"])
                subtopics_to_add = item["subtopics"][:10]
                for subtopic in subtopics_to_add:
                    _curriculum.append(f"  ↳ {subtopic}")
            else:
                _curriculum.append(item)
        
        # Initialize unlocked topics - main topics and first subtopic under active chapter
        new_unlocked = set()
        for i, topic in enumerate(_curriculum):
            if not topic.startswith("  ↳ "):
                new_unlocked.add(topic)
            elif i > 0 and not _curriculum[i-1].startswith("  ↳ "):
                new_unlocked.add(topic)
        
        # Auto-expand the active chapter
        new_expanded = set()
        for item in curriculum_formatted:
            if isinstance(item, dict) and "subtopics" in item and len(item["subtopics"]) > 1:
                topic_stripped = re.sub(r'^\d+:', '', item['topic']).strip()
                new_expanded.add(topic_stripped)
        
        # Reset completed topics (new chapter)
        new_completed = set()
        
        # Display first subtopic's study material
        response = f"""
                ### Chapter {str(active_chapter.number)}: {active_chapter.name}

                #### 1st Study Topic: {active_chapter.sub_topics[0].sub_topic}

                **Study Material:**

                {active_chapter.sub_topics[0].study_material}"""
        
        # Create checkbox updates - all visible
        checkbox_updates = []
        for i in range(10):
            if i < len(_curriculum):
                checkbox_updates.append(gr.Checkbox(visible=True, value=False))
            else:
                checkbox_updates.append(gr.Checkbox(visible=False))
        
        # Create button updates - all visible, non-interactive
        button_updates = []
        for i in range(10):
            if i < len(_curriculum):
                topic = _curriculum[i]
                button_updates.append(gr.Button(value=topic, visible=True, interactive=False))
            else:
                button_updates.append(gr.Button(visible=False))
        
        print(Fore.GREEN + f"✓ Loaded new chapter with {len(_curriculum)} topics", Fore.RESET)
        
        # Return updated UI components
        return (checkbox_updates + button_updates + 
                [gr.Accordion(visible=True),  # study_material_section
                 gr.Markdown(value=response),  # study_material_display
                 list(new_unlocked),  # unlocked_topics
                 list(new_expanded),  # expanded_topics
                 list(new_completed),  # completed_topics (reset)
                 gr.Button(visible=False),  # submit_btn (hidden until quiz generated)
                 gr.Button(visible=False, interactive=False)])  # next_chapter_btn (hidden)
        
    except Exception as e:
        print(Fore.RED + f"Error in go_to_next_chapter: {e}", Fore.RESET)
        import traceback
        traceback.print_exc()
        # Return current state unchanged
        return ([gr.update() for _ in range(10)] + [gr.update() for _ in range(10)] + 
                [gr.Accordion(visible=True), gr.Markdown(), unlocked_topics, expanded_topics, completed_topics,
                 gr.Button(visible=False), gr.Button(visible=False)])


def update_button_states(unlocked_topics, expanded_topics, completed_topics, username):
    """Update checkbox and button states based on unlocked, expanded, and completed topics"""
    # Load curriculum from user state
    CURRICULUM = get_curriculum_from_user_state(username)
       
    # Flatten curriculum to get button order
    curriculum = []
    for item in CURRICULUM:
        if isinstance(item, dict):
            curriculum.append(item["topic"])
            for subtopic in item["subtopics"]:
                curriculum.append(f"  ↳ {subtopic}")
        else:
            curriculum.append(item)
    
    # Create checkbox updates (10 max) - all visible
    checkbox_updates = []
    for i in range(10):
        if i < len(curriculum):
            topic = curriculum[i]
            is_checked = topic in completed_topics
            # All checkboxes always visible
            checkbox_updates.append(gr.Checkbox(visible=True, value=is_checked))
        else:
            checkbox_updates.append(gr.Checkbox(visible=False))
    
    # Create button updates (10 max) - all visible, non-interactive
    button_updates = []
    for i in range(10):
        if i < len(curriculum):
            topic = curriculum[i]
            # All buttons always visible but NOT clickable
            button_updates.append(gr.Button(value=topic, visible=True, interactive=False))
        else:
            button_updates.append(gr.Button(visible=False))
    
    return checkbox_updates + button_updates


def check_answers(chapter_name, total_questions, unlocked_topics, expanded_topics, completed_topics, username, *answers):
    """Check answers and update score"""
    # Load curriculum from user 
    global mnt_folder
    save_to=mnt_folder
    
    CURRICULUM = get_curriculum_from_user_state(username)
       
    # Load quiz questions from user state for the current subtopic
    quiz_questions = []
    try:
        u = load_user_state(username)
        if u and "curriculum" in u and len(u["curriculum"]) > 0:
            active_chapter = u["curriculum"][0]["active_chapter"]
            
            # Find the matching subtopic by name
            for subtopic in active_chapter.sub_topics:
                subtopic_text = re.sub(r'^\n?\d+:\s*', '', subtopic.sub_topic.strip()).strip()
                
                # Check if this subtopic matches the chapter_name
                if chapter_name in subtopic_text or subtopic_text in chapter_name:
                    if hasattr(subtopic, 'quizzes') and subtopic.quizzes:
                        quiz_questions = subtopic.quizzes
                        print(Fore.GREEN + f"Loaded {len(quiz_questions)} quizzes for grading", Fore.RESET)
                        break
    except Exception as e:
        print(Fore.RED + f"Error loading quiz questions: {e}", Fore.RESET)
    
    # Fallback to sample if no questions found
    if not quiz_questions:
        print(Fore.YELLOW + f"No quiz questions found for '{chapter_name}', using sample", Fore.RESET)
        quiz_questions = [
            {
                "question": f"Sample question for {chapter_name}?",
                "choices": ["(A) Choice A", "(B) Choice B", "(C) Choice C", "(D) Choice D"],
                "answer": "A",
                "citations": []
            }
        ]
    
    correct_count = 0
    explanations_visibility = []
    
    for i, q in enumerate(quiz_questions):
        user_answer = answers[i] if i < len(answers) else None
        correct_answer = q["answer"]  # This is just "A", "B", "C", or "D"
        
        # Extract the letter from user's choice (e.g., "(A) Text" -> "A")
        user_answer_letter = None
        if user_answer:
            match = re.match(r'\(([A-D])\)', user_answer)
            if match:
                user_answer_letter = match.group(1)
        
        if user_answer_letter and user_answer_letter == correct_answer:
            correct_count += 1
            
        # Always show explanation after submission
        explanations_visibility.append(gr.Markdown(visible=True))
    
    # Hide remaining explanations
    for i in range(len(quiz_questions), 10):
        explanations_visibility.append(gr.Markdown(visible=False))
    
    score_text = f"{correct_count}/{total_questions}"
    
    # Check if user passed (need all questions correct to unlock next)
    passed = correct_count == total_questions
    
    # Update unlocked and completed topics if passed
    new_unlocked_topics = set(unlocked_topics)
    new_completed_topics = set(completed_topics)
    print(Fore.MAGENTA + " score_text =\n", score_text, "\n passed =", passed , "\n new_unlocked_topics=", new_unlocked_topics, Fore.RESET)
    if passed:
        # Mark this topic as completed
        new_completed_topics.add(chapter_name)
        
        # Check if there are more chapters to study by loading user state
        user_state = load_user_state(username)
        has_next_chapter = False
        
        if user_state and "curriculum" in user_state and len(user_state["curriculum"]) > 0:
            curriculum_data = user_state["curriculum"][0]
            next_chapter = curriculum_data.get("next_chapter")
            # next_chapter is None when there are no more chapters
            has_next_chapter = next_chapter is not None
        
        ## if pass and there are more chapters, then generate & build the next chapter
        if has_next_chapter:
            new_user_state = asyncio.run(move_to_next_chapter(username, save_to))
            print(Fore.LIGHTGREEN_EX + f"✓ Moving to next chapter..." + Fore.RESET)
        else:
            print(Fore.GREEN + "🎉 Congratulations! All chapters and subtopics have been completed!" + Fore.RESET)
        
        # Find the next subtopic to unlock
        curriculum = []
        for item in CURRICULUM:
            if isinstance(item, dict):
                curriculum.append(item["topic"])
                for subtopic in item["subtopics"][:10]:  # Max 10 subtopics
                    curriculum.append(f"  ↳ {subtopic}")
            else:
                curriculum.append(item)
        
        # Find current topic index and unlock next if it's a subtopic
        current_full_name = f"  ↳ {chapter_name}" if not chapter_name in curriculum else chapter_name
        try:
            current_idx = curriculum.index(current_full_name)
            # Check if there's a next item and it's a subtopic in the same group
            if current_idx + 1 < len(curriculum):
                next_topic = curriculum[current_idx + 1]
                if next_topic.startswith("  ↳ "):
                    new_unlocked_topics.add(next_topic)
                print(Fore.MAGENTA + " current_full_name =\n", current_full_name, "\n next_topic =", next_topic , "\n new_unlocked_topics=", new_unlocked_topics, "\nnew_completed_topics", new_completed_topics, Fore.RESET)
        except ValueError:
            pass
        
        # Check if all subtopics under a main topic are completed
        for item in CURRICULUM:
            if isinstance(item, dict):
                main_topic = item["topic"]
                all_subtopics_completed = all(
                    subtopic in new_completed_topics
                    for subtopic in item["subtopics"][:10]  # Max 10 subtopics
                )
                if all_subtopics_completed:
                    new_completed_topics.add(main_topic)
    
    # Update button states (maintaining expanded and completed states)
    button_updates = update_button_states(new_unlocked_topics, expanded_topics, new_completed_topics, username)
    
    # Keep submit button visible, enable Next Chapter button only if passed
    submit_btn_update = gr.Button(visible=True)
    next_chapter_btn_update = gr.Button(visible=True, interactive=passed)
    
    return [gr.Textbox(value=score_text, visible=True)] + explanations_visibility + button_updates + [list(new_unlocked_topics)] + [expanded_topics] + [list(new_completed_topics)] + [submit_btn_update, next_chapter_btn_update]


# Note: go_to_next_chapter removed - users now manually check boxes to mark completion


def send_message(message, history, buddy_pref, username):
    """Handle chat messages with study buddy using AI-powered responses with memory"""
    if not message.strip():
        return "", history, None, None, None
    
    # Initialize calendar data (will be populated if calendar route is taken)
    calendar_file_path = None
    calendar_status_msg = None
    calendar_preview_text = None
    
    # Get or create memory ops for this user with rate limiting
    try:
        # Use rate_limit_delay to avoid hitting API limits (default 2.0s between LLM calls)
        # Increase to 3.0 or 5.0 if you frequently hit rate limits
        memory_ops = get_memory_ops(username, rate_limit_delay=2.0)
        print(Fore.CYAN + f"✓ Memory system active for user: {username}", Fore.RESET)
    except Exception as e:
        print(Fore.YELLOW + f"Memory system unavailable: {e}. Continuing without memory.", Fore.RESET)
        memory_ops = None
    
    # ============= QUERY ROUTING =================
    # Load user state to get current context and extract chapter info for routing
    chapter_name_for_routing = None
    sub_topic_for_routing = None
    
    try:
        user_state = load_user_state(username)
        if user_state and "curriculum" in user_state and len(user_state["curriculum"]) > 0:
            # Extract context from user state
            curriculum = user_state["curriculum"][0]
            active_chapter = curriculum.get("active_chapter")
            
            if active_chapter:
                # Get chapter name
                if isinstance(active_chapter, dict):
                    chapter_name_for_routing = active_chapter.get("name", "Unknown Chapter")
                    sub_topics = active_chapter.get("sub_topics", [])
                else:
                    chapter_name_for_routing = active_chapter.name if hasattr(active_chapter, 'name') else "Unknown Chapter"
                    sub_topics = active_chapter.sub_topics if hasattr(active_chapter, 'sub_topics') else []
                
                # Get first subtopic (or could track current active subtopic)
                if sub_topics and len(sub_topics) > 0:
                    first_subtopic = sub_topics[0]
                    if isinstance(first_subtopic, dict):
                        sub_topic_for_routing = first_subtopic.get("sub_topic", "Unknown Sub-topic")
                    else:
                        sub_topic_for_routing = first_subtopic.sub_topic if hasattr(first_subtopic, 'sub_topic') else "Unknown Sub-topic"
    except Exception as e:
        print(Fore.YELLOW + f"⚠️  Failed to load study context for routing: {e}" + Fore.RESET)
    
    # Convert history to chat history format for routing
    chat_history_str = ""
    if history:
        for msg in history[-6:]:  # Last 3 exchanges (6 messages)
            role = msg.get("role", "user")
            content = msg.get("content", "")
            chat_history_str += f"{role}: {content}\n"
    
    # Route the query to determine intent with chapter context
    try:
        print(Fore.CYAN + f"🔀 Routing query: '{message[:50]}...'" + Fore.RESET)
        route_classification = query_routing(
            message, 
            chat_history_str,
            chapter_name=chapter_name_for_routing,
            sub_topic=sub_topic_for_routing
        ).strip().lower()
        print(Fore.CYAN + f"✓ Query classified as: {route_classification}" + Fore.RESET)
    except Exception as e:
        print(Fore.YELLOW + f"⚠️  Routing failed: {e}. Defaulting to study_material." + Fore.RESET)
        route_classification = "study_material"
    
    # Load user state to get current context
    try:
        user_state = load_user_state(username)
        if not user_state or "curriculum" not in user_state or len(user_state["curriculum"]) == 0:
            # Fallback to simple response if user state not available
            bot_response = "I'm having trouble loading your study context. Please make sure you've generated a curriculum first."
        else:
            # Extract context from user state
            curriculum = user_state["curriculum"][0]
            active_chapter = curriculum.get("active_chapter")
            next_chapter = curriculum.get("next_chapter")
            
            # Get memory context if available
            memory_context = ""
            history_summary = ""
            if memory_ops:
                try:
                    memory_context = memory_ops.get_memory_context(message)
                    history_summary = memory_ops.get_history_summary()
                    if memory_context:
                        print(Fore.MAGENTA + f"✓ Added memory context to prompt", Fore.RESET)
                    if history_summary:
                        print(Fore.MAGENTA + f"✓ Added conversation summary to prompt", Fore.RESET)
                except Exception as e:
                    print(Fore.YELLOW + f"Error getting memory context: {e}", Fore.RESET)
            
            # ============= ROUTE BASED ON CLASSIFICATION =================
            if "chitchat" in route_classification:
                # Handle chitchat queries with simple, friendly response
                print(Fore.CYAN + "📢 Using chitchat handler..." + Fore.RESET)
                
                # Get user preferences
                user_preference = user_state.get("study_buddy_preference", buddy_pref if buddy_pref else "friendly and supportive")
                study_buddy_name = user_state.get("study_buddy_name", "Study Buddy")
                
                # Get chapter context for brief mention
                if active_chapter:
                    chapter_name = active_chapter.get("name", "your studies") if isinstance(active_chapter, dict) else active_chapter.name
                else:
                    chapter_name = "your studies"
                
                # Simple chitchat prompt
                chitchat_prompt = f"""You are a friendly study assistant named {study_buddy_name}.

Your communication style: {user_preference}

The user is currently studying: {chapter_name}

The user wants to have a casual conversation unrelated to their study material.
Respond in a brief, friendly, and warm manner (1-2 sentences maximum).
Gently guide the conversation back to studying if appropriate.

{chat_history_str}

User message: {message}

Response:"""
                
                response = inference_call(None, chitchat_prompt)
                try:
                    output_d = response.json()
                    bot_response = output_d['choices'][0]["message"]["content"]
                    print(Fore.GREEN + "✓ Chitchat response generated" + Fore.RESET)
                except Exception as exc:
                    print(Fore.RED + f'Chitchat inference failed: {exc}' + Fore.RESET)
                    bot_response = "I'm having trouble processing that right now. Want to get back to studying? 😊"
            
            elif "supplement" in route_classification:
                # Handle supplement requests (external resources, videos, etc.)
                print(Fore.CYAN + "🔗 Using supplement handler with YouTube search..." + Fore.RESET)
                
                # Extract keywords from user query using LLM for better accuracy
                print(Fore.YELLOW + "🤖 Extracting keywords with LLM..." + Fore.RESET)
                keyword_extraction_prompt = f"""Extract the core search keywords from this user request for a YouTube search. 
Return ONLY the essential keywords or topic phrase, nothing else. Remove filler words like "find me", "show me", "video about", etc.

User request: "{message}"

Essential keywords:"""
                
                try:
                    response = inference_call(None, keyword_extraction_prompt)
                    output_d = response.json()
                    search_query = output_d['choices'][0]["message"]["content"].strip()
                    # Remove quotes if LLM added them
                    search_query = search_query.strip('"').strip("'").strip()
                    print(Fore.GREEN + f"✓ Extracted keywords: '{search_query}'" + Fore.RESET)
                except Exception as e:
                    # Fallback to simple extraction if LLM fails
                    print(Fore.YELLOW + f"⚠️  LLM extraction failed, using fallback: {e}" + Fore.RESET)
                    search_query = message.lower()
                    filler_phrases = [
                        "can you find me a video", "can you find a video", "find me a video",
                        "show me a video", "show me videos", "find videos",
                        "can you show me", "show me", "find me",
                        "i want to watch", "i want to see", "i'd like to watch", "i'd like to see",
                        "could you find", "could you show", "please find", "please show",
                        "search for a video", "search for videos", "get me a video",
                        "look for a video", "look for videos",
                        "about", "on", "regarding", "related to", "for"
                    ]
                    for phrase in filler_phrases:
                        search_query = search_query.replace(phrase, " ")
                    search_query = " ".join(search_query.split()).strip()
                    if len(search_query) < 3:
                        search_query = message
                
                # Search YouTube with clean keywords
                print(Fore.YELLOW + f"🔍 Searching YouTube for keywords: '{search_query}'" + Fore.RESET)
                top_video = None
                try:
                    top_video = fetch_most_relevant_youtube_video(search_query, search_limit=15)
                    if top_video:
                        print(Fore.GREEN + f"✓ Found video: {top_video['title']}" + Fore.RESET)
                        print(Fore.GREEN + f"  URL: {top_video['url']}" + Fore.RESET)
                        print(Fore.GREEN + f"  Relevance: {top_video['relevance_score']:.2f}/100" + Fore.RESET)
                except Exception as e:
                    print(Fore.RED + f"YouTube search failed: {e}" + Fore.RESET)
                
                # Return ONLY the video preview with embed
                if top_video:
                    # Extract video ID from URL for embed
                    video_id = top_video.get('video_id', '')
                    
                    # Create embedded video response with minimal text
                    bot_response = f"""**{top_video['title']}**
📺 {top_video['channel']} • {top_video['duration']} • {top_video['views_text']}

<iframe width="560" height="315" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>

[Open in YouTube]({top_video['url']})"""
                    
                    print(Fore.GREEN + f"✓ Video embed created for: {top_video['title']}" + Fore.RESET)
                else:
                    # Fallback if YouTube search fails
                    bot_response = "I couldn't find a relevant video for your request. Try searching YouTube directly, or I can help explain concepts from your study materials. What would you like to know more about?"
                    print(Fore.YELLOW + "⚠️  No video found" + Fore.RESET)
            
            elif "book_calendar" in route_classification or "calendar" in route_classification:
                # Handle calendar booking requests
                print(Fore.CYAN + "📅 Using calendar booking handler..." + Fore.RESET)
                
                try:
                    # Get chapter context to enhance the calendar event
                    chapter_context = ""
                    if active_chapter:
                        if isinstance(active_chapter, dict):
                            chapter_name = active_chapter.get("name", "")
                        else:
                            chapter_name = active_chapter.name if hasattr(active_chapter, 'name') else ""
                        
                        if chapter_name:
                            chapter_context = f" for {chapter_name}"
                    
                    # Enhance message with study context if not already detailed
                    enhanced_message = message
                    if "study" not in message.lower() and chapter_context:
                        # Add study context to generic booking requests
                        enhanced_message = f"{message} (Study session{chapter_context})"
                    
                    print(Fore.YELLOW + f"📅 Creating calendar event: '{enhanced_message}'" + Fore.RESET)
                    
                    # Create the calendar event
                    file_path, status_msg, preview = create_event_with_ai(enhanced_message)
                    
                    # Store calendar data for return
                    calendar_file_path = file_path
                    calendar_status_msg = status_msg
                    calendar_preview_text = preview
                    
                    if file_path:
                        # Success! Generate a friendly response with event details
                        bot_response = f"""✅ **Calendar Event Created!**

{status_msg}

📥 **The .ics file is ready to download in the "📅 Quick Calendar Event" section in the left sidebar!**

💡 Look for the "Download .ics File" button that just appeared above."""
                        print(Fore.GREEN + f"✓ Calendar event created successfully, file: {file_path}" + Fore.RESET)
                    else:
                        # Failed to create event
                        bot_response = f"""I tried to create a calendar event but encountered an issue:

{status_msg}

Would you like to try rephrasing your request? For example:
- "Schedule a study session tomorrow at 3pm for 2 hours"
- "Book time on Friday 15:00-16:00 to study this topic"
- "Create an exam reminder for next Monday at 9am"

Or you can use the **"📅 Quick Calendar Event"** section in the left sidebar!"""
                        print(Fore.YELLOW + f"⚠️  Calendar event creation failed" + Fore.RESET)
                        
                except Exception as e:
                    print(Fore.RED + f"Error in calendar booking: {e}" + Fore.RESET)
                    import traceback
                    traceback.print_exc()
                    bot_response = """I encountered an error while trying to create your calendar event. 

You can try using the **"📅 Quick Calendar Event"** section in the left sidebar to create events directly!"""
            
            else:  # study_material
                # Handle study material queries with full context (existing implementation)
                print(Fore.CYAN + "📚 Using study material handler..." + Fore.RESET)
            
            # Check if user has completed all chapters
            if next_chapter is None and active_chapter and "study_material" in route_classification:
                # User has completed all chapters!
                user_preference = user_state.get("study_buddy_preference", buddy_pref if buddy_pref else "friendly and supportive")
                study_buddy_name = user_state.get("study_buddy_name", "Study Buddy")
                
                # Get the last chapter details for context
                chapter_name = active_chapter.get("name", "Unknown Chapter") if isinstance(active_chapter, dict) else active_chapter.name
                sub_topics = active_chapter.get("sub_topics", []) if isinstance(active_chapter, dict) else active_chapter.sub_topics
                
                # Get last subtopic details for context
                if sub_topics and len(sub_topics) > 0:
                    last_subtopic = sub_topics[-1]
                    sub_topic = last_subtopic.get("sub_topic", "Unknown") if isinstance(last_subtopic, dict) else last_subtopic.sub_topic
                    
                    # Try to get display_markdown first (contains images), fallback to study_material
                    if isinstance(last_subtopic, dict):
                        study_material = last_subtopic.get("display_markdown") or last_subtopic.get("study_material", "No material available.")
                    else:
                        study_material = getattr(last_subtopic, 'display_markdown', None) or getattr(last_subtopic, 'study_material', "No material available.")
                    
                    list_of_quizzes = last_subtopic.get("quizzes", []) if isinstance(last_subtopic, dict) else last_subtopic.quizzes
                else:
                    sub_topic = "General"
                    study_material = "All curriculum completed."
                    list_of_quizzes = []
                
                # Create a special study material context indicating completion
                completion_context = f"""🎉 CURRICULUM COMPLETED! 🎉

You have successfully finished all chapters and subtopics in your study plan! This is an outstanding achievement.

The user has completed their entire curriculum. While answering their question, acknowledge their completion and provide helpful, encouraging responses. You can help them review any topics, clarify concepts, or discuss what they've learned.

Last completed chapter: {chapter_name}
Last completed subtopic: {sub_topic}

Previous study material for reference:
{study_material}

{memory_context}

{history_summary}"""
                
                # Call study buddy with completion context
                bot_response = study_buddy_response(
                    chapter_name=f"✅ All Chapters Completed",
                    sub_topic=f"Review & Discussion",
                    study_material=completion_context,
                    list_of_quizzes=list_of_quizzes,
                    user_input=message,
                    study_buddy_name=study_buddy_name,
                    user_preference=user_preference
                )
                
            elif not active_chapter and "study_material" in route_classification:
                bot_response = "Please select a chapter to start studying first!"
            elif "study_material" in route_classification:
                # Get chapter details
                chapter_name = active_chapter.get("name", "Unknown Chapter") if isinstance(active_chapter, dict) else active_chapter.name
                
                # Get first subtopic (or could be modified to track current subtopic)
                sub_topics = active_chapter.get("sub_topics", []) if isinstance(active_chapter, dict) else active_chapter.sub_topics
                
                if not sub_topics or len(sub_topics) == 0:
                    sub_topic = "General"
                    study_material = "No study material available yet."
                    list_of_quizzes = []
                else:
                    # Get first subtopic details (could be extended to track current active subtopic)
                    first_subtopic = sub_topics[0]
                    sub_topic = first_subtopic.get("sub_topic", "Unknown") if isinstance(first_subtopic, dict) else first_subtopic.sub_topic
                    
                    # Try to get display_markdown first (contains images), fallback to study_material
                    if isinstance(first_subtopic, dict):
                        study_material = first_subtopic.get("display_markdown") or first_subtopic.get("study_material", "No material available.")
                    else:
                        study_material = getattr(first_subtopic, 'display_markdown', None) or getattr(first_subtopic, 'study_material', "No material available.")
                    
                    list_of_quizzes = first_subtopic.get("quizzes", []) if isinstance(first_subtopic, dict) else first_subtopic.quizzes
                
                # Get study buddy preference
                user_preference = user_state.get("study_buddy_preference", buddy_pref if buddy_pref else "friendly and supportive")
                
                # Enhance study material with memory context
                enhanced_study_material = study_material
                if memory_context:
                    enhanced_study_material = f"""{study_material}

---
{memory_context}

{history_summary}"""
                
                # Call the study buddy response function with enhanced context
                bot_response = study_buddy_response(
                    chapter_name=chapter_name,
                    sub_topic=sub_topic,
                    study_material=enhanced_study_material,
                    list_of_quizzes=list_of_quizzes,
                    user_input=message,
                    study_buddy_name="Study Buddy",
                    user_preference=user_preference
                )
        
        # Process message through memory system (with LLM-based fact extraction & routing)
        if memory_ops:
            try:
                # Process message and response through memory asynchronously
                # This will:
                # 1. Extract facts using LLM (with rate limiting)
                # 2. Route to appropriate memory operation (search_memory or no_operation)
                # 3. Save memories to JSON file
                # 4. Summarize conversation every 3 turns
                
                # Get chapter name - active_chapter could be Chapter object or dict
                chapter_name_for_memory = None
                if active_chapter:
                    if isinstance(active_chapter, dict):
                        chapter_name_for_memory = active_chapter.get("name")
                    else:
                        chapter_name_for_memory = active_chapter.name if hasattr(active_chapter, 'name') else None
                
                memory_result = asyncio.run(
                    memory_ops.process_message(
                        message=message,
                        bot_response=bot_response,
                        context={
                            "username": username,
                            "chapter": chapter_name_for_memory,
                        }
                    )
                )
                print(Fore.GREEN + f"✓ Memory processed: {memory_result['turns']} turns, {len(memory_result['memory_items'])} items saved", Fore.RESET)
                print(Fore.CYAN + f"  Memory operation: {memory_result['mem_ops']}", Fore.RESET)
                if memory_result['recalled_memories']:
                    print(Fore.MAGENTA + f"  Recalled {len(memory_result['recalled_memories'])} relevant memories", Fore.RESET)
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "Too Many Requests" in error_msg:
                    print(Fore.YELLOW + f"⚠️  Rate limit encountered during memory processing. Memory will be saved on next message.", Fore.RESET)
                else:
                    print(Fore.RED + f"Error processing memory: {e}", Fore.RESET)
                    import traceback
                    traceback.print_exc()
                
    except Exception as e:
        print(Fore.RED + f"Error in send_message: {e}", Fore.RESET)
        import traceback
        traceback.print_exc()
        bot_response = "I encountered an error while processing your message. Please try again."
    
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": bot_response})
    return "", history, calendar_file_path, calendar_status_msg, calendar_preview_text


def submit_feedback(feedback_text):
    """Handle feedback submission"""
    if not feedback_text or not feedback_text.strip():
        return gr.Textbox(value="", visible=False), ""
    
    # In a real app, you would save this to a database or file
    # For now, we'll just show a success message
    return gr.Textbox(value="✅ Thank you for your feedback! We appreciate your input.", visible=True), ""


def clear_feedback():
    """Clear feedback form"""
    return "", gr.Textbox(value="", visible=False)


def check_quiz_unlock(completed_topics, username):
    """Check if Quiz tab should be unlocked based on completion"""
    # Load curriculum from user state
    CURRICULUM = get_curriculum_from_user_state(username)
        
    # Unlock Quiz tab after the FIRST SUBTOPIC of the FIRST CHAPTER is completed
    # This means any subtopic with "↳" prefix in completed_topics
    
    first_subtopic_complete = False
    completed_set = set(completed_topics)
    
    # Check if any subtopic is completed (subtopics start with "  ↳ ")
    for completed in completed_set:
        if completed.strip().startswith("↳") or "  ↳" in completed:
            first_subtopic_complete = True
            print(Fore.GREEN + f"Quiz unlocked - first subtopic completed: {completed}", Fore.RESET)
            break
    
    # Return visibility updates for lock message and quiz content
    return gr.Markdown(visible=not first_subtopic_complete), gr.Column(visible=first_subtopic_complete)


def submit_username(username):
    """Handle username submission and hide modal"""
    if not username or not username.strip():
        return (
            gr.update(visible=True),  # Keep modal visible
            gr.update(visible=False, value=""),  # Keep username display hidden
            ""  # Empty username state
        )
    
    username = username.strip().lower()  # Lowercase the username for consistency
    username_html = f'<div style="background: #f0f0f0; padding: 8px 15px; border-radius: 15px; font-weight: bold; color: #2c3e50; box-shadow: 0 2px 8px rgba(0,0,0,0.1); display: inline-block; font-size: 14px;">👤 {username}</div>'
    return (
        gr.update(visible=False),  # Hide modal
        gr.update(visible=True, value=username_html),  # Show and display username
        username  # Store username in state (lowercased)
    )