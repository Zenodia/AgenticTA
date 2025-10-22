from typing import TypedDict, Annotated, List ,  Any
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.messages import BaseMessage
import operator

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from IPython.display import Markdown, display
import markdown

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
    study_buddy_persona: str = Field(description="the persona of a study_buddy")
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

# how to populate each states

markdown_str = markdown.markdown(f'''
#### Intro to Driving Basics
test 1
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
    material=[markdown_str] , 
    reference="intro_to_driving.pdf",
    quizes=[quiz_1],
    feedback=["this is good!"])
chapter_2=Chapter(
    number=2,
    name="Getting to know your vehicle",
    status=Status.NA, 
    material=[markdown_str] , 
    reference="know_your_vehicle.pdf",
    quizes=[quiz_1],
    feedback=[])
p = StudyPlan(study_plan=[chapter_1, chapter_2])
print("##### An example Chapter looks like this \n", p)
c=Curriculum(active_chapter=chapter_1,next_chapter=chapter_2,study_plan=p,status=Status.PROGRESSING)
print("---"*20)
print("##### An example of Curriculum :\n\n",c)
u=User(
    user_id="babe",
    study_buddy_preference="someone who is funny", 
    study_buddy_name="Ollie", 
    study_buddy_persona="I am a very funny guy",
    curriculum=c)
print("---"*20)
print("##### An example of User :\n\n",c)
GlobalState(
    input="hello",
    user=u,
    node_name="starter_node",
    )
print("---"*20)
print(" >>>>>>>>>>>>>>>>>>  Global state : <<<<<<<<<<<<< \n\n",c)
