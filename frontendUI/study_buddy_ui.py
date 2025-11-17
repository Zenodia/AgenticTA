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
from config import SAMPLE_CURRICULUM, SAMPLE_QUIZ_DATA, MAX_FILES, MAX_FILE_SIZE_GB, MAX_PAGES_PER_FILE
from utils import validate_pdf_files
import shutil
import yaml
import os
from colorama import Fore
from nemo_retriever_client_utils import delete_collections,fetch_collections, create_collection, upload_files_to_nemo_retriever, get_documents,fetch_rag_context
from nodes import init_user_storage,user_exists,load_user_state,save_user_state, _save_store, _load_store
from nodes import update_and_save_user_state, move_to_next_chapter, update_subtopic_status,add_quiz_to_subtopic, build_next_chapter, run_for_first_time_user
import asyncio
from states import Chapter, StudyPlan, Curriculum, User, GlobalState, Status, SubTopic, printmd
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
f=open("/workspace/docker-compose.yml","r")
yaml_f=yaml.safe_load(f)
global mnt_folder
mnt_folder=yaml_f["services"]["agenticta"]["volumes"][-1].split(":")[-1]

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
        
        # Handle both dict and StudyPlan object
        if isinstance(study_plan, dict) and "study_plan" in study_plan:
            chapters = study_plan["study_plan"]
        elif isinstance(study_plan, StudyPlan):
            chapters = study_plan.study_plan
        else:
            return []
        
        # Convert to SAMPLE_CURRICULUM format
        result = []
        for chapter in chapters:
            # Handle both dict and Chapter object
            if isinstance(chapter, dict):
                chapter_name = chapter.get("name", "")
                sub_topics = chapter.get("sub_topics", [])
            else:
                chapter_name = chapter.name
                sub_topics = chapter.sub_topics
            
            # If chapter has subtopics, create hierarchical structure
            if sub_topics and len(sub_topics) > 0:
                subtopic_names = []
                for st in sub_topics[:10]:  # Max 10 subtopics
                    if isinstance(st, dict):
                        subtopic_names.append(st.get("sub_topic", "").strip())
                    else:
                        subtopic_names.append(st.sub_topic.strip())
                
                result.append({
                    "topic": chapter_name,
                    "subtopics": subtopic_names
                })
            else:
                # Simple chapter without subtopics
                result.append(chapter_name)
        
        return result
    except Exception as e:
        print(Fore.RED + f"Error loading curriculum from user state: {e}", Fore.RESET)
        return []

def generate_curriculum(file_obj, validation_msg , username , preference, study_buddy_name="Ollie"):
    """Generate curriculum from uploaded PDF or use sample data"""
    global mnt_folder  
    pdf_loc = os.path.join(mnt_folder, "pdfs")
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
        if isinstance(study_plan, StudyPlan):
            chapters_ls=[f"{str(chapter.number)}:{chapter.name}" for chapter in study_plan.study_plan]
            curriculum = chapters_ls
        else:
            print(type(study_plan), study_plan)
    else: 
        print(Fore.LIGHTYELLOW_EX + "New user detected, running first time setup..." , Fore.RESET)       
        global_state: GlobalState = asyncio.run(run_for_first_time_user(u, pdf_loc, save_to, preference, store_path, user_store_dir))
        u=load_user_state(username)
        study_plan =u["curriculum"][0]["study_plan"]
        print(type(study_plan), study_plan)
        if isinstance(study_plan, StudyPlan):
            chapters_ls=[f"{str(chapter.number)}:{chapter.name}" for chapter in study_plan.study_plan]
            curriculum = chapters_ls
        else:
            print(type(study_plan), study_plan)
        
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
    active_chapter=u["curriculum"][0]["active_chapter"]
    print(type(active_chapter), active_chapter)

    # Extract subtopics - strip any existing numbering first to avoid duplication
    sub_topics = []
    for subtopic in active_chapter.sub_topics:
        # Get the subtopic text and strip any leading numbering/whitespace
        subtopic_text = subtopic.sub_topic.strip()
        subtopic_text = re.sub(r'^\n?\d+:\s*', '', subtopic_text).strip()
        sub_topics.append(subtopic_text)
    
    print(Fore.CYAN + f"Extracted sub_topics: {sub_topics}", Fore.RESET)
    response = f"""
            ### Chapter {str(active_chapter.number)}: {active_chapter.name}

            #### 1st Study Topic: {active_chapter.sub_topics[0].sub_topic}

            **Study Material:**

            {active_chapter.sub_topics[0].study_material}"""
    curriculum_formatted=[]
    for i, chapter in enumerate(chapters_ls):
        if i==0:
            temp={"topic": chapter,
             "subtopics": sub_topics
            }
            curriculum_formatted.append(temp)
        else:
            curriculum_formatted.append(chapter)

    """
    SAMPLE_CURRICULUM = [
    {
        "topic": "Introduction to Biology",
        "subtopics": [
            "Introduction to Biology - Cell Biology",
            "Introduction to Biology - Genetics",
            "Introduction to Biology - Ecology",
            "Introduction to Biology - Evolution",
            "Introduction to Biology - Human Anatomy"
        ]  # Max 10 subtopics allowed
    },
    "Cell Structure and Function",
    "Genetics and Heredity",
    "Evolution and Natural Selection",
    "Ecology and Ecosystems"
    ]"""


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
    
    # Create chapter buttons (10 max) - hide subtopics initially
    outputs = [gr.Column(visible=True)]
    for i in range(10):
        if i < len(_curriculum):
            button_text = _curriculum[i]
            is_unlocked = button_text in unlocked_topics
            is_subtopic = button_text.startswith("  ↳ ")
            # Hide subtopics initially, show main topics
            print(Fore.YELLOW + f"Button {i}: text='{button_text}', visible={not is_subtopic}, unlocked={is_unlocked}, is_subtopic={is_subtopic}", Fore.RESET)
            outputs.append(gr.Button(button_text, visible=not is_subtopic, interactive=is_unlocked))
        else:
            outputs.append(gr.Button(visible=False))
    
    # Return outputs + unlocked topics + expanded topics + completed topics (all empty initially)
    outputs.append(list(unlocked_topics))
    outputs.append([])  # No topics expanded initially
    outputs.append([])  # No topics completed initially
    return outputs


def handle_file_upload(files, username, progress=gr.Progress()):
    """Handle file upload and validate"""
    if files is None or len(files) == 0:
        return ""
    
    global mnt_folder  

    print(Fore.BLUE + "mnt_folder =", mnt_folder, "username=", username, Fore.RESET)
    pdf_dir = os.path.join(mnt_folder, "pdfs")
    user_name_folder=os.path.join(mnt_folder,username)
    os.makedirs(pdf_dir, exist_ok=True)
    os.makedirs(user_name_folder, exist_ok=True)
    new_ls=[shutil.copy(f, pdf_dir) for f in files]
    # Call create collection method
    
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
            
    nemo_retriever_files_upload_output = asyncio.run(upload_files_to_nemo_retriever(pdf_dir , username,[]))
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


def mark_chapter_complete(chapter_name, expanded_topics, unlocked_topics, completed_topics, username, progress=gr.Progress()):
    """Mark a chapter as complete and prepare quiz"""
    print(Fore.BLUE + f"mark_chapter_complete called with chapter_name='{chapter_name}', username='{username}'", Fore.RESET)
    print(Fore.CYAN + f"expanded_topics={expanded_topics}, unlocked_topics={unlocked_topics}", Fore.RESET)
    
    # Load curriculum from user state
    CURRICULUM = get_curriculum_from_user_state(username)
    print(Fore.MAGENTA + f"Loaded CURRICULUM: {CURRICULUM}", Fore.RESET)
    
    if not CURRICULUM:
        print(Fore.YELLOW + "No curriculum loaded, using SAMPLE_CURRICULUM", Fore.RESET)
        CURRICULUM = SAMPLE_CURRICULUM
    
    # Strip numbering from chapter_name (e.g., "0:Sweden: Key Facts" -> "Sweden: Key Facts")
    chapter_name_stripped = re.sub(r'^\d+:', '', chapter_name).strip()
    print(Fore.YELLOW + f"Stripped chapter_name: '{chapter_name}' -> '{chapter_name_stripped}'", Fore.RESET)
    
    # Check if this is a main topic with subtopics
    has_subtopics = False
    for item in CURRICULUM:
        if isinstance(item, dict):
            # Also strip numbering from topic for comparison
            topic_stripped = re.sub(r'^\d+:', '', item['topic']).strip()
            print(Fore.GREEN + f"Checking if '{topic_stripped}' == '{chapter_name_stripped}'", Fore.RESET)
            if topic_stripped == chapter_name_stripped or item["topic"] == chapter_name:
                has_subtopics = True
                print(Fore.GREEN + f"Found match! has_subtopics=True", Fore.RESET)
                break
    
    # If it's a main topic with subtopics, toggle subtopics visibility and return
    if has_subtopics:
        # Toggle expanded state
        new_expanded = set(expanded_topics)
        if chapter_name in new_expanded:
            new_expanded.remove(chapter_name)
        else:
            new_expanded.add(chapter_name)
        
        # Update button visibility but don't open quiz
        curriculum = []
        for item in CURRICULUM:
            if isinstance(item, dict):
                curriculum.append(item["topic"])
                for subtopic in item["subtopics"][:10]:  # Max 10 subtopics
                    curriculum.append(f"  ↳ {subtopic}")
            else:
                curriculum.append(item)
        
        button_updates = []
        for i in range(10):
            if i < len(curriculum):
                topic = curriculum[i]
                is_subtopic = topic.startswith("  ↳ ")
                
                if is_subtopic:
                    # Find parent topic
                    parent_topic = None
                    for j in range(i-1, -1, -1):
                        if not curriculum[j].startswith("  ↳ "):
                            parent_topic = curriculum[j]
                            break
                    # Show subtopic only if parent is expanded
                    is_visible = parent_topic in new_expanded
                else:
                    # Main topics are always visible
                    is_visible = True
                
                is_unlocked = topic in unlocked_topics
                is_completed = topic in completed_topics or topic.replace("  ↳ ", "") in completed_topics
                
                # Add CSS class for completed topics
                elem_class = ["chapter-btn"]
                if is_completed:
                    elem_class.append("completed-topic")
                if is_subtopic:
                    elem_class.append("subtopic-btn")
                
                button_updates.append(gr.Button(visible=is_visible, interactive=is_unlocked, elem_classes=elem_class))
            else:
                button_updates.append(gr.Button(visible=False))
        
        # Create empty quiz components (keep quiz hidden)
        quiz_components = []
        for _ in range(10):
            quiz_components.append(gr.Radio(visible=False))
            quiz_components.append(gr.Markdown(visible=False))
        
        # Return all expected outputs (don't open quiz, just toggle subtopics)
        return (
            [gr.Accordion(visible=False),  # Keep quiz hidden
             gr.Textbox(visible=False),  # Keep score hidden
             "",  # current_chapter (empty)
             0]  # total_questions (0)
            + quiz_components  # 20 components (10 radio + 10 markdown)
            + button_updates  # 10 buttons
            + [list(new_expanded),  # expanded_topics_state
               completed_topics,  # completed_topics_state (unchanged)
               gr.Button(visible=False),  # Submit button (hidden when no quiz)
               gr.Button(visible=False)]  # Next Chapter button (hidden when no quiz)
        )
    
    progress(0.3, desc="Preparing quiz...")
    
    # Remove indentation prefix if present
    actual_chapter_name = chapter_name.replace("  ↳ ", "") if "  ↳ " in chapter_name else chapter_name
    
    # Get quiz data for the chapter - handle hierarchical structure
    quiz_data = SAMPLE_QUIZ_DATA.get(actual_chapter_name, None)
    
    # Determine if this is a main topic with subtopics, a subtopic, or a simple topic
    if isinstance(quiz_data, dict) and "questions" in quiz_data:
        # This is a main topic with subtopics, use the main topic questions
        quiz_questions = quiz_data["questions"]
    elif isinstance(quiz_data, list):
        # This is a simple topic with direct question list
        quiz_questions = quiz_data
    else:
        # Try to find it as a subtopic under its parent
        quiz_questions = []
        for topic, data in SAMPLE_QUIZ_DATA.items():
            if isinstance(data, dict) and "subtopics" in data:
                if actual_chapter_name in data["subtopics"]:
                    quiz_questions = data["subtopics"][actual_chapter_name]
                    break
    
    if not quiz_questions:
        # Generate fake questions if none exist
        quiz_questions = [
            {
                "question": f"Sample question for {chapter_name}?",
                "choices": ["Choice A", "Choice B", "Choice C", "Choice D", "Choice E"],
                "answer": "Choice A",
                "explanation": "This is a sample explanation for the question."
            }
        ]
    
    # Create quiz components (max 10 questions)
    quiz_components = []
    for i in range(10):
        if i < len(quiz_questions):
            q = quiz_questions[i]
            radio = gr.Radio(
                choices=q["choices"],
                label=f"Q{i+1}: {q['question']}",
                interactive=True,
                visible=True,
                value=None  # Reset value to None for new quiz
            )
            explanation = gr.Markdown(f"**Explanation:** {q['explanation']}", visible=False)
        else:
            radio = gr.Radio(visible=False, value=None)
            explanation = gr.Markdown(visible=False)
        quiz_components.extend([radio, explanation])
    
    total_questions = len(quiz_questions)
    counter_text = f"0/{total_questions}"
    
    # Generate button updates to maintain current state
    curriculum = []
    for item in CURRICULUM:
        if isinstance(item, dict):
            curriculum.append(item["topic"])
            for subtopic in item["subtopics"]:
                curriculum.append(f"  ↳ {subtopic}")
        else:
            curriculum.append(item)
    
    button_updates = []
    for i in range(10):
        if i < len(curriculum):
            topic = curriculum[i]
            is_subtopic = topic.startswith("  ↳ ")
            
            if is_subtopic:
                # Find parent topic
                parent_topic = None
                for j in range(i-1, -1, -1):
                    if not curriculum[j].startswith("  ↳ "):
                        parent_topic = curriculum[j]
                        break
                # Show subtopic only if parent is expanded
                is_visible = parent_topic in expanded_topics
            else:
                # Main topics are always visible
                is_visible = True
            
            is_unlocked = topic in unlocked_topics
            is_completed = topic in completed_topics or topic.replace("  ↳ ", "") in completed_topics
            
            # Add CSS class for completed topics
            elem_class = ["chapter-btn"]
            if is_completed:
                elem_class.append("completed-topic")
            if is_subtopic:
                elem_class.append("subtopic-btn")
            
            button_updates.append(gr.Button(visible=is_visible, interactive=is_unlocked, elem_classes=elem_class))
        else:
            button_updates.append(gr.Button(visible=False))
    
    return (
        [gr.Accordion(visible=True),
         gr.Textbox(value=counter_text, visible=True),
         actual_chapter_name,  # Current chapter name (without prefix)
         total_questions]  # Total questions
        + quiz_components
        + button_updates
        + [expanded_topics,  # Maintain expanded state
           completed_topics,  # Maintain completed state
           gr.Button(visible=True),  # Submit button (visible when quiz loads)
           gr.Button(visible=True, interactive=False)]  # Next Chapter button (visible but disabled initially)
    )


def update_button_states(unlocked_topics, expanded_topics, completed_topics, username):
    """Update button interactive states and visibility based on unlocked, expanded, and completed topics"""
    # Load curriculum from user state
    CURRICULUM = get_curriculum_from_user_state(username)
    if not CURRICULUM:
        CURRICULUM = SAMPLE_CURRICULUM
    
    # Flatten curriculum to get button order
    curriculum = []
    for item in CURRICULUM:
        if isinstance(item, dict):
            curriculum.append(item["topic"])
            for subtopic in item["subtopics"]:
                curriculum.append(f"  ↳ {subtopic}")
        else:
            curriculum.append(item)
    
    # Create button updates (10 max)
    button_updates = []
    for i in range(10):
        if i < len(curriculum):
            topic = curriculum[i]
            is_subtopic = topic.startswith("  ↳ ")
            
            if is_subtopic:
                # Find parent topic
                parent_topic = None
                for j in range(i-1, -1, -1):
                    if not curriculum[j].startswith("  ↳ "):
                        parent_topic = curriculum[j]
                        break
                # Show subtopic only if parent is expanded
                is_visible = parent_topic in expanded_topics
            else:
                # Main topics are always visible
                is_visible = True
            
            is_unlocked = topic in unlocked_topics
            is_completed = topic in completed_topics or topic.replace("  ↳ ", "") in completed_topics
            
            # Add CSS class for completed topics
            elem_class = ["chapter-btn"]
            if is_completed:
                elem_class.append("completed-topic")
            if is_subtopic:
                elem_class.append("subtopic-btn")
            
            button_updates.append(gr.Button(visible=is_visible, interactive=is_unlocked, elem_classes=elem_class))
        else:
            button_updates.append(gr.Button())
    
    return button_updates


def check_answers(chapter_name, total_questions, unlocked_topics, expanded_topics, completed_topics, username, *answers):
    """Check answers and update score"""
    # Load curriculum from user state
    CURRICULUM = get_curriculum_from_user_state(username)
    if not CURRICULUM:
        CURRICULUM = SAMPLE_CURRICULUM
    
    # Get quiz data for the chapter - handle hierarchical structure
    quiz_data = SAMPLE_QUIZ_DATA.get(chapter_name, None)
    
    # Determine if this is a main topic with subtopics, a subtopic, or a simple topic
    if isinstance(quiz_data, dict) and "questions" in quiz_data:
        # This is a main topic with subtopics, use the main topic questions
        quiz_questions = quiz_data["questions"]
    elif isinstance(quiz_data, list):
        # This is a simple topic with direct question list
        quiz_questions = quiz_data
    else:
        # Try to find it as a subtopic under its parent
        quiz_questions = []
        for topic, data in SAMPLE_QUIZ_DATA.items():
            if isinstance(data, dict) and "subtopics" in data:
                if chapter_name in data["subtopics"]:
                    quiz_questions = data["subtopics"][chapter_name]
                    break
    
    if not quiz_questions:
        quiz_questions = [
            {
                "question": f"Sample question for {chapter_name}?",
                "choices": ["Choice A", "Choice B", "Choice C", "Choice D", "Choice E"],
                "answer": "Choice A",
                "explanation": "This is a sample explanation for the question."
            }
        ]
    
    correct_count = 0
    explanations_visibility = []
    
    for i, q in enumerate(quiz_questions):
        user_answer = answers[i] if i < len(answers) else None
        correct_answer = q["answer"]
        
        if user_answer == correct_answer:
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
    
    if passed:
        # Mark this topic as completed
        new_completed_topics.add(chapter_name)
        
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


def go_to_next_chapter(current_chapter, unlocked_topics, expanded_topics, completed_topics, username):
    """Navigate to the next unlocked chapter"""
    # Load curriculum from user state
    CURRICULUM = get_curriculum_from_user_state(username)
    if not CURRICULUM:
        CURRICULUM = SAMPLE_CURRICULUM
    
    # Flatten curriculum to get chapter order
    curriculum = []
    for item in CURRICULUM:
        if isinstance(item, dict):
            curriculum.append(item["topic"])
            for subtopic in item["subtopics"]:
                curriculum.append(f"  ↳ {subtopic}")
        else:
            curriculum.append(item)
    
    # Find current chapter and get next unlocked one
    current_full_name = f"  ↳ {current_chapter}" if f"  ↳ {current_chapter}" in curriculum else current_chapter
    try:
        current_idx = curriculum.index(current_full_name)
        # Find next unlocked topic
        for i in range(current_idx + 1, len(curriculum)):
            next_topic = curriculum[i]
            if next_topic in unlocked_topics or not next_topic.startswith("  ↳ "):
                # Found next unlocked topic, open it
                return mark_chapter_complete(next_topic, expanded_topics, unlocked_topics, completed_topics, username)
    except (ValueError, IndexError):
        pass
    
    # If no next chapter found, return current state unchanged
    return mark_chapter_complete(current_chapter, expanded_topics, unlocked_topics, completed_topics, username)


def send_message(message, history, buddy_pref):
    """Handle chat messages with study buddy"""
    if not message.strip():
        return "", history
    
    # Simple response logic based on user preference
    responses = [
        f"I understand you prefer a {buddy_pref.lower() if buddy_pref else 'helpful'} study buddy!",
        "That's a great point! Let me help clarify that concept.",
        "I found some additional resources on that topic for you.",
        "Would you like me to explain that in a different way?",
        "That's an excellent question! Here's what I know about it..."
    ]
    
    bot_response = random.choice(responses)
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": bot_response})
    return "", history


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
    if not CURRICULUM:
        CURRICULUM = SAMPLE_CURRICULUM
    
    # Unlock Quiz tab only if a FULL topic is completed
    # A full topic is either:
    # 1. A topic without subtopics (like "Cell Structure and Function")
    # 2. A main topic whose all subtopics are completed (like "Introduction to Biology")
    
    full_topic_complete = False
    completed_set = set(completed_topics)
    
    for item in CURRICULUM:
        if isinstance(item, dict):
            # This is a main topic with subtopics
            # Check if the main topic itself is in completed (meaning all subtopics done)
            if item["topic"] in completed_set:
                full_topic_complete = True
                break
        else:
            # This is a simple topic without subtopics
            if item in completed_set:
                full_topic_complete = True
                break
    
    # Return visibility updates for lock message and quiz content
    return gr.Markdown(visible=not full_topic_complete), gr.Column(visible=full_topic_complete)


def submit_username(username):
    """Handle username submission and hide modal"""
    if not username or not username.strip():
        return (
            gr.update(visible=True),  # Keep modal visible
            gr.update(visible=False, value=""),  # Keep username display hidden
            ""  # Empty username state
        )
    
    username = username.strip()
    username_html = f'<div style="background: #f0f0f0; padding: 8px 15px; border-radius: 15px; font-weight: bold; color: #2c3e50; box-shadow: 0 2px 8px rgba(0,0,0,0.1); display: inline-block; font-size: 14px;">👤 {username}</div>'
    return (
        gr.update(visible=False),  # Hide modal
        gr.update(visible=True, value=username_html),  # Show and display username
        username  # Store username in state
    )

