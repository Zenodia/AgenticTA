import gradio as gr
import random
from typing import List, Tuple
from colorama import Fore
import os 
import shutil
import time
from states import Chapter, StudyPlan, Curriculum, User, GlobalState, Status
from states import save_user_to_file, load_user_from_file
from states import convert_to_json_safe
from test_orchestrator import run_for_user
# Sample data for demonstration
SAMPLE_CURRICULUM = [
    "Introduction to Biology",
    "Cell Structure and Function",
    "Genetics and Heredity",
    "Evolution and Natural Selection",
    "Ecology and Ecosystems"
]

SAMPLE_QUIZ_DATA = {
    "Introduction to Biology": [
        {
            "question": "What is the basic unit of life?",
            "choices": ["Atom", "Molecule", "Cell", "Organ", "Tissue"],
            "answer": "Cell",
            "explanation": "Cells are the basic structural and functional units of all living organisms."
        },
        {
            "question": "Which of these is NOT a characteristic of living things?",
            "choices": ["Reproduction", "Metabolism", "Response to stimuli", "Photosynthesis", "Growth"],
            "answer": "Photosynthesis",
            "explanation": "While photosynthesis is important for plants, not all living things perform it (e.g., animals)."
        }
    ],
    "Cell Structure and Function": [
        {
            "question": "Which organelle is known as the 'powerhouse of the cell'?",
            "choices": ["Nucleus", "Ribosome", "Mitochondria", "Endoplasmic Reticulum", "Golgi Apparatus"],
            "answer": "Mitochondria",
            "explanation": "Mitochondria produce ATP, the cell's energy currency, through cellular respiration."
        }
    ]
}

def generate_curriculum(file_obj):
    """Generate curriculum from uploaded PDF or use sample data"""
    print(Fore.CYAN + "file_objs = \n", type(file_obj), file_obj)

    if file_obj:       
        
        # In a real app, you would extract content from PDF here
        # For demo, we'll just return sample curriculum
        new_ls=[shutil.copy(f, "/workspace/mnt/pdfs/") for f in file_obj]
        print(Fore.CYAN + "new_ls =\n", new_ls)
        print(os.listdir("/workspace/mnt/pdfs/"), Fore.RESET)
        u=User(
        user_id="user",
        study_buddy_preference="someone who has patience, a good sense of humor, can make boring subject fun.", 
        study_buddy_name="ollie", 
        study_buddy_persona=None,
        )
        uploaded_pdf_loc="/workspace/mnt/pdfs/"
        save_to="/workspace/mnt/"
        g = run_for_user(u,uploaded_pdf_loc,save_to)
        #print(Fore.YELLOW + "gstate=\n", type(g),g)
        _study_plan=g["user"]["curriculum"]["study_plan"]
        print(type(_study_plan), _study_plan)
        if isinstance(_study_plan,dict):
            study_plan = _study_plan["study_plan"]
        else:
            study_plan=_study_plan.study_plan
        print("---"*10)
        print("\n\n",type(study_plan), study_plan)
        if isinstance(study_plan[0], dict):
            curriculum=[f"Chapter {str(c["number"])}: Extracted Topic {c["name"].split(':')[1]}" for c in study_plan]
        else:
            curriculum=[f"Chapter {str(c.number)}: Extracted Topic {c.name.split(':')[1]}" for c in study_plan]
        #curriculum = [f"Chapter {i+1}: Extracted Topic {i+1}" for i in range(5)]
        print(curriculum)
    else:
        curriculum = SAMPLE_CURRICULUM.copy()
    
    # Create chapter buttons (10 max)
    outputs = [gr.Column(visible=True)]
    for i in range(10):
        if i < len(curriculum):
            outputs.append(gr.Button(curriculum[i], visible=True))
        else:
            outputs.append(gr.Button(visible=False))
    return outputs

def mark_chapter_complete(chapter_name, progress=gr.Progress()):
    """Mark a chapter as complete and prepare quiz"""
    progress(0.3, desc="Preparing quiz...")
    
    # Get quiz data for the chapter
    quiz_questions = SAMPLE_QUIZ_DATA.get(chapter_name, [])
    
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
                visible=True
            )
            explanation = gr.Markdown(f"**Explanation:** {q['explanation']}", visible=False)
        else:
            radio = gr.Radio(visible=False)
            explanation = gr.Markdown(visible=False)
        quiz_components.extend([radio, explanation])
    
    total_questions = len(quiz_questions)
    counter_text = f"0/{total_questions}"
    
    return [
        gr.Accordion(visible=True),
        gr.Textbox(value=counter_text, visible=True),
        chapter_name,  # Current chapter name
        total_questions  # Total questions
    ] + quiz_components

def check_answers(chapter_name, total_questions, *answers):
    """Check answers and update score"""
    # Get quiz data for the chapter
    quiz_questions = SAMPLE_QUIZ_DATA.get(chapter_name, [])
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
    
    return [gr.Textbox(value=score_text, visible=True)] + explanations_visibility

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
    history.append((message, bot_response))
    return "", history

with gr.Blocks(title="Study Assistant") as demo:
    gr.Markdown("# 📚 AI Study Assistant")
    
    # State variables
    current_chapter = gr.State("")
    total_questions_state = gr.State(0)
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## Upload Study Material")
            file_upload = gr.File(label="Upload PDF", file_types=[".pdf"], file_count="multiple")
            generate_btn = gr.Button("Generate Curriculum")
            
            gr.Markdown("## Study Preferences")
            buddy_pref = gr.Textbox(
                label="Preferred Study Buddy Characteristics",
                placeholder="E.g., encouraging, knowledgeable in science..."
            )
            
        with gr.Column(scale=2):
            # Curriculum section
            curriculum_col = gr.Column(visible=False)
            with curriculum_col:
                gr.Markdown("## Study Curriculum")
                chapter_buttons = []
                for i in range(10):  # Max 10 chapters
                    btn = gr.Button(visible=False, elem_classes=["chapter-btn"])
                    chapter_buttons.append(btn)
            
            # Quiz section
            quiz_accordion = gr.Accordion("Quiz", visible=False)
            with quiz_accordion:
                with gr.Row():
                    score_counter = gr.Textbox(
                        label="Score",
                        value="0/0",
                        interactive=False,
                        visible=False
                    )
                
                # Quiz questions will be dynamically added here
                quiz_components = []
                for _ in range(10):  # Max 10 questions
                    radio = gr.Radio(visible=False)
                    explanation = gr.Markdown(visible=False)
                    quiz_components.extend([radio, explanation])
                
                submit_btn = gr.Button("Submit Answers", visible=True)
            
            # Chat section
            gr.Markdown("## Study Buddy Chat")
            chatbot = gr.Chatbot(height=300)
            with gr.Row():
                msg = gr.Textbox(
                    label="Message",
                    placeholder="Ask your study buddy anything...",
                    scale=8
                )
                send_btn = gr.Button("Send", scale=1)
            
            # Summary section
            summary_accordion = gr.Accordion("Summary", open=False, visible=True)
            with summary_accordion:
                gr.Markdown("Complete a chapter quiz to see your results summary here.")
    
    # Event handling
    generate_outputs = [curriculum_col] + chapter_buttons
    generate_btn.click(
        generate_curriculum,
        inputs=[file_upload],
        outputs=generate_outputs
    )
    
    # Connect chapter buttons
    mark_outputs = [
        quiz_accordion,
        score_counter,
        current_chapter,
        total_questions_state
    ] + quiz_components
    
    for btn in chapter_buttons:
        btn.click(
            mark_chapter_complete,
            inputs=[btn],
            outputs=mark_outputs
        )
    
    # Submit answers
    submit_inputs = [current_chapter, total_questions_state] + quiz_components[::2]  # Only radio components
    submit_btn.click(
        check_answers,
        inputs=submit_inputs,
        outputs=[score_counter] + quiz_components[1::2]  # Only explanation components
    )
    
    # Chat functionality
    msg.submit(send_message, [msg, chatbot, buddy_pref], [msg, chatbot])
    send_btn.click(send_message, [msg, chatbot, buddy_pref], [msg, chatbot])

# Custom CSS for better UI
demo.css = """
.chapter-btn {
    margin: 5px 0;
    text-align: left;
}
.gradio-button.primary {
    background-color: #3498db;
    border: none;
}
.gradio-button.secondary {
    background-color: #2ecc71;
    border: none;
}
"""

if __name__ == "__main__":
    demo.launch()
