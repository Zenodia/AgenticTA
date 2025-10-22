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

# Local simple storage for users (JSON file)
STORE_PATH = Path("/workspace/mnt/_langgraph_store.json")
USER_STORE_DIR = Path("/workspace/mnt/users")
USER_STORE_DIR.mkdir(exist_ok=True)


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


def _build_chapters_from_quiz_output(output_dir) -> typing.List[Chapter]:
    """Try to reuse the heuristics in helper.extract_summaries_and_chapters
    to create Chapter objects. We'll implement a small local parser here so
    the orchestrator is self-contained.
    """
    summaries = []
    if output_dir.endswith(".csv"):
        csv_file=output_dir
        df = pd.read_csv(csv_file)            
        output_ls=df["document_summary"].values.tolist()
        output=output_ls[0] 
        f_loc=csv_file
        if isinstance(output, str):
            summaries.append([output,f_loc]) # summaries is a list of (summary, f_location including f_name )
    else:
        csv_ls=os.listdir(output_dir)
        summary_csv_ls=[f for f in csv_ls if "summary_" in f and f.endswith(".csv")]        
        for f in summary_csv_ls: 
            f_loc=os.path.join(output_dir,f)
            df = pd.read_csv(f_loc)            
            output_ls=df["document_summary"].values.tolist()
            output=output_ls[0] 
            if isinstance(output, str):
                summaries.append([output,f_loc]) # summaries is a list of (summary, f_location including f_name )
    
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
            
            chap = Chapter(number=i+1, name=s, status=Status.NA, material=[], reference=ref, quizes=[], feedback=[])
            chapters.append(chap)
        
    return chapters


def call_helper_clients_for_user(user: User, uploaded_pdf_loc: str, save_to:str ) -> dict:
    """Use helper.run_together to run the MCP clients in parallel and
    return their results as a dict.
    The helper module already imports `quiz_generation_client`, `study_buddy_client_requests`,
    and `agentic_mem_mcp_client` so we can call them by delegating to run_together.
    """
    print(Fore.GREEN + "user =\n", type(user), user)
    save_logs = True    
    tasks = {
        "study_buddy": (study_buddy_client_requests, user["study_buddy_preference"]),        
        "quiz_gen": (quiz_generation_client, uploaded_pdf_loc, save_to),
    }
    results = run_together(tasks)

    # print parallel task results/logs
    i=0
    
    for key, result in results.items():
        print(f"------------------------------ processing {str(i)} ------------------------------")
        print(Fore.LIGHTBLUE_EX + f"Result from {key}:\n{result}\n\n")
        i+=1

    return results


def populate_states_for_user(user:User, results: dict) -> dict:
    """Given results from MCP clients, construct Chapter, StudyPlan, Curriculum, User and GlobalState
    and persist them in the store. Returns the GlobalState as dict.
    """
    quiz_output = results["quiz_gen"]
    
    summary_output_location=quiz_output.split('|')[-1].split(':')[-1]
    print(Fore.YELLOW+ "quiz_gen output extracting summary_output_location =\n", quiz_output, '\n\n', summary_output_location, Fore.RESET)
    chapters = _build_chapters_from_quiz_output(summary_output_location)
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


def run_for_user(user: User, uploaded_pdf_loc: str, save_to:str) -> dict:
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
    
    results = call_helper_clients_for_user(user, uploaded_pdf_loc, save_to)

    print("Populating application states from helper results...")
    gstate = populate_states_for_user(user, results)
    print("Done. GlobalState created and saved.")
    return gstate


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("user_id", nargs="?", default="babe")
    parser.add_argument("preference", nargs="?", default="someone who has patience, a good sense of humor, can make boring subject fun.")
    parser.add_argument("study_buddy_name", nargs="?", default="Ollie")
    parser.add_argument("pdf_loc", nargs="?", default="/workspace/mnt/pdf/")
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
    g = run_for_user(u,uploaded_pdf_loc,save_to)
    # print a JSON-serializable representation of the user
    print(json.dumps(convert_to_json_safe(u), indent=2, ensure_ascii=False))
