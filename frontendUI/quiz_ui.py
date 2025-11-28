"""
Quiz tab UI components and logic.
"""
import pandas as pd
import sys
from pathlib import Path

# Add parent directory to path so we can import from root-level modules
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
import os
import random
from colorama import Fore
from utils import get_question, get_answer, get_citation_as_explain, get_choices
from standalone_quizes_gen import get_quiz, quiz_output_parser
from nodes import init_user_storage,user_exists,load_user_state,save_user_state, _save_store, _load_store
from nodes import update_and_save_user_state, move_to_next_chapter, update_subtopic_status,add_quiz_to_subtopic, build_next_chapter, run_for_first_time_user
import asyncio
from states import Chapter, StudyPlan, Curriculum, User, GlobalState, Status, SubTopic, printmd
import yaml
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

# Global variables to track state
current_question = 0
user_answers = []
quiz_data = []
df = None



def load_quiz_data(mnt_folder=mnt_folder, username=None, save_to=None):
    """Load quiz data from CSV files"""
    global quiz_data
    store_path, user_store_dir = init_user_storage(save_to, username)
    u=load_user_state(username)
    active_chapter = u["curriculum"][0]["active_chapter"]
    quizzes_d_ls = active_chapter.sub_topics[0].quizzes 
    if quizzes_d_ls: 
        quiz_data=quizzes_d_ls
    else:
        title=active_chapter.name
        summary=active_chapter.sub_topics[0].sub_topic
        text_chunk=active_chapter.sub_topics[0].study_material
        quizes_ls= get_quiz(title, summary, text_chunk, "")
        quizzes_d_ls=quiz_output_parser(quizes_ls)
    try :
        
        quiz_data = []
        for i in range(len(quizzes_d_ls)):
            quiz_d = quizzes_d_ls[i]
            item = {
                "question": get_question(quiz_d),
                "choices": get_choices(quiz_d),
                "answer": get_answer(quiz_d),
                "explanation": get_citation_as_explain(quiz_d)
            }
            quiz_data.append(item)
    except Exception as e:
        #print(Fore.RED + "Error loading quiz data:", str(e), Fore.RESET)
        item = {
                "question": "Sample Question: What is the capital of France?",
                "choices": ["(A) Berlin", "(B) Madrid", "(C) Paris", "(D) Rome"],
                "answer": "(C)",
                "explanation": "The capital of France is Paris."
            }
        quiz_data = [item]


def init_quiz(username):
    """Initialize quiz state"""
    global current_question, user_answers
    # Use global mnt_folder as save_to
    save_to = mnt_folder
    load_quiz_data(mnt_folder=mnt_folder, username=username, save_to=save_to)
    current_question = 0
    user_answers = [None] * len(quiz_data)
    return update_question()


def update_question():
    """Update the displayed question"""
    import gradio as gr
    question_data = quiz_data[current_question]
    progress = f"Question {current_question + 1} of {len(quiz_data)}"
    
    # Determine button visibility
    show_prev = current_question > 0
    show_next = current_question < len(quiz_data) - 1
    show_submit = current_question == len(quiz_data) - 1  # Show submit only on last question
    
    return (
        progress,
        question_data["question"],
        gr.update(choices=question_data["choices"], value=user_answers[current_question]),
        gr.update(visible=show_prev),
        gr.update(visible=show_next),
        gr.update(visible=show_submit)
    )


def record_answer(answer):
    """Record user's answer"""
    print(Fore.BLUE + "recorded user answer =", answer, Fore.RESET)
    user_answers[current_question] = answer


def next_question():
    """Move to next question"""
    global current_question
    current_question += 1
    return update_question()


def previous_question():
    """Move to previous question"""
    global current_question
    current_question -= 1
    return update_question()


def submit_quiz():
    """Submit quiz and calculate results"""
    import gradio as gr
    correct_count = 0
    results = []
    
    for i, (question_data, user_answer) in enumerate(zip(quiz_data, user_answers)):
        correct_answer = question_data["answer"]
        is_correct = True if correct_answer in user_answer else False
        if is_correct:
            correct_count += 1
            
        result_text = f"Question {i+1}: {'✅ Correct' if is_correct else '❌ Incorrect'}\n"
        result_text += f"Q: {question_data['question']}\n"
        result_text += f"Your answer: {user_answer if user_answer is not None else 'No answer'}\n"
        if not is_correct:
            # Find the correct choice text
            correct_choice_text = ""
            for choice in question_data['choices']:
                if question_data['answer'] in choice:
                    correct_choice_text = choice
                    break
            result_text += f"Correct answer: {correct_choice_text}\n"
            result_text += f"Explanation: {question_data['explanation']}\n"
        result_text += "---\n"
        results.append(result_text)
    
    score_text = f"Your score: {correct_count}/{len(quiz_data)} ({int((correct_count/len(quiz_data))*100)}%)\n\n"
    full_result = score_text + "".join(results)
    
    return (
        gr.update(visible=True),
        full_result,
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False)
    )

