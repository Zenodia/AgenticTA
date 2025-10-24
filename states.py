from typing import TypedDict, Annotated, List ,  Any
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.messages import BaseMessage
import operator

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from IPython.display import Markdown, display
import markdown
import json
from pydantic import parse_obj_as


def printmd(markdown_str):
    display(Markdown(markdown_str))
#printmd(markdown_str)

class Status(Enum):
    NA = "NA"
    STARTED = "started"
    PROGRESSING = "progressing"
    COMPLETED = "completed"

#class MyModel(BaseModel):
#    status: Optional[Status] = None

# Example usage:
#model = MyModel(status=Status.STARTED)
#print(model.status)          # Output: Status.STARTED
#print(MyModel().status)      # Output: None

class Chapter(BaseModel):
    number : int = Field(description="each chapter is numbered")
    name : str = Field(description="name of this chapter")
    status: Optional[Status] = None
    sub_topics: Optional[List[str]] = Field(description="list of sub_topics under this chapter")
    material: List[Any] # each studying materails should be in markdown format  
    reference: str = Field(description="name of the PDF document, from which this chapter is derived")    
    quizes : List[dict] # each quiz is a dictionary, user can generate several round of quizes
    feedback:Optional[List[str]]

## each quiz is a dictionary looks like this 
class StudyPlan(BaseModel):
    study_plan : List[Chapter]

class Curriculum(TypedDict):
    active_chapter : Optional[Chapter]
    next_chapter : Optional[Chapter]
    study_plan: Optional[StudyPlan]    
    status : List[Optional[Status]]     


class User(TypedDict):
    user_id : str = Field(description="each user should have a unique user_id")
    study_buddy_preference: Optional[str] = Field(description="user specified preference of a study_buddy")
    study_buddy_persona: Optional[str] = Field(description="the persona of a study_buddy")
    study_buddy_name: str = Field(description="name of the study_buddy")
    curriculum: Optional[List[Curriculum]]

class GlobalState(TypedDict):
    # The input string
    input: str
    user_id : str = Field(description="each user should have a user_id, if it is not specified, it will be randomly generated")
    # The list of previous messages in the conversation
    chat_history: list[BaseMessage]
    # The outcome of a given call to the agent
    # Needs `None` as a valid type, since this is what this will start as
    user: User
    node_name: str = Field(description="name of the current node in the agentic system")
    # List of actions and corresponding observations
    # Here we annotate this with `operator.add` to indicate that operations to
    # this state should be ADDED to the existing values (not overwrite it)


def _to_json_safe(obj):
    """Recursively convert Pydantic models, Enums and other non-JSON types to JSON-serializable forms."""
    # Pydantic BaseModel
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        return _to_json_safe(obj.dict())
    # Enums
    if isinstance(obj, Enum):
        return obj.value
    # dict
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    # list/tuple
    if isinstance(obj, (list, tuple)):
        return [_to_json_safe(v) for v in obj]
    # Base types
    return obj


def save_user_to_file(user: User, path: str):
    """Save a User TypedDict (which may include Pydantic models) to a JSON file."""
    safe = _to_json_safe(user)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(safe, f, ensure_ascii=False, indent=2)


def convert_to_json_safe(obj):
    """Public wrapper to convert objects (Pydantic models, Enums, lists, dicts)
    into JSON-serializable structures.
    """
    return _to_json_safe(obj)


def _construct_enum(enum_cls, value):
    try:
        return enum_cls(value)
    except Exception:
        return None


def load_user_from_file(path: str) -> User:
    """Load the JSON file and reconstruct User, Chapter, StudyPlan and Curriculum structures.

    This function makes minimal assumptions based on the current models in this module.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Reconstruct Curriculum/StudyPlan/Chapter objects where appropriate
    # If 'curriculum' is a mapping for a single curriculum, keep it as-is.
    curr = data.get("curriculum")
    if curr is None:
        return data

    # curriculum may be a single object (TypedDict). Try to rebuild Chapter and StudyPlan
    def rebuild_chapter(ch):
        # ch may already be a structure matching Chapter fields
        if not isinstance(ch, dict):
            return ch
        # rebuild status enum
        status = ch.get("status")
        if status is not None:
            ch["status"] = _construct_enum(Status, status)
        return Chapter(**ch)

    # If study_plan is present and looks like {'study_plan': [...]}
    if isinstance(curr, dict):
        sp = curr.get("study_plan")
        if sp and isinstance(sp, dict):
            plan_list = sp.get("study_plan", [])
            plan_objs = [rebuild_chapter(x) for x in plan_list]
            study_plan = StudyPlan(study_plan=plan_objs)
        elif sp and isinstance(sp, list):
            # sometimes it's already a list of chapters
            plan_objs = [rebuild_chapter(x) for x in sp]
            study_plan = StudyPlan(study_plan=plan_objs)
        else:
            study_plan = None

        active = curr.get("active_chapter")
        next_c = curr.get("next_chapter")
        active_obj = rebuild_chapter(active) if active else None
        next_obj = rebuild_chapter(next_c) if next_c else None

        curriculum_obj = {
            "active_chapter": active_obj,
            "next_chapter": next_obj,
            "study_plan": study_plan,
            "status": curr.get("status"),
        }
        data["curriculum"] = curriculum_obj

    return data


if __name__ == "__main__":
    # demo: save and load the example user
    
    # how to populate each states

    driving_intro = markdown.markdown(f'''
    #### Intro to Driving Basics
    here is the study material for learning the basics on driving theory.
    Before you start practicing driving, you need to understand many things ...
    blah blah blah blah blah blah ...
    ''')
    know_ur_car = markdown.markdown(f'''
    #### Know Your Vehicles
    here is the study material for getting to know your vehicles.
    First of all, it is important to understand , that there are manual vs automatic gear system.
    blah blah blah blah blah blah ...
    ''')

    quiz_1={
        "question": "my question",
        "choices": ["A","B","C"],
        "answer": "A",  # Index of correct choice (0-based)
        "explanation": "here is an explanation"
    }
    chapter_1=Chapter(
        number=1,
        name="Intro to Driving Basics",
        status=Status.STARTED, 
        sub_topics=[],
        material=[driving_intro] , 
        reference="intro_to_driving.pdf",
        quizes=[quiz_1],
        feedback=["this is good!"])
    chapter_2=Chapter(
        number=2,
        name="Getting to know your vehicle",
        status=Status.NA, 
        sub_topics=[],
        material=[know_ur_car] , 
        reference="know_your_vehicle.pdf", 
        quizes=[quiz_1],
        feedback=[])
    p = StudyPlan(study_plan=[chapter_1, chapter_2])
    #print("##### An example Chapter looks like this \n", p)
    c=Curriculum(active_chapter=chapter_1,next_chapter=chapter_2,study_plan=p,status=Status.PROGRESSING)
    #print("---"*20)
    #print("##### An example of Curriculum :\n\n",c)
    u=User(
        user_id="babe",
        study_buddy_preference="someone who is funny", 
        study_buddy_name="Ollie", 
        study_buddy_persona="I am a very funny guy",
        curriculum=c)
    #print("---"*20)
    #print("##### An example of User :\n\n",c)
    GlobalState(
        input="hello",
        user=u,
        node_name="starter_node",
        )
    #print("---"*20)
    #print(" >>>>>>>>>>>>>>>>>>  Global state : <<<<<<<<<<<<< \n\n",c)

    """
    demo_path = "user_state.json"
    print(f"Saving example user to {demo_path}")
    save_user_to_file(u, demo_path)
    print("Saved. Now loading back and printing summary...")
    loaded = load_user_from_file(demo_path)
    # print a small check
    try:
        print("Loaded user_id:", loaded.get("user_id"))
        curr = loaded.get("curriculum")
        if isinstance(curr, dict) and curr.get("active_chapter"):
            ac = curr["active_chapter"]
            print("Active chapter name:", ac.name if hasattr(ac, 'name') else ac.get('name'))
    except Exception as e:
        print("Load check error:", e)
    """
