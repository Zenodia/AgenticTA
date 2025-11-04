"""A lightweight orchestrator that builds LangGraph-like nodes to populate
the application's state objects defined in `states.py` using helper clients.

This file provides a minimal runtime-friendly shim for composing nodes (steps)
that can be wired together. It uses `helper.run_together` to call the MCP
clients (quiz generation, study buddy, agentic memory) and then constructs
`Chapter`, `StudyPlan`, `Curriculum`, `User`, and `GlobalState` objects.

The orchestrator exposes a `run_for_user(user_id)` function that will check
for an existing user (in a local JSON store), create/populate state objects
for first-time users, and return the final GlobalState instance.
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

# Local simple storage for users (JSON file)
STORE_PATH = Path(os.environ["global_state_json_path"])
USER_STORE_DIR = Path(os.environ["user_store_path"])
USER_STORE_DIR.mkdir(exist_ok=True)

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


def create_user_minimal(user: User) -> dict:
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


def save_user_state(user_id: str, user_obj: dict):
    # Persist per-user JSON using states.save_user_to_file for Pydantic-aware serialization
    save_user_to_file(user_obj, str(USER_STORE_DIR / f"{user_id}.json"))
    # Keep central store in sync as a convenience index
    store = _load_store()
    users = store.setdefault("users", {})
    # central store must contain only JSON-serializable data
    users[user_id] = convert_to_json_safe(user_obj)
    _save_store(store)


def load_user_state(user_id: str) -> dict:
    user_file = USER_STORE_DIR / f"{user_id}.json"
    if user_file.exists():
        return load_user_from_file(str(user_file))
    # fallback to central store
    return _load_store().get("users", {}).get(user_id)


def parallel_extract_study_materials(subject, sub_topics, pdf_file, num_docs):   
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # study_materail_create is an async coroutine. Create a small
        # synchronous wrapper that executes it via `asyncio.run` so the
        # ThreadPoolExecutor receives a regular callable that returns the
        # coroutine result (and avoids un-awaited coroutine warnings).
        def _sync_run(sub_topic):
            return asyncio.run(study_materail_create(subject, sub_topic, pdf_file, num_docs))

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
async def sub_topic_builder(pdf_loc, subject, pdf_f_name):
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
        study_material_str, markdown_str = await study_material_gen(subject,_sub_topic, pdf_f_name, num_docs)
        if markdown_str == "":
            pass
            print(Fore.YELLOW + f"invalid subtopic {sub_topic} failed to fetch relevant documents\n ") 
        else:
            sub_topic_temp=SubTopic(
                number=j,        
                sub_topic=sub_topic,
                status=Status.NA,
                study_material=study_material_str,
                reference=pdf_f_name,
                quizes = [],
                feedback = []
            )
            j+=1
            valid_sub_topics.append(sub_topic_temp)
            sub_topic_ls.append(sub_topic)
            print(Fore.YELLOW + "markdown_pretty_print \n ") 
            print( study_material_str)                
            print("\n\n\n")
    return valid_sub_topics           


async def build_next_chapter( curriculum : Curriculum ) -> Curriculum :
    """Try to reuse the heuristics in helper.extract_summaries_and_chapters
    to create Chapter objects. We'll implement a small local parser here so
    the orchestrator is self-contained.
    """
    study_plan = curriculum["study_plan"]
    next_chapter = curriculum["next_chapter"]
    active_chapter = curriculum["active_chapter"]
    active_chapter.status = Status.COMPLETED 
    current_index = active_chapter.number 
    pdf_file_loc = next_chapter.pdf_loc 
    chapter_titile = next_chapter.name 

    pdf_f_name=pdf_file_loc.split('/')[-1]
    subject=pdf_f_name.split('.pdf')[0]
    
    subtopics_and_study_material = await sub_topic_builder(pdf_file_loc, subject, pdf_f_name)
    chap=Chapter(
    number=i,
    name=chapter_title,
    status=Status.STARTED, 
    sub_topics=subtopics_and_study_material,        
    reference=pdf_f_name,
    pdf_loc = pdf_loc,
    quizes=[],
    feedback=[])
    curriculum["active_chapter"]=chap 
    curriculum["next_chapter"] = study_plan[current_index+1]
    print(Fore.LIGHTGREEN_EX + " how many chapters = \n", len(chapters), chapters, Fore.RESET)
    return curriculum


async def build_chapters( pdf_files_loc: str ) -> typing.List[Chapter]:
    """Try to reuse the heuristics in helper.extract_summaries_and_chapters
    to create Chapter objects. We'll implement a small local parser here so
    the orchestrator is self-contained.
    """
    
    chapter_titles_str = chapter_gen_from_pdfs(pdf_files_loc)
    chapter_output=parse_output_from_chapters(chapter_titles_str)
    
    pdf_files_ls = [os.path.join(pdf_files_loc, item["file_loc"]) for item in chapter_output]
    chapter_titles_cleaned_ls=[ item["title"] for item in chapter_output]
    chapters=[]

    i=0
    for pdf_loc, chapter_title in zip(pdf_files_ls,chapter_titles_cleaned_ls):
        print(f"....................................... i :{str(i)}...............................")
        print( "pdf_loc =", pdf_loc , "|" , "chapter_title=",chapter_title)
        pdf_f_name=pdf_loc.split('/')[-1]
        subject=pdf_f_name.split('.pdf')[0]
        if i==0 :
            valid_sub_topics = await sub_topic_builder(pdf_loc, subject, pdf_f_name)
            chap=Chapter(
            number=i,
            name=chapter_title,
            status=Status.STARTED, 
            sub_topics=valid_sub_topics,        
            reference=pdf_f_name,
            pdf_loc = pdf_loc,
            quizes=[],
            feedback=[])
            
        else:
            chap=Chapter(
            number=i,
            name=chapter_title,
            status=Status.NA, 
            sub_topics=[],        
            reference=pdf_f_name,
            pdf_loc = pdf_loc,
            quizes=[],
            feedback=[])
        
        chapters.append(chap)
        i+=1
    

        print(Fore.LIGHTGREEN_EX + " how many chapters = \n", len(chapters), chapters, Fore.RESET)
    return chapters

async def populate_states_for_user(user:User, pdf_files_loc: str, study_buddy_preference: str) -> dict:
    """Given results from MCP clients, construct Chapter, StudyPlan, Curriculum, User and GlobalState
    and persist them in the store. Returns the GlobalState as dict.
    """
    chapters = await build_chapters(pdf_files_loc)
    print(Fore.LIGHTGREEN_EX + "len of chapter is = \n",len(chapters), chapters, '\n\n', Fore.RESET )
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
    
    user_dict = {
        "user_id": user["user_id"],
        "study_buddy_preference": user["study_buddy_preference"],
        "study_buddy_persona": persona,
        "study_buddy_name": user["study_buddy_name"],
        "curriculum": curriculum,
    }

    # Save into store
    save_user_state(user["user_id"], user_dict)

    # Build GlobalState-like dict
    gstate = {
        "input": "initializing",
        "user_id": user["user_id"],
        "chat_history": [],
        "user": user_dict,
        "node_name": "orchestrator_start",
    }
    # persist top-level
    store = _load_store()
    store.setdefault("global_states", {})[user["user_id"]] = gstate
    _save_store(store)

    return gstate


async def run_for_first_time_user(user: User, uploaded_pdf_loc: str, save_to:str, study_buddy_preference: str) -> dict:
    """Main entrypoint: ensure user exists, call helper clients if necessary,
    populate states, and return the GlobalState dict.
    """
    user_id = user["user_id"]
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
    u=User(
    user_id=args.user_id,
    study_buddy_preference=args.preference, 
    study_buddy_name=args.study_buddy_name, 
    study_buddy_persona=None,
    )
    uploaded_pdf_loc=args.pdf_loc
    save_to=args.save_to
    g = asyncio.run(run_for_first_time_user(u,uploaded_pdf_loc,save_to, args.preference))
    # print a JSON-serializable representation of the user
    print(json.dumps(convert_to_json_safe(u), indent=2, ensure_ascii=False))
