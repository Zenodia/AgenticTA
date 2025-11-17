import requests
import os
import ast
import json
import sys
from colorama import Fore
from nodes import init_user_storage,user_exists,load_user_state, update_and_save_user_state, move_to_next_chapter, update_subtopic_status,add_quiz_to_subtopic, build_next_chapter, run_for_first_time_user
import asyncio
from vault import get_secret
import re
from dotenv import load_dotenv
load_dotenv()
# Initialize the new LLM client
 
# Legacy LangChain LLM for fallback chains only

astra_api_key = get_secret('ASTRA_TOKEN')

def inference_call(system_prompt, user_prompt):    
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {astra_api_key}',
    }
    
    json_data = {
        'model': 'nvidia/llama-3.3-nemotron-super-49b-v1',
        'messages': [
            {"role": "system", "content": system_prompt},
            {'role': 'user','content': user_prompt},
        ],        
    "temperature":0.6,
    "top_p":0.95,
    "max_tokens":36000,
    'stream': False,
    }
    
    response = requests.post(
        'https://datarobot.prd.astra.nvidia.com/api/v2/deployments/688e407ed8a8e0543e6d9b80/chat/completions',
        headers=headers,
        json=json_data,
    )
    
    return response 


def get_quiz(title, document_summary, chunk_text, additional_instruction):
        
    user_prompt_str = QUESTION_GENERATION_USER_PROMPT.format(
                    title=title,
                    document_summary=document_summary,
                    text_chunk=chunk_text,
                    additional_instructions=additional_instruction,
                )
    
    try:
        response = inference_call(QUESTION_GENERATION_SYSTEM_PROMPT_MULTI, user_prompt_str)
        output_d=response.json()
        output_str= output_d['choices'][0]["message"]["content"]
    except Exception as exc:
        output_str = "an error happened during inference call, error msg = \n" + str(exc) 
    
    return output_str 

               

QUESTION_GENERATION_SYSTEM_PROMPT_HEADER = """## Your Role

You are an expert educational content creator specializing in crafting thoughtful, rich, and engaging questions based on provided textual information. Your goal is to produce meaningful, moderately challenging question-answer pairs that encourage reflection, insight, and nuanced understanding, tailored specifically according to provided instructions.

## Input Structure

Your input consists of:

<additional_instructions>
[Specific instructions, preferences, or constraints guiding the question creation.]
</additional_instructions>

<title>
[Document title]
</title>

<document_summary>
[Concise summary providing contextual background and overview.]
</document_summary>

<text_chunk>
[The single text segment to analyze.]
</text_chunk>

## Primary Objective

Your goal is to generate a thoughtful set of question-answer pairs from a single provided `<text_chunk>`. Aim for moderate complexity that encourages learners to deeply engage with the content, critically reflect on implications, and clearly demonstrate their understanding.

### Context Fields:

- `<title>`: Contextualizes the content.
- `<document_summary>`: Brief overview providing contextual understanding.
- `<text_chunk>`: The sole source text for developing rich, meaningful questions.
- `<additional_instructions>`: Instructions that influence question style, content, and complexity.

## Analysis Phase

Conduct careful analysis within `<document_analysis>` XML tags, following these steps:

1. **Thoughtful Content Examination**
   - Carefully analyze the given text_chunk, identifying central ideas, nuanced themes, and significant relationships within it.

2. **Concept Exploration**
   - Consider implicit assumptions, subtle details, underlying theories, and potential applications of the provided information.

3. **Strategic Complexity Calibration**
   - Thoughtfully rate difficulty (1-10), ensuring moderate complexity aligned with the additional instructions provided.

4. **Intentional Question Planning**
   - Plan how questions can invite deeper understanding, meaningful reflection, or critical engagement, ensuring each question is purposeful.

## Additional Instructions for Handling Irrelevant or Bogus Information

### Identification and Ignoring of Irrelevant Information:

- **Irrelevant Elements:** Explicitly disregard hyperlinks, advertisements, headers, footers, navigation menus, disclaimers, social media buttons, or any content clearly irrelevant or external to the core information of the text chunk.
- **Bogus Information:** Detect and exclude any information that appears nonsensical or disconnected from the primary subject matter.

### Decision Criteria for Question Generation:

- **Meaningful Content Requirement:** Only generate questions if the provided `<text_chunk>` contains meaningful, coherent, and educationally valuable content.
- **Complete Irrelevance:** If the entire `<text_chunk>` consists exclusively of irrelevant, promotional, web navigation, footer, header, or non-informational text, explicitly state this in your analysis and do NOT produce any question-answer pairs.

### Documentation in Analysis:

- Clearly document the rationale in the `<document_analysis>` tags when identifying irrelevant or bogus content, explaining your reasons for exclusion or inclusion decisions.
- Briefly justify any decision NOT to generate questions due to irrelevance or poor quality content.


## Question Generation Guidelines

### Encouraged Question Characteristics:

- **Thoughtful Engagement**: Prioritize creating questions that inspire deeper thought and nuanced consideration.
- **Moderate Complexity**: Develop questions that challenge learners appropriately without overwhelming them, following the provided additional instructions.
- **Self-contained Clarity**: Questions and answers should contain sufficient context, clearly understandable independently of external references.
- **Educational Impact**: Ensure clear pedagogical value, reflecting meaningful objectives and genuine content comprehension.
- **Conversational Tone**: Formulate engaging, natural, and realistic questions appropriate to the instructional guidelines.

### Permitted Question Types:

- Analytical
- Application-based
- Clarification
- Counterfactual
- Conceptual
- True-False
- Factual
- Open-ended
- False-premise
- Edge-case

(You do not need to use every question type, only those naturally fitting the content and instructions.)"""
QUESTION_GENERATION_SYSTEM_PROMPT_OUTPUT = """## Output Structure

Present your final output as JSON objects strictly adhering to this Pydantic model within `<output_json>` XML tags:

```python
class QuestionAnswerPair(BaseModel):
    thought_process: str # Clear, detailed rationale for selecting question and analysis approach
    question_type: Literal["analytical", "application-based", "clarification",
                           "counterfactual", "conceptual", "true-false",
                           "factual", "open-ended", "false-premise", "edge-case"]
    question: str
    answer: str
    estimated_difficulty: int  # 1-10, calibrated according to additional instructions
    citations: List[str]  # Direct quotes from the text_chunk supporting the answer
```

## Output Format

Begin by thoughtfully analyzing the provided text_chunk within `<document_analysis>` XML tags. Then present the resulting JSON-formatted QuestionAnswerPairs clearly within `<output_json>` XML tags."""

QUESTION_GENERATION_SYSTEM_PROMPT_OUTPUT_MULTI = """## Output Structure

Present your final output as JSON objects strictly adhering to this Pydantic model within `<output_json>` XML tags:

```python
class MultipleChoiceQuestion(BaseModel):
    thought_process: str  # Rationale for the question and distractors
    question_type: Literal["analytical", "application-based", "clarification",
                           "counterfactual", "conceptual", "true-false",
                           "factual", "false-premise", "edge-case"]
    question: str
    answer: str  # One of "A", "B", "C", or "D"
    choices: List[str]  # Must contain exactly 4 items
    estimated_difficulty: int  # 1-10
    citations: List[str]  # Direct support from the text_chunk
```

## Output Format

Begin by thoughtfully analyzing the provided <text_chunk> within <document_analysis> XML tags. Your analysis should identify the key concepts, technical details, and reasoning opportunities found in the text.

Then present the resulting multiple-choice questions as valid JSON objects within <output_json> tags, strictly following this structure:

<document_analysis>
- Key concept: ...
- Important facts: ...
- Reasoning opportunities: ...
</document_analysis>

<output_json>
[
  {
    "thought_process": "This question targets understanding of how the chunk explains the purpose of semantic chunking in document processing. Distractors are phrased using near-synonyms or subtle distortions of the true concept.",
    "question_type": "conceptual",
    "question": "What is the primary reason for using semantic chunking in document preprocessing?",
    "choices": [
      "(A) To compress the document into fewer tokens.",
      "(B) To group content based on semantic similarity and token limits.",
      "(C) To translate the text into multiple languages.",
      "(D) To strip metadata and formatting from the input file."
    ],
    "answer": "B",
    "estimated_difficulty": 6,
    "citations": ["Semantic chunking partitions documents into coherent segments based on semantic similarity and token length constraints."]
  },
  ...
]
</output_json>"""


QUESTION_GENERATION_SYSTEM_PROMPT_OUTPUT_MULTI = """## Output Structure

Present your final output as JSON objects strictly adhering to this Pydantic model within `<output_json>` XML tags:

```python
class MultipleChoiceQuestion(BaseModel):
    thought_process: str  # Rationale for the question and distractors
    question_type: Literal["analytical", "application-based", "clarification",
                           "counterfactual", "conceptual", "true-false",
                           "factual", "false-premise", "edge-case"]
    question: str
    answer: str  # One of "A", "B", "C", or "D"
    choices: List[str]  # Must contain exactly 4 items
    estimated_difficulty: int  # 1-10
    citations: List[str]  # Direct support from the text_chunk
```

## Output Format

Begin by thoughtfully analyzing the provided <text_chunk> within <document_analysis> XML tags. Your analysis should identify the key concepts, technical details, and reasoning opportunities found in the text.

Then present the resulting multiple-choice questions as valid JSON objects within <output_json> tags, strictly following this structure:

<document_analysis>
- Key concept: ...
- Important facts: ...
- Reasoning opportunities: ...
</document_analysis>

<output_json>
[
  {
    "thought_process": "This question targets understanding of how the chunk explains the purpose of semantic chunking in document processing. Distractors are phrased using near-synonyms or subtle distortions of the true concept.",
    "question_type": "conceptual",
    "question": "What is the primary reason for using semantic chunking in document preprocessing?",
    "choices": [
      "(A) To compress the document into fewer tokens.",
      "(B) To group content based on semantic similarity and token limits.",
      "(C) To translate the text into multiple languages.",
      "(D) To strip metadata and formatting from the input file."
    ],
    "answer": "B",
    "estimated_difficulty": 6,
    "citations": ["Semantic chunking partitions documents into coherent segments based on semantic similarity and token length constraints."]
  },
  ...
]
</output_json>"""

QUESTION_GENERATION_SYSTEM_PROMPT_OUTPUT_MULTI = """## Output Structure

Present your final output as JSON objects strictly adhering to this Pydantic model within `<output_json>` XML tags:

```python
class MultipleChoiceQuestion(BaseModel):
    thought_process: str  # Rationale for the question and distractors
    question_type: Literal["analytical", "application-based", "clarification",
                           "counterfactual", "conceptual", "true-false",
                           "factual", "false-premise", "edge-case"]
    question: str
    answer: str  # One of "A", "B", "C", or "D"
    choices: List[str]  # Must contain exactly 4 items
    estimated_difficulty: int  # 1-10
    citations: List[str]  # Direct support from the text_chunk
```

## Output Format

Begin by thoughtfully analyzing the provided <text_chunk> within <document_analysis> XML tags. Your analysis should identify the key concepts, technical details, and reasoning opportunities found in the text.

Then present the resulting multiple-choice questions as valid JSON objects within <output_json> tags, strictly following this structure:

<document_analysis>
- Key concept: ...
- Important facts: ...
- Reasoning opportunities: ...
</document_analysis>

<output_json>
[
  {
    "thought_process": "This question targets understanding of how the chunk explains the purpose of semantic chunking in document processing. Distractors are phrased using near-synonyms or subtle distortions of the true concept.",
    "question_type": "conceptual",
    "question": "What is the primary reason for using semantic chunking in document preprocessing?",
    "choices": [
      "(A) To compress the document into fewer tokens.",
      "(B) To group content based on semantic similarity and token limits.",
      "(C) To translate the text into multiple languages.",
      "(D) To strip metadata and formatting from the input file."
    ],
    "answer": "B",
    "estimated_difficulty": 6,
    "citations": ["Semantic chunking partitions documents into coherent segments based on semantic similarity and token length constraints."]
  },
  ...
]
</output_json>"""

QUESTION_GENERATION_SYSTEM_PROMPT_FOOTER = """## Important Notes
- Strive to generate questions that inspire genuine curiosity, reflection, and thoughtful engagement.
- Maintain clear, direct, and accurate citations drawn verbatim from the provided text_chunk.
- Ensure complexity and depth reflect thoughtful moderation as guided by the additional instructions.
- Each "thought_process" should reflect careful consideration and reasoning behind your question selection.
- Ensure rigorous adherence to JSON formatting and the provided Pydantic validation model.
- When generating questions, NEVER include phrases like 'as per the text,' 'according to the document,' or any similar explicit references. Questions should inherently integrate content naturally and stand independently without explicit references to the source material
"""

QUESTION_GENERATION_SYSTEM_PROMPT = (
    QUESTION_GENERATION_SYSTEM_PROMPT_HEADER
    + QUESTION_GENERATION_SYSTEM_PROMPT_OUTPUT
    + QUESTION_GENERATION_SYSTEM_PROMPT_FOOTER
)

QUESTION_GENERATION_SYSTEM_PROMPT_MULTI = (
    QUESTION_GENERATION_SYSTEM_PROMPT_HEADER
    + QUESTION_GENERATION_SYSTEM_PROMPT_OUTPUT_MULTI
    + QUESTION_GENERATION_SYSTEM_PROMPT_FOOTER
)


QUESTION_GENERATION_USER_PROMPT = """<title>
{title}
</title>

<document_summary>
{document_summary}
</document_summary>

<text_chunk>
{text_chunk}
</text_chunk>

<additional_instructions>
{additional_instructions}
</additional_instructions>"""


def quiz_output_parser(output_str: str) -> list[dict]:
    # Find the start of the JSON content
    start_marker = '<output_json>'
    if start_marker not in output_str:
        print("No <output_json> marker found")
        return []
    
    start_idx = output_str.index(start_marker) + len(start_marker)
    json_str = output_str[start_idx:]
    
    # Find the end of the JSON content if closing tag exists
    end_marker = '</output_json>'
    if end_marker in json_str:
        print("Found closing tag")
        end_idx = json_str.index(end_marker)
        json_str = json_str[:end_idx]
    else:
        print("No closing tag found, using remaining string")
    
    # Clean up markdown code fences and whitespace
    json_str = json_str.strip()
    json_str = json_str.replace('```json', '').replace('```', '')
    json_str = json_str.strip()
    
    # Remove inline notes that break JSON (e.g., *Note: ...)
    # This regex removes text like: ] *Note: ...* or ] *Note: ...*
    json_str = re.sub(r'\]\s*\*Note:.*?\*', ']', json_str)
    
    # Parse the JSON
    try:
        quizes_ls = json.loads(json_str)
        if isinstance(quizes_ls, list):
            return quizes_ls
        else:
            print("Parsed JSON is not a list")
            return []
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}")
        print(f"JSON string preview (first 500 chars):\n{json_str[:500]}")
        print(f"\nJSON string preview (around error position):")
        error_pos = e.pos if hasattr(e, 'pos') else 2364
        start = max(0, error_pos - 100)
        end = min(len(json_str), error_pos + 100)
        print(f"{json_str[start:end]}")
        return []



if __name__ == "__main__":
    user_id="babe"
    save_to="/workspace/mnt/"
    init_user_storage(save_to, user_id)
    user_state = load_user_state(user_id)
    print("----"*10)
    print(type(user_state), user_state.keys())
    print(type(user_state["curriculum"][0]), user_state["curriculum"][0].keys())
    c=user_state["curriculum"][0]
    print(type(c["active_chapter"]), type(c["study_plan"]), type(c["status"]))
    print(" ----> currently active_chapter is = \n ----------------")
    active_chapter=c["active_chapter"]
    print(f"active_chapter = {active_chapter.number}:{active_chapter.name}")

    print("\n Pick the 1st sub topic as a test ")
    title=active_chapter.name
    summary=active_chapter.sub_topics[0].sub_topic
    text_chunk=active_chapter.sub_topics[0].study_material
    quizes_ls= get_quiz(title, summary, text_chunk, "")
    quizzes_d_ls=quiz_output_parser(quizes_ls)
    print("\n"*3)
    #print(type(quizes_ls),type(quizes_ls[0]), len(quizes_ls), quizes_ls)
    #print(Fore.YELLOW + "\n Generated Quiz from SubTopics", '\n'.join([f"{subtopic.number}:{subtopic.sub_topic}" for subtopic in active_chapter.sub_topics]))
    print("==="*10 , ">")
    print(type(quizzes_d_ls),type(quizzes_d_ls[0]), len(quizzes_d_ls), quizzes_d_ls)

    for quiz in quizzes_d_ls:
        print("\n"+"--"*10)
        print(f"Q: {quiz['question']}\nA: {quiz['answer']}\nType: {quiz['question_type']}\nDifficulty: {quiz['estimated_difficulty']}\nCitations: {quiz['citations']}\nThought Process: {quiz['thought_process']}")
    print("\n"*3)
    updated_user = asyncio.run(add_quiz_to_subtopic(
        user_id=user_id,
        save_to=save_to,
        subtopic_number=0,
        quiz=quizzes_d_ls
    ))
    print(type(updated_user))

    