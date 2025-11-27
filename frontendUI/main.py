"""
Main application file combining Study Buddy and Quiz tabs.
"""
import gradio as gr
from config import MAX_FILES, MAX_FILE_SIZE_GB, MAX_PAGES_PER_FILE
from study_buddy_ui import (
    generate_curriculum, handle_file_upload, mark_topic_complete,
    check_answers, send_message, submit_feedback,
    clear_feedback, check_quiz_unlock, submit_username, go_to_next_chapter
)
from quiz_ui import init_quiz, record_answer, next_question, previous_question, submit_quiz
from colorama import Fore
import os, sys, json

def check_and_init_quiz(completed_topics, username):
    """Check if quiz should be unlocked and initialize it if so"""
    import gradio as gr
    
    # Check if quiz should be unlocked
    lock_msg_update, quiz_col_update = check_quiz_unlock(completed_topics, username)
    
    # Determine if quiz is unlocked by checking if any SUBTOPIC is completed
    # (subtopics have "↳" prefix)
    is_quiz_unlocked = False
    if completed_topics:
        for completed in completed_topics:
            if completed.strip().startswith("↳") or "  ↳" in completed:
                is_quiz_unlocked = True
                break
    
    # If quiz is now unlocked (visible), initialize it
    if is_quiz_unlocked and username:
        try:
            quiz_init_outputs = init_quiz(username)
            return (lock_msg_update, quiz_col_update) + quiz_init_outputs
        except Exception as e:
            print(Fore.RED + f"Error initializing quiz: {e}", Fore.RESET)
            # Return empty/default values if initialization fails
            return (lock_msg_update, quiz_col_update, "", "", gr.Radio(choices=[]), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False))
    else:
        # Quiz is still locked, return default empty values
        return (lock_msg_update, quiz_col_update, "", "", gr.Radio(choices=[]), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False))
import yaml

# Custom CSS
CUSTOM_CSS = """
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
/* Style for subtopic buttons - smaller and lighter */
.subtopic-btn {
    font-size: 0.85em !important;
    padding: 6px 12px !important;
    margin-left: 20px !important;
}
/* Style for completed topics - green background */
.completed-topic {
    background-color: #2ecc71 !important;
    color: white !important;
    border: 2px solid #27ae60 !important;
}
.completed-topic:hover {
    background-color: #27ae60 !important;
}
/* Style for locked/disabled buttons */
button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
    background-color: #cccccc !important;
}

/* Make tabs more responsive/clickable */
.tab-nav button {
    padding: 12px 24px !important;
    cursor: pointer !important;
}

/* Username modal overlay */
.username-modal {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    width: 100vw !important;
    height: 100vh !important;
    background: rgba(0, 0, 0, 0.6) !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    z-index: 9999 !important;
}

.modal-content {
    background: white !important;
    padding: 25px 30px !important;
    border-radius: 20px !important;
    box-shadow: 0 15px 50px rgba(0, 0, 0, 0.5) !important;
    width: 420px !important;
    height: 220px !important;
    max-width: 420px !important;
    max-height: 220px !important;
    text-align: center !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: space-between !important;
    box-sizing: border-box !important;
    overflow: hidden !important;
}

.modal-content > * {
    overflow: hidden !important;
}

.modal-content h3 {
    margin: 0 !important;
    padding: 0 !important;
    font-size: 1.3em !important;
    line-height: 1 !important;
}

.modal-content p {
    margin: 0 !important;
    padding: 0 !important;
    font-size: 0.9em !important;
    line-height: 1.3 !important;
    color: #666 !important;
}

.modal-content .gradio-textbox {
    margin: 15px 0 !important;
    flex-shrink: 0 !important;
}

/* Target the outer block container */
.modal-content .block,
.modal-content .svelte-1svsvh2 {
    border: none !important;
    background: transparent !important;
    padding: 0 !important;
    box-shadow: none !important;
}

/* Target the label with border */
.modal-content .show_textbox_border,
.modal-content label.container {
    border: none !important;
    background: transparent !important;
    padding: 0 !important;
    box-shadow: none !important;
}

/* Target the input container */
.modal-content .input-container {
    border: none !important;
    background: transparent !important;
    padding: 0 !important;
    box-shadow: none !important;
}

.modal-content .gradio-textbox label > span {
    display: none !important;
}

.modal-content input[type="text"] {
    text-align: center !important;
    font-size: 1em !important;
    padding: 12px 15px !important;
    border-radius: 8px !important;
    border: 2px solid #d0d0d0 !important;
    width: 100% !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.08) !important;
    background: white !important;
    transition: all 0.2s ease !important;
    display: block !important;
}

.modal-content input[type="text"]:focus {
    border-color: #ff6b35 !important;
    background: white !important;
    outline: none !important;
    box-shadow: 0 0 0 4px rgba(255, 107, 53, 0.12) !important;
}

.modal-content button {
    width: 100% !important;
    margin: 0 !important;
    padding: 11px !important;
    font-size: 1em !important;
    flex-shrink: 0 !important;
    border-radius: 8px !important;
}

/* Username corner display */
.username-corner {
    position: fixed !important;
    top: 15px !important;
    right: 15px !important;
    z-index: 1000 !important;
    pointer-events: none !important;
}

.username-corner > div {
    pointer-events: auto !important;
}
"""
f=open("/workspace/docker-compose.yml","r")
yaml_f=yaml.safe_load(f)
global mnt_folder
mnt_folder=yaml_f["services"]["agenticta"]["volumes"][-1].split(":")[-1]

def create_app():
    """Create and configure the Gradio application"""
    with gr.Blocks(title="Study Assistant") as demo:
        
        # Username state and components
        username_state = gr.State("")
        print(Fore.CYAN + "Initialized username_state" , username_state, Fore.RESET)
        # Username modal popup (overlay)
        username_modal = gr.Column(visible=True, elem_classes=["username-modal"])
        with username_modal:
            with gr.Column(elem_classes=["modal-content"]):
                gr.HTML('<h3 style="margin: 0; padding: 0;">Welcome</h3><p style="margin: 8px 0 0 0; padding: 0; font-size: 0.9em;">Enter a username below</p>')
                username_input = gr.Textbox(
                    label="",
                    placeholder="Username",
                    max_lines=1,
                    show_label=False
                )
                username_submit_btn = gr.Button("Start", variant="primary")
        
        # Username display (small corner box - doesn't affect layout)
        username_display = gr.HTML(
            value="",
            visible=False,
            elem_classes=["username-corner"]
        )
        
        with gr.Tab("Study Buddy"):
            gr.Markdown("# 📚 AI Study Assistant")
            
            # State variables
            current_chapter = gr.State("")
            total_questions_state = gr.State(0)
            unlocked_topics_state = gr.State([])
            expanded_topics_state = gr.State([])
            completed_topics_state = gr.State([])
            
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("## Upload Study Material")
                    file_upload = gr.File(
                        label="Upload PDF Files",
                        file_types=[".pdf"],
                        file_count="multiple"
                    )
                    gr.Markdown(
                        f"""
                        **Upload Requirements:**
                        - Maximum {MAX_FILES} PDF files
                        - Maximum {MAX_FILE_SIZE_GB}GB per file
                        - Maximum {MAX_PAGES_PER_FILE} pages per file
                        """
                    )
                    validation_status = gr.Textbox(
                        label="Upload Status",
                        interactive=False,
                        visible=True,
                        value=""
                    )
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
                        chapter_checkboxes = []
                        for i in range(10):  # Max 10 chapters
                            with gr.Row():
                                checkbox = gr.Checkbox(visible=False, label="", scale=1, elem_classes=["chapter-checkbox"])
                                btn = gr.Button(visible=False, elem_classes=["chapter-btn"], scale=9)
                                chapter_checkboxes.append(checkbox)
                                chapter_buttons.append(btn)
                    
                    # Study Material section - shows current subtopic material
                    study_material_section = gr.Accordion("📚 Current Study Material", open=True, visible=False)
                    with study_material_section:
                        study_material_display = gr.Markdown(
                            value="Study material will appear here after generating curriculum.",
                            elem_classes=["study-material"]
                        )
                    
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
                        
                        with gr.Row():
                            submit_btn = gr.Button("Submit Answers", visible=False, scale=1)
                            next_chapter_btn = gr.Button("Next Chapter", visible=False, interactive=False, scale=1)
                    
                    # Chat section
                    gr.Markdown("## Study Buddy Chat")
                    chatbot = gr.Chatbot(height=300, type='messages')
                    with gr.Row():
                        msg = gr.Textbox(
                            label="Message",
                            placeholder="Ask your study buddy anything...",
                            scale=8
                        )
                        send_btn = gr.Button("Send", scale=1)
                    
                    # Feedback section
                    feedback_accordion = gr.Accordion("💬 Chatbot Feedback", open=False, visible=True)
                    with feedback_accordion:
                        gr.Markdown("### Help us improve the Study Buddy!\nShare your thoughts about the chatbot's responses and suggestions.")
                        feedback_input = gr.Textbox(
                            label="Your Feedback",
                            placeholder="Tell us what you think about the chatbot's responses...",
                            lines=3,
                            max_lines=5
                        )
                        with gr.Row():
                            feedback_submit_btn = gr.Button("Submit Feedback", variant="primary", scale=1)
                            feedback_clear_btn = gr.Button("Clear", scale=1)
                        feedback_status = gr.Textbox(
                            label="Status",
                            value="",
                            interactive=False,
                            visible=False
                        )
                    
                    # Summary section
                    summary_accordion = gr.Accordion("Summary", open=False, visible=True)
                    with summary_accordion:
                        gr.Markdown("Complete a chapter quiz to see your results summary here.")
            
            # Event handling for Study Buddy tab
            # Validate files on upload
            file_upload.change(
                handle_file_upload,
                inputs=[file_upload, username_state],
                outputs=[validation_status]
            )
            
            generate_outputs = [curriculum_col] + chapter_checkboxes + chapter_buttons + [study_material_section, study_material_display, unlocked_topics_state, expanded_topics_state, completed_topics_state]
            generate_btn.click(
                generate_curriculum,
                inputs=[file_upload, validation_status, username_state, buddy_pref],
                outputs=generate_outputs
            )
            
            # Buttons are now non-clickable (interactive=False), so no click handlers needed
            
            # Connect checkboxes for marking completion
            # Outputs: checkboxes + buttons + study_material_display + quiz accordion + quiz components + states + submit button
            checkbox_outputs = (chapter_checkboxes + chapter_buttons + 
                              [study_material_display, quiz_accordion, score_counter, current_chapter, total_questions_state] +
                              quiz_components + 
                              [unlocked_topics_state, expanded_topics_state, completed_topics_state, submit_btn, next_chapter_btn])
            
            # Helper function to create checkbox handler with correct index
            def make_checkbox_handler(idx):
                def handler(checkbox_value, unlocked, expanded, completed, username, *buttons):
                    return mark_topic_complete(checkbox_value, idx, unlocked, expanded, completed, username, *buttons)
                return handler
            
            for i, checkbox in enumerate(chapter_checkboxes):
                checkbox.change(
                    make_checkbox_handler(i),
                    inputs=[checkbox, unlocked_topics_state, expanded_topics_state, completed_topics_state, username_state] + chapter_buttons,
                    outputs=checkbox_outputs
                )
            
            # Submit answers
            submit_inputs = [current_chapter, total_questions_state, unlocked_topics_state, expanded_topics_state, completed_topics_state, username_state] + quiz_components[::2]
            submit_outputs = [score_counter] + quiz_components[1::2] + chapter_checkboxes + chapter_buttons + [unlocked_topics_state, expanded_topics_state, completed_topics_state, submit_btn, next_chapter_btn]
            submit_btn.click(
                check_answers,
                inputs=submit_inputs,
                outputs=submit_outputs
            )
            
            # Next Chapter button - loads the next chapter into UI after passing quiz
            next_chapter_inputs = [unlocked_topics_state, expanded_topics_state, completed_topics_state, username_state]
            next_chapter_outputs = chapter_checkboxes + chapter_buttons + [study_material_section, study_material_display, unlocked_topics_state, expanded_topics_state, completed_topics_state, submit_btn, next_chapter_btn]
            next_chapter_btn.click(
                go_to_next_chapter,
                inputs=next_chapter_inputs,
                outputs=next_chapter_outputs
            )
            
            # Chat functionality
            msg.submit(send_message, [msg, chatbot, buddy_pref, username_state], [msg, chatbot])
            send_btn.click(send_message, [msg, chatbot, buddy_pref, username_state], [msg, chatbot])
            
            # Feedback functionality
            feedback_submit_btn.click(
                submit_feedback,
                inputs=[feedback_input],
                outputs=[feedback_status, feedback_input]
            )
            feedback_clear_btn.click(
                clear_feedback,
                inputs=[],
                outputs=[feedback_input, feedback_status]
            )
        
        with gr.Tab("Quiz"):
            gr.Markdown("# Quiz Application")
            
            # Lock message (shown when no full topics completed)
            quiz_lock_message = gr.Markdown(
                """
                ## 🔒 Quiz Tab Locked
                
                Complete a **full topic** in the Study Buddy tab to unlock this quiz section!
                
                **How to unlock:**
                - ✅ Complete a topic without subtopics (like "Cell Structure and Function"), OR
                - ✅ Complete ALL subtopics under a main topic (like all 5 subtopics under "Introduction to Biology")
                - Each question requires 100% score to proceed
                - Once a full topic is completed, this tab will unlock automatically
                """,
                visible=True
            )
            
            # Quiz content (hidden when locked)
            quiz_content_col = gr.Column(visible=False)
            with quiz_content_col:
                # State tracking
                progress = gr.Textbox(label="Progress", interactive=False)
                question_display = gr.Textbox(label="Question", interactive=False)
                choices = gr.Radio(choices=[], label="Choices", interactive=True)
                choices.change(record_answer, inputs=choices, outputs=[])
                
                with gr.Row():
                    prev_btn = gr.Button("Previous", visible=False)
                    next_btn = gr.Button("Next", visible=False)
                    submit_btn_quiz = gr.Button("Submit Quiz", visible=False)
                
                result_display = gr.Textbox(label="Results", interactive=False, visible=False)
                
                # Event handlers for Quiz tab
                next_btn.click(next_question, None, [progress, question_display, choices, prev_btn, next_btn, submit_btn_quiz])
                prev_btn.click(previous_question, None, [progress, question_display, choices, prev_btn, next_btn, submit_btn_quiz])
                submit_btn_quiz.click(submit_quiz, None, [result_display, result_display, progress, question_display, choices, submit_btn_quiz])
                
                # Initialize quiz when user accesses the quiz tab (after curriculum is generated)
                # Removed demo.load to avoid initialization errors for first-time users
        
        # Username submission event handler
        username_submit_btn.click(
            submit_username,
            inputs=[username_input],
            outputs=[username_modal, username_display, username_state]
        )
        
        # Allow Enter key to submit username
        username_input.submit(
            submit_username,
            inputs=[username_input],
            outputs=[username_modal, username_display, username_state]
        )
        
        # Update Quiz tab visibility when completed_topics changes and initialize quiz if unlocked
        completed_topics_state.change(
            check_and_init_quiz,
            inputs=[completed_topics_state, username_state],
            outputs=[quiz_lock_message, quiz_content_col, progress, question_display, choices, prev_btn, next_btn, submit_btn_quiz]
        )
    
    demo.css = CUSTOM_CSS
    return demo


if __name__ == "__main__":
    app = create_app()
    app.launch(
        server_name="0.0.0.0",  # Allow access from outside the container
        server_port=7860,
        share=False,
        show_error=True
    )

