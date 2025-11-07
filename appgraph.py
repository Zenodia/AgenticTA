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
import random
from colorama import Fore
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from langgraph.graph import END, StateGraph
from nodes import init_user_storage,user_exists,load_user_state, update_and_save_user_state, move_to_next_chapter, update_subtopic_status,add_quiz_to_subtopic, build_next_chapter
from states import Chapter, StudyPlan, Curriculum, User, GlobalState, Status, SubTopic

"""
## copy GlobalState here for reference 
class GlobalState(TypedDict):
    input: str
    existing_user: bool 
    user: User
    user_id: str  # each user should have a user_id, if it is not specified, it will be randomly generated    
    chat_history: list[BaseMessage]
    next_node_name: str  # name of the current node in the agentic system
    pdf_loc: str  # the location where the pdfs files are uploaded to, default to /workspace/mnt/pdfs/
    save_to: str  # the location to save processed study material, user states and more, default to /workspace/mnt/
    agent_final_output: Union[str, Markdown, None]        
    intermediate_steps: Annotated[list[Union[str, Markdown]], operator.add]
"""

def check_user(data):
    inputs = data.copy()
    user_id=inputs["user_id"]    
    init_user_storage(save_to, user_id)
    
    
    user_exist_flag = user_exists(user_id=user_id)
    data["existing_user"]=user_exist_flag
    ## if it is existing user, then load the existing user states and restore from disk
    ## if it is new user then create new curriculum 
    print(Fore.BLUE + "Node = **check_user** > data : ", data ,Fore.RESET)
    if not data["intermediate_steps"] :
        data["intermediate_steps"] =[]
    if user_exist_flag:        
        data["next_node_name"]="query_routing"
        # Load existing user state
        user_state = load_user_state(user_id)
    
    else:        
        data["intermediate_steps"].append("first_time_user_setup")
        data["next_node_name"]= "query_routing"
    return data


def query_routing(data):
    existing_user = data["existing_user"]
    ## first time user invoke creation of curriculum 
    query=data["input"]
    # llm should classify the query into one of the following 
    ## study_session : study the study materials via chatting with study buddy 
    ## quiz: ready for quiz 
    ## next_chapter : completed this chapter and move on to next chapter 
    ## next_sub_topic : completed this sub_topic and move on to next sub_topic
    ## chitchat : sometimes one needs to relax and chitchat that has nothing to do with studying nor the material 
    ## save_and_quit : if user is too tired to go on and would like to save the current progress and quit , but resume later on.
    if not data["next_node_name"]:
        output  = random.sample(["study_session","quiz", "next_sub_topic", "next_chapter","chitchat","save_and_quit", "end", "first_time_user_setup"],1)
    else:
        output= data["next_node_name"]
    print(Fore.CYAN +"Node = **query_routing** > output : ", output )    
    print("Node = **query_routing** > data : ", data , Fore.RESET)
    
    if "study_session" in output:
        data["intermediate_steps"].append("study_session")
        next_node="continue"
    elif "next_chapter" in output:
        data["intermediate_steps"].append("move_to_next_chapter")
        next_node="continue"
    elif "quiz" in output : 
        data["intermediate_steps"].append( "add_quiz_to_subtopic")
        next_node="continue"
    elif "next_sub_topic" in output:
        data["intermediate_steps"].append("move_to_next_subtopic")
        next_node="continue"
    elif "save_and_quit" in output : 
        data["intermediate_steps"].append("save_andupdate_user_states")
        next_node="continue"
    elif "chitchat" in output:
        data["intermediate_steps"].append("chitchat")
        next_node="continue"
    elif "first_time_user_setup" in output:
        data["intermediate_steps"].append("first time user")
        next_node="end"
    else:
        next_node ="end"
    return next_node


def execute_tools(data):
    existing_user = data["existing_user"]
    ## first time user invoke creation of curriculum 
    query=data["input"]
    # llm should classify the query into one of the following 
    ## study_session : study the study materials via chatting with study buddy 
    ## quiz: ready for quiz 
    ## next_chapter : completed this chapter and move on to next chapter 
    ## next_sub_topic : completed this sub_topic and move on to next sub_topic
    ## chitchat : sometimes one needs to relax and chitchat that has nothing to do with studying nor the material 
    ## save_and_quit : if user is too tired to go on and would like to save the current progress and quit , but resume later on. 
    tool= data["intermediate_steps"][-1]
    if not data["intermediate_steps"] :
        data["intermediate_steps"] =[]
    print("\n")
    print(Fore.MAGENTA + "Node = **execute_tool** > executing tool : ", tool )
    print("Node = **execute_tool** > data : ", data , Fore.RESET)
    if "study_session" in tool :
        
        data["agent_final_output"]="this is study session"
    elif "next_chapter" in tool :
        
        data["agent_final_output"]="move to next chapter"
    elif "quiz" in tool  : 
        
        data["agent_final_output"]="added quiz , take a look at quiz session"
    elif "next_subtopic" in tool :
        
        data["agent_final_output"]="move to move_to_next_subtopic"
    elif "save_and_quit" in tool : 
        
        data["agent_final_output"]="thanks for talking to me, I'll remember our conversation and your study progress, see you next time !"
    elif "chitchat" in tool :
        
        data["agent_final_output"]="hey what's up?"       
    elif "first_time_user_setup" in tool:
        data["agent_final_output"]="you are all set to go !"
    else:
        data["agent_final_output"]="completed"
    data["next_node_name"]="end"
    return data


# Define a new graph
workflow = StateGraph(GlobalState)

# Define the two nodes we will cycle between
workflow.add_node("check_user", check_user)
workflow.add_node("execute_tools", execute_tools)

# Set the entrypoint as `agent`
# This means that this node is the first one called
workflow.set_entry_point("check_user")

# We now add a conditional edge
workflow.add_conditional_edges(
    # First, we define the start node. We use `agent`.
    # This means these are the edges taken after the `agent` node is called.
    "check_user",
    # Next, we pass in the function that will determine which node is called next.
    query_routing,
    # Finally we pass in a mapping.
    # The keys are strings, and the values are other nodes.
    # END is a special node marking that the graph should finish.
    # What will happen is we will call `should_continue`, and then the output of that
    # will be matched against the keys in this mapping.
    # Based on which one it matches, that node will then be called.
    {
        # If `tools`, then we call the tool node.
        "continue": "execute_tools",
        # Otherwise we finish.
        "end": END,
    },
)

# We now add a normal edge from `tools` to `agent`.
# This means that after `tools` is called, `agent` node is called next.
workflow.add_edge("execute_tools", "check_user")

# Finally, we compile it!
# This compiles it into a LangChain Runnable,
# meaning you can use it as you would any other runnable
app = workflow.compile()


inputs={
    "user_id": "babe", 
    "existing_user": False, 
    "input": "make a curriculum for me", 
    "pdf_loc": "/workspace/mnt/pdfs", 
    "save_to": "workspace/mnt/",
    "chat_history": [],
    "next_node_name": "",
    "agent_final_output": None,
    "intermediate_steps": []
}
#ipython kernel install --user --name=my-conda-env-kernel   # configure Jupyter to use Python kernel
#out=app.invoke(inputs)
#print(out["intermediate_steps"])
#print("--"*10)
#print(out["agent_final_output"])
save_to="/workspace/mnt/"
user_id="babe"
init_user_storage(save_to, user_id)
    
# Load existing user state
user_state = load_user_state(user_id)
print("----"*10)
print(type(user_state), user_state.keys())
print(type(user_state["curriculum"][0]), user_state["curriculum"][0].keys())
c=user_state["curriculum"][0]
print(type(c["active_chapter"]), type(c["study_plan"]), type(c["status"]))
print("## \n")
