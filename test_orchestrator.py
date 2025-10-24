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
from chapter_gen import process_parallel_titles,post_process_chapter_title
from states import Chapter, StudyPlan, Curriculum, User, GlobalState, Status
from states import save_user_to_file, load_user_from_file
from states import convert_to_json_safe
from study_material_gen_agent import fetch_quiz_qa_pairs, sub_chapter_generation
import asyncio
import concurrent 
# Local simple storage for users (JSON file)
STORE_PATH = Path("/workspace/mnt/_GlobalState_store.json")
USER_STORE_DIR = Path("/workspace/mnt/users")
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


async def _build_chapters_from_quiz_output( pdf_files:list[str], quiz_csv_locations: list[str], summary_csv_locations:list[str]) -> typing.List[Chapter]:
    """Try to reuse the heuristics in helper.extract_summaries_and_chapters
    to create Chapter objects. We'll implement a small local parser here so
    the orchestrator is self-contained.
    """
        
    summaries = None
    for summary_csv_location, pdf_file in zip(summary_csv_locations, pdf_files):
    
        df = pd.read_csv(summary_csv_location)    

        output=df["document_summary"].values.tolist()[0]
        summaries.append([output,pdf_file]) # summaries is a list of (summary, f_location including f_name )
        print(Fore.MAGENTA + f"pdf_file ={pdf_file} summaries =\n", output , Fore.RESET)

    if not summaries :
        print(Fore.RED + "no summaries is extracted, check the quiz generation pipeline errors...", Fore.RESET)
        return []
    else:
        sumamries_ls=[summary[0] for summary in summaries]  # extract only the summary text
        chapter_nrs=[i for i in range(len(sumamries_ls))]  # generate chapter numbers based on the number of summaries

        chapter_titles = process_parallel_titles(sumamries_ls, chapter_nrs)        
        chapter_title_cleaned = post_process_chapter_title(chapter_titles)
        doc_reference_names = [summary[1] for summary in summaries]  # extract f_location as document reference names

        n=len(doc_reference_names)
    
    chapters=[]
    for i, s, ref in zip(range(n), chapter_title_cleaned, doc_reference_names):
        if i==0:
            print(Fore.LIGHTGREEN_EX + f"Generating subtopics for chapter {i+1} : {s} ..." , Fore.RESET)
            sub_topics_ls=generate_subtopics_for_chapter(s, quiz_csv_locations[i])
            study_materials_for_first_chapter = await generate_parallel_study_materails(s,sub_topics_ls)
            chap = Chapter(number=i+1, name=s, status=Status.NA, sub_topics=sub_topics_ls, material=study_materials_for_first_chapter, reference=ref, quizes=[], feedback=[])
        else:
            chap = Chapter(number=i+1, name=s, status=Status.NA,sub_topics=[], material=[], reference=ref, quizes=[], feedback=[])
            chapters.append(chap)
        
    return chapters


def call_helper_clients_for_user(user: User, uploaded_pdf_loc: str, save_to:str ) -> dict:
    """Use helper.run_together to run the MCP clients in parallel and
    return their results as a dict.
    The helper module already imports `quiz_generation_client`, `study_buddy_client_requests`,
    and `agentic_mem_mcp_client` so we can call them by delegating to run_together.
    """
    global quiz_gen_output_files_loc, quiz_gen_tasks_ls, pdf_files
    print(Fore.GREEN + "user =\n", type(user), user)
    pdf_files=os.listdir(uploaded_pdf_loc)
    pdf_files=[os.path.join(uploaded_pdf_loc, f) for f in pdf_files if f.endswith('.pdf')]
    tasks={}
    quiz_gen_output_files_loc=[]
    if len(pdf_files) >1:
        for pdf_file in pdf_files:
            pdf_file_name=pdf_file.split('/')[-1].split(".pdf")[0]
            
            os.makedirs(os.path.join(save_to, pdf_file_name),exist_ok=True)
            save_to_pdf=os.path.join(save_to, pdf_file_name)
            quiz_gen_output_files_loc.append(save_to_pdf)
            quiz_gen_task_item=f"quiz_{pdf_file_name}"
            quiz_gen_tasks_ls.append(quiz_gen_task_item)
            print(Fore.GREEN + f"adding quiz generation task for pdf_file ={pdf_file} saving to {save_to_pdf} ..." , Fore.RESET)
            tasks[quiz_gen_task_item]=(quiz_generation_client, uploaded_pdf_loc, save_to_pdf)

    save_logs = True   
    ## adding study_buddy client as task 
    tasks["study_buddy"]= (study_buddy_client_requests, user["study_buddy_preference"])     
    
    results = run_together(tasks)

    # print parallel task results/logs
    i=0
    
    for key, result in results.items():
        print(f"------------------------------ processing {str(i)} ------------------------------")
        print(Fore.LIGHTBLUE_EX + f"Result from {key}:\n{result}\n\n")
        i+=1

    return results, pdf_files


def generate_subtopics_for_chapter(chapter_topic:str, quiz_csv_loc:str) -> str:
    quiz_qa_pairs=fetch_quiz_qa_pairs(quiz_csv_loc)
    
    sub_chapters_ls=sub_chapter_generation(chapter_topic,quiz_qa_pairs)

    return sub_chapters_ls

async def generate_study_material_for_chapter(chapter_topic:str, sub_topic:str) -> str:
    study_material_output=await study_material_gen(chapter_topic, sub_topic)
    return study_material_output

    
def pretty_print_study_material_in_markdown(study_material_output:str):
    markdown_str = markdown.markdown(study_material_output)

    def printmd(markdown_str):
        display(Markdown(markdown_str))
    printmd(markdown_str)


async def generate_parallel_study_materails(chapter_topic, sub_topics):
    # Use asyncio tasks rather than ThreadPoolExecutor to correctly await
    # the async `generate_study_material_for_chapter` coroutine.
    max_concurrency = 5
    sem = asyncio.Semaphore(max_concurrency)

    async def _worker(subject, subtopic):
        async with sem:
            try:
                result = await generate_study_material_for_chapter(subject, subtopic)
                try:
                    print('page is %d bytes' % (len(result)))
                except Exception:
                    pass
                return result
            except Exception as exc:
                print('generated an exception: %s' % (exc))
                return ''

    # create tasks for each subtopic and await them
    tasks = [asyncio.create_task(_worker(chapter_topic, st)) for st in sub_topics]
    outputs = await asyncio.gather(*tasks)
    print("#### the generated study_materials >>>> ", len(outputs))
    return outputs




async def populate_states_for_user(user:User, results: dict, pdf_files: list[str]) -> dict:
    """Given results from MCP clients, construct Chapter, StudyPlan, Curriculum, User and GlobalState
    and persist them in the store. Returns the GlobalState as dict.
    """
    ## only populate the 1st chapter's study materials, other chapters will be populated/triggered when user finish the previous chapter in the UI
    first_chapter_quiz_loc=quiz_gen_tasks_ls[0]
           
    quiz_output = results[first_chapter_quiz_loc]
    print(Fore.LIGHTBLUE_EX + "\n quiz_output =\n", type(quiz_output), quiz_output,'\n\n' ,Fore.RESET )
    summary_output_location=quiz_output.split('|')[-1].split(':')[-1]
    quiz_csv_locations=[]
    summary_csv_locations=[]
    print(Fore.LIGHTBLUE_EX + "\n quiz_gen_tasks_ls =\n", quiz_gen_tasks_ls,'\n\n' ,Fore.RESET )
    for quiz_gen_task in quiz_gen_tasks_ls:
        if quiz_gen_task.startswith("quiz_"):
            quiz_output = results[quiz_gen_task]
            single_shot_csv_location=quiz_output.split("|")[-2].split(":")[-1]
            summary_csv_location=quiz_output.split("|")[-1].split(":")[-1]
            summary_csv_locations.append(summary_csv_location)
            print(Fore.CYAN + f"\n single_shot_csv_location for {quiz_gen_task} =\n", single_shot_csv_location,'\n\n' ,Fore.RESET )
            quiz_csv_locations.append(single_shot_csv_location)
    #quiz_csv_locations= [ result[quiz_gen_task].split("|")[-2].split(":")[-1] for quiz_gen_task in quiz_gen_tasks_ls if quiz_gen_task.startswith("quiz_") ]
    
    
    
    print(Fore.YELLOW+ "single shot quiz csv_file_location =\n", quiz_csv_locations, Fore.RESET)
    chapters = await _build_chapters_from_quiz_output(pdf_files, quiz_csv_locations, summary_csv_locations)
    study_plan = StudyPlan(study_plan=chapters)
    if len(chapters) == 1:
        curriculum = Curriculum(active_chapter=chapters[0], study_plan=study_plan, status=Status.PROGRESSING)
    else:
        # next_chapter should refer to the second chapter in the generated list
        curriculum = Curriculum(active_chapter=chapters[0], next_chapter=chapters[1], study_plan=study_plan, status=Status.PROGRESSING)
    
    
    # build User Pydantic-compatible dict
    if "study_buddy" in results:
        persona = results["study_buddy"]
        print(Fore.LIGHTBLUE_EX + "persona extracted from study_buddy results =\n", persona , Fore.RESET)
    else:
        persona = user["study_buddy_persona"]
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


async def run_for_user(user: User, uploaded_pdf_loc: str, save_to:str) -> dict:
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
    print("Calling helper clients to populate initial state...")
    
    results , pdf_files = call_helper_clients_for_user(user, uploaded_pdf_loc, save_to)

    print("Populating application states from helper results...")
    gstate = await populate_states_for_user(user, results, pdf_files)
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
    g = asyncio.run(run_for_user(u,uploaded_pdf_loc,save_to))
    # print a JSON-serializable representation of the user
    print(json.dumps(convert_to_json_safe(u), indent=2, ensure_ascii=False))
