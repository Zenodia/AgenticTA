"""A lightweight orchestrator that builds LangGraph-like nodes to populate
the application's state objects defined in `states.py` using helper clients.

This file provides a minimal runtime-friendly shim for composing nodes (steps)
that can be wired together. It uses `helper.run_together` to call the MCP
clients (quiz generation, study buddy, agentic memory) and then constructs
`Chapter`, `StudyPlan`, `Curriculum`, `User`, and `GlobalState` objects.

The orchestrator exposes a `run_for_first_time_user(user, uploaded_pdf_loc, save_to, study_buddy_preference)` 
function that will initialize per-user storage paths, check for an existing user 
(in a local JSON store), create/populate state objects for first-time users, 
and return the final GlobalState instance.

Per-User Storage Structure:
    save_to/
    └── user_id/
        ├── global_state.json      # GlobalState for this user
        └── user_store/             # Per-user storage files
            └── user_id.json        # User profile with Curriculum > StudyPlan > Chapter > SubTopic

Example:
    /workspace/mnt/
    └── babe/
        ├── global_state.json
        └── user_store/
            └── babe.json

User State Update Functions:
    This module provides several functions to load, update, and save user states:
    
    1. update_and_save_user_state(user_id, save_to, update_fn)
       - Generic function that accepts a callback for custom updates
       - Loads user state, applies updates, saves back to disk
       
    2. move_to_next_chapter(user_id, save_to)
       - Marks current chapter as COMPLETED
       - Moves to next chapter and sets it as STARTED
       - Updates study plan accordingly
       
    3. update_subtopic_status(user_id, save_to, subtopic_number, new_status, feedback)
       - Updates a specific subtopic's status
       - Optionally adds feedback
       
    4. add_quiz_to_subtopic(user_id, save_to, subtopic_number, quiz)
       - Adds a quiz to a specific subtopic

Troubleshooting:
    If you encounter JSON parsing errors when loading user state:
    1. The saved state file may be corrupted or from an older version
    2. Delete the user directory: rm -rf {save_to}/{user_id}/
    3. Re-run run_for_first_time_user to recreate the state
    
    Example:
        # If getting JSON errors for user 'babe'
        rm -rf /workspace/mnt/babe/
        # Then re-run the initialization
       
Usage Examples:
    # Move to next chapter (async)
    updated_state = await move_to_next_chapter("babe", "/workspace/mnt/")
    # Or from synchronous context:
    updated_state = asyncio.run(move_to_next_chapter("babe", "/workspace/mnt/"))
    
    # Update subtopic status with feedback (async)
    updated_state = await update_subtopic_status(
        "babe", "/workspace/mnt/", 
        subtopic_number=0,
        new_status=Status.COMPLETED,
        feedback=["Great work!", "All tests passed"]
    )
    
    # Add a quiz (async)
    quiz = {
        "question": "What is X?",
        "choices": ["A", "B", "C"],
        "answer": "A",
        "explanation": "Because..."
    }
    updated_state = await add_quiz_to_subtopic("babe", "/workspace/mnt/", 0, quiz)
    
    # Custom update (async)
    async def my_update(user_state):
        curriculum_list = user_state.get("curriculum")  # curriculum is List[Curriculum]
        if curriculum_list and isinstance(curriculum_list, list) and len(curriculum_list) > 0:
            curriculum = curriculum_list[0]  # Get first curriculum
            active_ch = curriculum.get("active_chapter")
            # ... custom logic ...
        return user_state
    
    updated_state = await update_and_save_user_state("babe", "/workspace/mnt/", my_update)
"""
from __future__ import annotations
from study_buddy_client import study_buddy_client_requests
from agent_mem_client import agentic_mem_mcp_client
from quiz_gen_client import quiz_generation_client
import json
import os
import typing
from pathlib import Path
import pandas as pd
from dataclasses import asdict, dataclass
from colorama import Fore
from helper import run_together
from chapter_gen_from_file_names import chapter_gen_from_pdfs, parse_output_from_chapters
from states import Chapter, StudyPlan, Curriculum, User, GlobalState, Status, SubTopic
from states import save_user_to_file, load_user_from_file
from states import convert_to_json_safe
from study_material_gen_agent import study_material_gen, printmd
from extract_sub_chapters import parallel_extract_pdf_page_and_text, post_process_extract_sub_chapters
import asyncio
import concurrent

# Local simple storage for users (JSON file) - will be initialized per user
STORE_PATH = None
USER_STORE_DIR = None

def init_user_storage(save_to: str, user_id: str):
    """Initialize per-user storage paths based on save_to and user_id.
    
    Args:
        save_to: Base directory for storing user data
        user_id: Unique user identifier
        
    This creates a directory structure like:
        save_to/user_id/global_state.json
        save_to/user_id/user_store/
    """
    global STORE_PATH, USER_STORE_DIR
    
    # Create per-user base directory
    user_base_dir = Path(save_to) / user_id
    user_base_dir.mkdir(parents=True, exist_ok=True)
    
    # Store path for global state JSON
    STORE_PATH = user_base_dir / "global_state.json"
    
    # Directory for per-user storage files
    USER_STORE_DIR = user_base_dir / "user_store"
    USER_STORE_DIR.mkdir(parents=True, exist_ok=True)
    
    return STORE_PATH, USER_STORE_DIR

# global placeholders populated by `call_helper_clients_for_user`
# ensure these exist at module import time so other async functions can reference them
quiz_gen_output_files_loc: list[str] = []
quiz_gen_tasks_ls: list[str] = []
pdf_files: list[str] = []
quiz_csv_locations: list[str] = []

def _store_file_path() -> Path:
    """Return a safe file path for the central store.

    If `STORE_PATH` is a directory (e.g., mistakenly created as one), use
    a file named `store.json` inside it. Ensure parent directories exist.
    """
    p = STORE_PATH
    if p.exists() and p.is_dir():
        filep = p / "store.json"
        filep.parent.mkdir(parents=True, exist_ok=True)
        return filep
    # ensure parent directory exists for the file
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_store() -> dict:
    filep = _store_file_path()
    if filep.exists():
        try:
            return json.loads(filep.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_store(data: dict):
    filep = _store_file_path()
    # ensure the stored data is JSON-serializable (convert Pydantic models, Enums, etc.)
    try:
        safe_data = convert_to_json_safe(data)
    except Exception:
        # fallback: attempt to write raw data (this will raise if not serializable)
        safe_data = data
    filep.write_text(json.dumps(safe_data, indent=2, ensure_ascii=False), encoding="utf-8")


def user_exists(user_id: str) -> bool:

    # First check per-user file store (created via save_user_to_file)
    user_file = USER_STORE_DIR / f"{user_id}.json"
    if user_file.exists():
        return True
    store = _load_store()
    return user_id in store.get("users", {})


def create_user_minimal(user: User) -> User:
    # Accept either a mapping-like User or a Pydantic/Typed object
    if isinstance(user, dict):
        uid = user.get("user_id")
        pref = user.get("study_buddy_preference")
        persona = user.get("study_buddy_persona")
        name = user.get("study_buddy_name")
    else:
        uid = getattr(user, "user_id", None)
        pref = getattr(user, "study_buddy_preference", None)
        persona = getattr(user, "study_buddy_persona", None)
        name = getattr(user, "study_buddy_name", None)

    minimal = {
        "user_id": uid,
        "study_buddy_preference": pref,
        "study_buddy_persona": persona,
        "study_buddy_name": name,
        "curriculum": None,
    }

    # Save per-user file
    save_user_to_file(minimal, str(USER_STORE_DIR / f"{uid}.json"))

    # Also register in central store for quick lookups
    store = _load_store()
    users = store.setdefault("users", {})
    users[uid] = minimal
    _save_store(store)
    return minimal


def save_user_state(user_id: str, user_obj: User):
    """Save user state to disk with proper serialization of Pydantic models.
    
    This function mirrors save_user_to_file from states.py by:
    - Converting Pydantic BaseModel instances (Chapter, SubTopic, StudyPlan) to JSON-safe dicts
    - Converting Status Enum values to their string representations
    - Preserving the structure for later reconstruction
    
    Args:
        user_id: The user identifier
        user_obj: User TypedDict that may contain Pydantic models (Chapter, StudyPlan, etc.)
    
    Storage locations:
        - Per-user file: {USER_STORE_DIR}/{user_id}.json (primary storage)
        - Central store: {STORE_PATH} (convenience index)
    """
    # Persist per-user JSON using states.save_user_to_file for Pydantic-aware serialization
    user_file_path = str(USER_STORE_DIR / f"{user_id}.json")
    save_user_to_file(user_obj, user_file_path)
    print(f"Saved user state to {user_file_path}")
    
    # Keep central store in sync as a convenience index
    # Convert to JSON-safe format for central storage
    store = _load_store()
    users = store.setdefault("users", {})
    users[user_id] = convert_to_json_safe(user_obj)
    _save_store(store)
    print(f"Updated central store index for user {user_id}")


def load_user_state(user_id: str) -> User:
    """Load user state from disk and reconstruct Python classes.
    
    This function mirrors load_user_from_file from states.py by:
    - Loading JSON data from disk
    - Reconstructing SubTopic as BaseModel with Status enum
    - Reconstructing Chapter as BaseModel with Status enum and SubTopic list
    - Reconstructing StudyPlan as BaseModel containing Chapter list
    - Reconstructing Curriculum as TypedDict containing properly typed objects
    - Reconstructing User with curriculum as List[Curriculum]
    
    Args:
        user_id: The user identifier
        
    Returns:
        User TypedDict with properly reconstructed Pydantic models and Enums
        
    Raises:
        json.JSONDecodeError: If the user state file is corrupted
        
    Note:
        If the per-user file doesn't exist, falls back to central store.
        The fallback also properly reconstructs objects using load_user_from_file
        to ensure type consistency.
    """
    user_file = USER_STORE_DIR / f"{user_id}.json"
    
    # Primary path: Load from per-user file with proper reconstruction
    if user_file.exists():
        try:
            print(f"Loading user state from {user_file}")
            user_state = load_user_from_file(str(user_file))
            print(f"Successfully loaded and reconstructed user state for {user_id}")
            _verify_reconstruction(user_state, user_id)
            return user_state
        except json.JSONDecodeError as e:
            print(f"ERROR: JSON decode error loading user state from {user_file}: {e}")
            print(f"The file may be corrupted. Consider deleting the user directory:")
            print(f"  rm -rf {USER_STORE_DIR.parent}")
            print(f"Then re-run initialization for user '{user_id}'")
            raise
        except Exception as e:
            print(f"ERROR: Unexpected error loading user state: {e}")
            raise
    
    # Fallback path: Load from central store and reconstruct
    print(f"Per-user file not found for {user_id}, checking central store...")
    central_data = _load_store().get("users", {}).get(user_id)
    
    if central_data:
        # Save to per-user file for next time, then reload with proper reconstruction
        print(f"Found user {user_id} in central store, migrating to per-user file...")
        temp_file = USER_STORE_DIR / f"{user_id}_temp.json"
        save_user_to_file(central_data, str(temp_file))
        
        # Now load back with proper reconstruction
        reconstructed = load_user_from_file(str(temp_file))
        
        # Replace temp file with permanent file
        temp_file.replace(user_file)
        print(f"Migrated and reconstructed user state for {user_id}")
        _verify_reconstruction(reconstructed, user_id)
        return reconstructed
    
    print(f"WARNING: User {user_id} not found in any storage location")
    return None


def _verify_reconstruction(user_state: User, user_id: str):
    """Verify that loaded user state has properly reconstructed Python classes.
    
    This is a helper function to ensure that:
    - StudyPlan is a BaseModel instance (not a dict)
    - Chapter objects are BaseModel instances (not dicts)
    - SubTopic objects are BaseModel instances (not dicts)
    - Status values are Enum instances (not strings)
    """
    if not user_state:
        return
    
    try:
        curriculum_list = user_state.get("curriculum")
        if curriculum_list and isinstance(curriculum_list, list) and len(curriculum_list) > 0:
            curr = curriculum_list[0]
            
            # Verify StudyPlan reconstruction
            study_plan = curr.get("study_plan")
            if study_plan:
                from states import StudyPlan, Chapter, SubTopic
                is_study_plan = isinstance(study_plan, StudyPlan)
                print(f"  ✓ StudyPlan reconstructed: {is_study_plan} (type: {type(study_plan).__name__})")
                
                # Verify Chapter reconstruction
                if hasattr(study_plan, 'study_plan') and study_plan.study_plan:
                    first_chapter = study_plan.study_plan[0]
                    is_chapter = isinstance(first_chapter, Chapter)
                    print(f"  ✓ Chapter reconstructed: {is_chapter} (type: {type(first_chapter).__name__})")
                    
                    # Verify SubTopic reconstruction
                    if hasattr(first_chapter, 'sub_topics') and first_chapter.sub_topics:
                        first_subtopic = first_chapter.sub_topics[0]
                        is_subtopic = isinstance(first_subtopic, SubTopic)
                        print(f"  ✓ SubTopic reconstructed: {is_subtopic} (type: {type(first_subtopic).__name__})")
            
            # Verify active_chapter reconstruction
            active_ch = curr.get("active_chapter")
            if active_ch:
                is_active_chapter = isinstance(active_ch, Chapter)
                print(f"  ✓ Active Chapter reconstructed: {is_active_chapter}")
                
    except Exception as e:
        print(f"  Note: Verification check encountered: {e}")


async def update_and_save_user_state(user_id: str, save_to: str, update_fn: typing.Callable[[User], User]) -> User:
    """Load user state, apply updates via callback, and save back to disk.
    
    Args:
        user_id: The user identifier
        save_to: Base directory where user data is stored
        update_fn: A callback function (can be sync or async) that takes the loaded User and returns the updated User
        
    Returns:
        The updated User state
        
    Example:
        async def my_updates(user_state):
            # Access curriculum (stored as List[Curriculum] per User TypedDict)
            curriculum_list = user_state.get("curriculum")
            if curriculum_list and isinstance(curriculum_list, list) and len(curriculum_list) > 0:
                curr = curriculum_list[0]  # Get first curriculum
                active_ch = curr.get("active_chapter")
                
                # Update active chapter status
                if active_ch and isinstance(active_ch, dict):
                    active_ch["status"] = Status.COMPLETED.value
                    
                    # Update subtopic
                    sub_topics = active_ch.get("sub_topics", [])
                    if sub_topics and len(sub_topics) > 0:
                        sub_topics[0]["status"] = Status.COMPLETED.value
                        sub_topics[0]["feedback"] = ["Great work!"]
            
            return user_state
        
        updated = await update_and_save_user_state("babe", "/workspace/mnt/", my_updates)
    """
    # Initialize storage paths for this user
    init_user_storage(save_to, user_id)
    
    # Load existing user state
    user_state = load_user_state(user_id)
    
    if not user_state:
        raise ValueError(f"User {user_id} not found in storage at {save_to}/{user_id}")
    
    print(f"Loaded user state for {user_id}")
    
    # Apply updates via callback (handle both sync and async callbacks)
    import inspect
    if inspect.iscoroutinefunction(update_fn):
        updated_state = await update_fn(user_state)
    else:
        updated_state = update_fn(user_state)
    
    # Save back to disk
    save_user_state(user_id, updated_state)
    print(f"Saved updated state for {user_id} to {USER_STORE_DIR / f'{user_id}.json'}")
    
    return updated_state


async def move_to_next_chapter(user_id: str, save_to: str) -> User:
    """Convenience function to move user to the next chapter in their curriculum.
    
    Args:
        user_id: The user identifier
        save_to: Base directory where user data is stored
        
    Returns:
        The updated User state
        
    This function:
    - Marks current active chapter as COMPLETED
    - Moves to next chapter (sets it as active with status STARTED)
    - Updates the study plan accordingly
    """
    
    async def _move_to_next(user_state: User) -> User:
        curriculum_list = user_state.get("curriculum")
        user_id = user_state.get("user_id")
        # curriculum is stored as List[Curriculum] per User TypedDict definition
        if not curriculum_list or not isinstance(curriculum_list, list):
            print("Warning: No curriculum found for user")
            return user_state
        
        if len(curriculum_list) == 0:
            print("Warning: Curriculum list is empty")
            return user_state
        
        # Get the first (and typically only) curriculum
        curriculum = curriculum_list[0]
        
        if not curriculum or not isinstance(curriculum, dict):
            print("Warning: Invalid curriculum format")
            return user_state
        
        new_curr = await build_next_chapter(user_id, curriculum)
        user_state["curriculum"] = [convert_to_json_safe(new_curr)]
        return user_state
    
    return await update_and_save_user_state(user_id, save_to, _move_to_next)


async def update_subtopic_status(user_id: str, save_to: str, subtopic_number: int, 
                           new_status: Status, feedback: typing.Optional[typing.List[str]] = None) -> User:
    """Update a subtopic's status and optionally add feedback in the active chapter.
    
    Args:
        user_id: The user identifier
        save_to: Base directory where user data is stored
        subtopic_number: The subtopic number to update (0-indexed)
        new_status: New status for the subtopic
        feedback: Optional list of feedback strings to add
        
    Returns:
        The updated User state
    """
    def _update_subtopic(user_state: User) -> User:
        curriculum_list = user_state.get("curriculum")
        
        # curriculum is stored as List[Curriculum] per User TypedDict definition
        if not curriculum_list or not isinstance(curriculum_list, list):
            print("Warning: No curriculum found")
            return user_state
        
        if len(curriculum_list) == 0:
            print("Warning: Curriculum list is empty")
            return user_state
        
        # Get the first (and typically only) curriculum
        curriculum = curriculum_list[0]
        
        if not curriculum or not isinstance(curriculum, dict):
            print("Warning: Invalid curriculum format")
            return user_state
        
        active_ch = curriculum.get("active_chapter")
        
        if not active_ch or not isinstance(active_ch, dict):
            print("Warning: No active chapter found")
            return user_state
        
        sub_topics = active_ch.get("sub_topics", [])
        if not sub_topics or subtopic_number >= len(sub_topics):
            print(f"Warning: Subtopic {subtopic_number} not found")
            return user_state
        
        subtopic = sub_topics[subtopic_number]
        
        if isinstance(subtopic, dict):
            subtopic["status"] = new_status.value if isinstance(new_status, Status) else new_status
            print(f"✓ Updated subtopic '{subtopic.get('sub_topic', 'unknown')}' status to {new_status}")
            
            if feedback:
                if "feedback" not in subtopic or not subtopic["feedback"]:
                    subtopic["feedback"] = []
                subtopic["feedback"].extend(feedback)
                print(f"✓ Added {len(feedback)} feedback item(s)")
        
        return user_state
    
    return await update_and_save_user_state(user_id, save_to, _update_subtopic)


async def add_quiz_to_subtopic(user_id: str, save_to: str, subtopic_number: int, quiz: dict) -> User:
    """Add a quiz to a specific subtopic in the active chapter.
    
    Args:
        user_id: The user identifier
        save_to: Base directory where user data is stored
        subtopic_number: The subtopic number to add quiz to (0-indexed)
        quiz: Quiz dictionary with keys: question, choices, answer, explanation
        
    Returns:
        The updated User state
    """
    def _add_quiz(user_state: User) -> User:
        curriculum_list = user_state.get("curriculum")
        
        # curriculum is stored as List[Curriculum] per User TypedDict definition
        if not curriculum_list or not isinstance(curriculum_list, list):
            print("Warning: No curriculum found")
            return user_state
        
        if len(curriculum_list) == 0:
            print("Warning: Curriculum list is empty")
            return user_state
        
        # Get the first (and typically only) curriculum
        curriculum = curriculum_list[0]
        
        if not curriculum or not isinstance(curriculum, dict):
            print("Warning: Invalid curriculum format")
            return user_state
        
        active_ch = curriculum.get("active_chapter")
        
        if not active_ch or not isinstance(active_ch, dict):
            print("Warning: No active chapter found")
            return user_state
        
        sub_topics = active_ch.get("sub_topics", [])
        if not sub_topics or subtopic_number >= len(sub_topics):
            print(f"Warning: Subtopic {subtopic_number} not found")
            return user_state
        
        subtopic = sub_topics[subtopic_number]
        
        if isinstance(subtopic, dict):
            if "quizzes" not in subtopic or not subtopic["quizzes"]:
                subtopic["quizzes"] = []
            subtopic["quizzes"].append(quiz)
            print(f"✓ Added quiz to subtopic '{subtopic.get('sub_topic', 'unknown')}'")
        
        return user_state
    
    return await update_and_save_user_state(user_id, save_to, _add_quiz)


def parallel_extract_study_materials(username, subject, sub_topics, pdf_file, num_docs):   
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # study_material_gen is an async coroutine. Create a small
        # synchronous wrapper that executes it via `asyncio.run` so the
        # ThreadPoolExecutor receives a regular callable that returns the
        # coroutine result (and avoids un-awaited coroutine warnings).
        def _sync_run(sub_topic):
            return asyncio.run(study_material_gen(username,subject, sub_topic, pdf_file, num_docs))

        future_to_study_material = {executor.submit(_sync_run, sub_topic): sub_topic for sub_topic in sub_topics}
        outputs = []
        for future in concurrent.futures.as_completed(future_to_study_material):
            temp = future_to_study_material[future]
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
    print(Fore.BLUE +"#### extracted future_to_page_text >>>> ", len(outputs), type(outputs),outputs[-1], Fore.RESET)
    return outputs
async def sub_topic_builder(username,pdf_loc, subject, pdf_f_name):
    sub_topics = parallel_extract_pdf_page_and_text(pdf_loc)
    sub_topics_ordered = post_process_extract_sub_chapters(sub_topics)        
    print(Fore.LIGHTGREEN_EX + " creating studying materails for chapter :", Fore.RESET)
                            
    num_docs=3
    print("subject =", subject ,"\n sub_topics=\n", sub_topics, "\npdf_f_name=\n", pdf_f_name)
    # pass the full pdf path (pdf_loc) into the extractor so it can locate the file                
    valid_sub_topics=[]
    j=0
    for sub_topic in sub_topics_ordered:
        
        print(f" ======================== j = {str(j)} | pdf_f_name : {pdf_f_name} | sub_topic= {sub_topic} ===================") 
        num_docs=3
        if ':' in sub_topic:
            _sub_topic=sub_topic.split(':')[-1]
        else:
            _sub_topic=sub_topic
        study_material_str, markdown_str = await study_material_gen(username,subject,_sub_topic, pdf_f_name, num_docs)
        if markdown_str == "":
            pass
            print(Fore.YELLOW + f"invalid subtopic {sub_topic} failed to fetch relevant documents\n ") 
        else:
            sub_topic_temp=SubTopic(
                number=j,        
                sub_topic=sub_topic,
                status=Status.NA,
                study_material=study_material_str,
                display_markdown = markdown_str,
                reference=pdf_f_name,
                quizzes = [],
                feedback = []
            )
            j+=1
            valid_sub_topics.append(sub_topic_temp)
            
            print(Fore.YELLOW + "markdown_pretty_print \n ") 
            print( study_material_str)                
            print("\n\n\n")
    return valid_sub_topics           


async def build_next_chapter( username,curriculum : Curriculum ) -> Curriculum :
    """Try to reuse the heuristics in helper.extract_summaries_and_chapters
    to create Chapter objects. We'll implement a small local parser here so
    the orchestrator is self-contained.
    """
    study_plan = curriculum["study_plan"]
    next_chapter = curriculum["next_chapter"]
    active_chapter = curriculum["active_chapter"]
    
    # Update active chapter status - handle both dict and object access
    if isinstance(active_chapter, dict):
        active_chapter["status"] = Status.COMPLETED.value
        current_index = active_chapter["number"]
    else:
        active_chapter.status = Status.COMPLETED
        current_index = active_chapter.number
    
    # Access next chapter properties - handle both dict and object access  
    if isinstance(next_chapter, dict):
        pdf_file_loc = next_chapter["pdf_loc"]
        chapter_title = next_chapter["name"]
    else:
        pdf_file_loc = next_chapter.pdf_loc
        chapter_title = next_chapter.name 

    pdf_f_name=pdf_file_loc.split('/')[-1]
    subject=pdf_f_name.split('.pdf')[0]
    
    subtopics_and_study_material = await sub_topic_builder(username,pdf_file_loc, subject, pdf_f_name)
    chap=Chapter(
    number=current_index + 1,
    name=chapter_title,
    status=Status.STARTED, 
    sub_topics=subtopics_and_study_material,        
    reference=pdf_f_name,
    pdf_loc = pdf_file_loc,
    quizzes=[],
    feedback=[])
    
    # Convert Chapter to dict for consistency
    curriculum["active_chapter"] = convert_to_json_safe(chap)
    
    # Update next_chapter - access study_plan properly
    study_plan_chapters = study_plan.get("study_plan", []) if isinstance(study_plan, dict) else study_plan.study_plan
    if current_index + 2 < len(study_plan_chapters):
        next_chap = study_plan_chapters[current_index + 2]
        curriculum["next_chapter"] = convert_to_json_safe(next_chap) if not isinstance(next_chap, dict) else next_chap
    else:
        curriculum["next_chapter"] = None
    
    print(Fore.LIGHTGREEN_EX + " Moving to next chapter: ", chapter_title, Fore.RESET)
    return curriculum


async def build_chapters(username, pdf_files_loc: str ) -> typing.List[Chapter]:
    """Try to reuse the heuristics in helper.extract_summaries_and_chapters
    to create Chapter objects. We'll implement a small local parser here so
    the orchestrator is self-contained.
    """
    
    chapter_titles_str = await chapter_gen_from_pdfs(pdf_files_loc)
    chapter_output=parse_output_from_chapters(chapter_titles_str)
    
    # Filter out invalid items (non-dicts or empty lists) and validate structure
    valid_chapter_output = [
        item for item in chapter_output 
        if isinstance(item, dict) and "file_loc" in item and "title" in item
    ]
    
    if not valid_chapter_output:
        print("Warning: No valid chapters found in chapter_output. Returning empty list.")
        print(f"Raw chapter_output: {chapter_output}")
        return []
    
    pdf_files_ls = [os.path.join(pdf_files_loc, item["file_loc"]) for item in valid_chapter_output]
    chapter_titles_cleaned_ls=[ item["title"] for item in valid_chapter_output]
    chapters=[]

    i=0
    for pdf_loc, chapter_title in zip(pdf_files_ls,chapter_titles_cleaned_ls):
        print(f"....................................... i :{str(i)}...............................")
        print( "pdf_loc =", pdf_loc , "|" , "chapter_title=",chapter_title)
        pdf_f_name=pdf_loc.split('/')[-1]
        subject=pdf_f_name.split('.pdf')[0]
        if i==0 :
            valid_sub_topics = await sub_topic_builder(username,pdf_loc, subject, pdf_f_name)
            chap=Chapter(
            number=i,
            name=chapter_title,
            status=Status.STARTED, 
            sub_topics=valid_sub_topics,        
            reference=pdf_f_name,
            pdf_loc = pdf_loc,
            quizzes=[],
            feedback=[])
            
        else:
            chap=Chapter(
            number=i,
            name=chapter_title,
            status=Status.NA, 
            sub_topics=[],        
            reference=pdf_f_name,
            pdf_loc = pdf_loc,
            quizzes=[],
            feedback=[])
        
        chapters.append(chap)
        i+=1
    

        print(Fore.LIGHTGREEN_EX + " how many chapters = \n", len(chapters), chapters, Fore.RESET)
    return chapters

async def populate_states_for_user(user: User, pdf_files_loc: str, study_buddy_preference: str) -> GlobalState:
    """Given results from MCP clients, construct Chapter, StudyPlan, Curriculum, User and GlobalState
    and persist them in the store.
    
    Args:
        user: User TypedDict with basic user information
        pdf_files_loc: Path to directory containing PDF files
        study_buddy_preference: User's preference for study buddy persona
        
    Returns:
        GlobalState TypedDict with populated user, curriculum, and study plan
    """
    username = user["user_id"]
    chapters = await build_chapters(username,pdf_files_loc)
    print(Fore.LIGHTGREEN_EX + "len of chapter is = \n",len(chapters), chapters, '\n\n', Fore.RESET )
    
    # Handle case when no chapters are found
    if len(chapters) == 0:
        raise ValueError(
            "No valid chapters found. This typically means:\n"
            "1. The PDF files directory is empty or invalid\n"
            "2. The chapter generation failed to produce valid output\n"
            "3. The PDF files don't have proper structure/content\n"
            f"PDF location checked: {pdf_files_loc}"
        )
    
    study_plan = StudyPlan(study_plan=chapters)
    if len(chapters) == 1:
        curriculum = Curriculum(active_chapter=chapters[0], study_plan=study_plan, status=Status.PROGRESSING)
    else:
        # next_chapter should refer to the second chapter in the generated list
        curriculum = Curriculum(active_chapter=chapters[0], next_chapter=chapters[1], study_plan=study_plan, status=Status.PROGRESSING)
    
    
    # build User Pydantic-compatible dict
    try :
        persona = await study_buddy_client_requests(query=study_buddy_preference)
        print(Fore.LIGHTBLUE_EX + "persona extracted from study_buddy results =\n", persona , Fore.RESET)
    except :
        persona = user["study_buddy_preference"]
    
    #existing = _load_store().get("users", {}).get(user_id, {})
    
    # Convert Pydantic Curriculum to JSON-safe dict
    curriculum_dict = convert_to_json_safe(curriculum)
    
    # User TypedDict expects curriculum as List[Curriculum], so wrap in list
    user_dict = {
        "user_id": user["user_id"],
        "study_buddy_preference": user["study_buddy_preference"],
        "study_buddy_persona": persona,
        "study_buddy_name": user["study_buddy_name"],
        "curriculum": [curriculum_dict],  # Wrap in list to match User TypedDict definition
    }

    # Save into store
    save_user_state(user["user_id"], user_dict)
    processed_pdf_files=[os.path.join(pdf_files_loc, pdf_f) for pdf_f in os.listdir(pdf_files_loc) if pdf_f.endswith('.pdf')]
    # Build GlobalState TypedDict with all required fields
    gstate: GlobalState = {
        "input": "initializing",
        "existing_user": False,  # This is a first-time user
        "user": user_dict,
        "user_id": user["user_id"],
        "chat_history": [],
        "next_node_name": "",
        "pdf_loc": pdf_files_loc,        
        "processed_files": processed_pdf_files,
        "agent_final_output": None,
        "intermediate_steps": [],
    }
    # persist top-level
    store = _load_store()
    store.setdefault("global_states", {})[user["user_id"]] = gstate
    _save_store(store)

    return gstate


async def run_for_first_time_user(user: User, uploaded_pdf_loc: str, save_to: str, study_buddy_preference: str , store_path : str = None, user_store_dir :str = None) -> GlobalState:
    """Main entrypoint: ensure user exists, call helper clients if necessary,
    populate states, and return the GlobalState.
    
    This function initializes per-user storage paths based on save_to and user_id,
    creating a directory structure for storing GlobalState and user data.
    
    Args:
        user: User TypedDict with basic user information
        uploaded_pdf_loc: Path to directory containing uploaded PDF files
        save_to: Base directory for storing user data and states
        study_buddy_preference: User's preference for study buddy persona
        
    Returns:
        GlobalState TypedDict with fully populated user state and curriculum
    """
    user_id = user["user_id"]
    
    # Initialize per-user storage paths
    print(f"Initializing storage for user {user_id} at {save_to}...")
    if store_path is None and user_store_dir is None:
        store_path, user_store_dir = init_user_storage(save_to, user_id)
    print(f"  - Global state path: {store_path}")
    print(f"  - User store directory: {user_store_dir}")
    
    if not user_exists(user_id):
        print(f"User {user_id} not found. Creating minimal user record...")
        create_user_minimal(user)

    # check if we already have a global state
    store = _load_store()
    if store.get("global_states", {}).get(user_id):
        print(f"Found existing GlobalState for user {user_id}; returning it.")
        return store["global_states"][user_id]

    # First-time population: call helper clients
    print("Populating application states ...")
    gstate = await populate_states_for_user(user, uploaded_pdf_loc, study_buddy_preference)
    
    # Update GlobalState with save_to path
    gstate["save_to"] = save_to
    
    # Re-save the updated GlobalState
    store = _load_store()
    store.setdefault("global_states", {})[user_id] = gstate
    _save_store(store)
    
    print("Done. GlobalState created and saved.")
    return gstate


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("user_id", nargs="?", default="babe")
    parser.add_argument("preference", nargs="?", default="someone who has patience, a good sense of humor, can make boring subject fun.")
    parser.add_argument("study_buddy_name", nargs="?", default="Ollie")
    parser.add_argument("pdf_loc", nargs="?", default="/workspace/mnt/pdfs/")
    parser.add_argument("save_to", nargs="?", default="/workspace/mnt/")
    args = parser.parse_args()
    
    # Create User TypedDict
    u: User = {
        "user_id": args.user_id,
        "study_buddy_preference": args.preference,
        "study_buddy_name": args.study_buddy_name,
        "study_buddy_persona": None,
        "curriculum": None,
    }
    
    uploaded_pdf_loc = args.pdf_loc
    save_to = args.save_to
    
    print(". . . . . . . . . ."*25)
    print("[FIRST_TIME_USER] : populating curriculum for first time user")
    
    # Run for first time user - returns GlobalState
    global_state: GlobalState = asyncio.run(run_for_first_time_user(u, uploaded_pdf_loc, save_to, args.preference))
    
    # Print a JSON-serializable representation of the global state
    print(json.dumps(convert_to_json_safe(global_state), indent=2, ensure_ascii=False))
    
    # Example: Demonstrate updating user state
    print("\n" + "="*60)
    print("DEMONSTRATION: Update User State Functions")
    print("="*60)
    
    # Example 1: Update a subtopic's status and add feedback
    print(". . . . . . . . . ."*25)
    print("\n1. [RETURN USER] : Updating subtopic status with feedback...")
    try:
        updated_user: User = asyncio.run(update_subtopic_status(
            user_id=args.user_id,
            save_to=save_to,
            subtopic_number=0,
            new_status=Status.COMPLETED,
            feedback=["Excellent work!", "All concepts mastered"]
        ))
        print(f"   ✓ Success! Updated user: {updated_user['user_id']}")
    except Exception as e:
        print(f"   (Skipped - user state may not exist yet: {e})")
    
    # Example 2: Add a quiz to a subtopic
    print("\n2. [RETURN USER] : Adding quiz to subtopic...")
    try:
        quiz = {
            "question": "What is the main topic discussed?",
            "choices": ["Option A", "Option B", "Option C"],
            "answer": "Option A",
            "explanation": "This is the correct answer because..."
        }
        updated_user: User = asyncio.run(add_quiz_to_subtopic(
            user_id=args.user_id,
            save_to=save_to,
            subtopic_number=0,
            quiz=quiz
        ))
        print(f"   ✓ Success! Updated user: {updated_user['user_id']}")
    except Exception as e:
        print(f"   (Skipped - user state may not exist yet: {e})")
    
    # Example 3: Move to next chapter
    print("\n3. [RETURN USER] : Moving to next chapter...")
    try:
        updated_user: User = asyncio.run(move_to_next_chapter(
            user_id=args.user_id,
            save_to=save_to
        ))
        print(f"   ✓ Success! Updated user: {updated_user['user_id']}")
        
        # Verify the update worked
        if updated_user["curriculum"] and len(updated_user["curriculum"]) > 0:
            curr = updated_user["curriculum"][0]
            active_ch = curr.get("active_chapter")
            if active_ch and isinstance(active_ch, Chapter):
                print(f"   ✓ Now on chapter: {active_ch.name} (status: {active_ch.status})")
    except Exception as e:
        print(f"   (Skipped - user state may not exist yet: {e})")
    
    # Example 4: Custom update using update_and_save_user_state
    """
    print("\n4. [RETURN USER] : Custom update using callback function...")
    try:
        def custom_update(user_state: User) -> User:
            '''Custom update logic with proper User type annotations'''
            curriculum_list = user_state.get("curriculum")
            if curriculum_list and len(curriculum_list) > 0:
                curr = curriculum_list[0]
                active_ch = curr.get("active_chapter")
                if active_ch and isinstance(active_ch, Chapter):
                    # Add custom feedback to chapter
                    if not active_ch.feedback:
                        active_ch.feedback = []
                    active_ch.feedback.append("Custom feedback added via update function")
                    print("   ✓ Added custom feedback to active chapter")
            return user_state
        
        updated_user: User = asyncio.run(update_and_save_user_state(
            user_id=args.user_id,
            save_to=save_to,
            update_fn=custom_update
        ))
        print(f"   ✓ Success! Updated user: {updated_user['user_id']}")
    except Exception as e:
        print(f"   (Skipped - user state may not exist yet: {e})")
    
    print("\n" + "="*60)
    print("✓ Update demonstrations complete!")
    print("="*60)"""
