"""
Quiz tab UI components and logic.
"""
import pandas as pd
import os
import random
from colorama import Fore
from utils import get_question, get_answer, get_citation_as_explain, get_choices

# Global variables to track state
current_question = 0
user_answers = []
quiz_data = []
df = None


def load_quiz_data():
    """Load quiz data from CSV files"""
    global df, quiz_data
    csv_dir = './sample_data'
    files = [f for f in os.listdir(csv_dir) if f.endswith('.csv') and not f.startswith("summary_")]
    f = random.choice(files)
    df = pd.read_csv(os.path.join(csv_dir, f))
    df = df.sample(n=2, replace=True)
    n = len(df)
    quiz_data = []
    for i in range(n):
        item = {
            "question": get_question(i, df),
            "choices": get_choices(i, df),
            "answer": get_answer(i, df),
            "explanation": get_citation_as_explain(i, df)
        }
        quiz_data.append(item)


def init_quiz():
    """Initialize quiz state"""
    global current_question, user_answers
    load_quiz_data()
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

