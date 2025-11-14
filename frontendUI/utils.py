"""
Utility functions for the Study Assistant application.
"""
import os
import pandas as pd
import re
from colorama import Fore
from config import MAX_FILES, MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_GB, MAX_PAGES_PER_FILE

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None


def validate_pdf_files(files):
    """
    Validate uploaded PDF files against size, count, and page limits.
    Returns (is_valid, error_message)
    """
    if files is None or len(files) == 0:
        return True, ""
    
    # Check number of files
    if len(files) > MAX_FILES:
        return False, f"❌ Error: You can upload a maximum of {MAX_FILES} files. You uploaded {len(files)} files."
    
    # Check each file
    for idx, file in enumerate(files):
        file_path = file.name if hasattr(file, 'name') else file
        
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE_BYTES:
            file_size_gb = file_size / (1024 * 1024 * 1024)
            return False, f"❌ Error: File '{os.path.basename(file_path)}' is {file_size_gb:.2f}GB. Maximum file size is {MAX_FILE_SIZE_GB}GB."
        
        # Check if it's a PDF
        if not file_path.lower().endswith('.pdf'):
            return False, f"❌ Error: File '{os.path.basename(file_path)}' is not a PDF file."
        
        # Check page count if PyPDF2 is available
        if PdfReader is not None:
            try:
                pdf_reader = PdfReader(file_path)
                num_pages = len(pdf_reader.pages)
                if num_pages > MAX_PAGES_PER_FILE:
                    return False, f"❌ Error: File '{os.path.basename(file_path)}' has {num_pages} pages. Maximum allowed is {MAX_PAGES_PER_FILE} pages per file."
            except Exception as e:
                return False, f"❌ Error: Unable to read PDF file '{os.path.basename(file_path)}': {str(e)}"
    
    return True, f"✅ {len(files)} file(s) uploaded successfully!"


def double_check(choice):
    """Helper function to validate choice format"""
    print(choice)
    if '(A)' in choice and '(B)' in choice and '(C)' in choice and '(D)' in choice and '(E)' in choice:
        print("A-E")
        choices = get_choices(choice)
    elif '(A)' in choice and '(B)' in choice and '(C)' in choice and '(D)' in choice:
        print("A-D")
        choices = get_choices(choice)
    elif '(A)' in choice and '(B)' in choice and '(C)' in choice:
        print("A-C")
        choices = get_choices(choice)
    elif '(A)' in choice and '(B)' in choice:
        print("A-B")
        choices = get_choices(choice)
    elif '(A)' in choice:
        print("just A")
        choices = choice
    elif '(B)' in choice:
        print("just B")
        choices = choice
    elif '(C)' in choice:
        print("just C")
        choices = choice
    elif '(D)' in choice:
        print("just D")
        choices = choice
    elif '(E)' in choice:
        print("just E")
        choices = choice
    else:
        print(Fore.RED + "error=\n", choice)
    return choices


def get_choices(row_nr=None, df=None, choice_str=None):
    """
    Extract choices from a DataFrame row or choice string.
    Can be called with either (row_nr, df) or just choice_str.
    """
    if choice_str is None and row_nr is not None and df is not None:
        choice_str = df.iloc[row_nr, 5]
    
    choice_text = str(choice_str).replace('[', '').replace(']', '').replace("'", "").replace('"', '').strip()
    lines = [line.strip() for line in choice_text.split('\n') if line.strip()]
    
    all_choices = []
    for line in lines:
        # Handle the specific format where choices are concatenated
        # Replace ')''(' with ') ' (' to separate them properly
        fixed = re.sub(r"\)'\s*'\s*\(", ")' '(", line)
        
        # Clean up
        cleaned = ""
        for char in fixed:
            if char not in "[]":
                cleaned += char
        
        # Remove extra quotes and normalize
        cleaned = cleaned.replace("'", " ").replace("\\", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        
        # Extract choices
        pattern = r"\([A-E]\)[^(\]]*"
        matches = re.findall(pattern, cleaned)
        
        result = [match.strip() for match in matches if match.strip()]
        final_result = [double_check(item) for item in result]
        
        if isinstance(final_result, list):
            all_choices.extend([ch.strip() for ch in final_result if ch.strip()])
        else:
            all_choices.append(str(final_result).strip())
    
    if len(all_choices) < 4:
        print(Fore.RED + "extracted=", '\n', len(all_choices), all_choices, Fore.RESET)
    
    return all_choices


def get_question(row_nr, df):
    """
    Extract question from a pandas DataFrame row.
    """
    question = df.iloc[row_nr, 3].replace('[', '').replace(']', '').replace("'", "")
    return question


def get_answer(row_nr, df):
    """
    Extract answer from a pandas DataFrame row.
    """
    answer = df.iloc[row_nr, 4].replace('[', '').replace(']', '').replace("'", "")
    answer_to_index = {"A": '(A)', "B": '(B)', "C": '(C)', "D": '(D)', "E": '(E)'}
    if answer in answer_to_index.keys():
        answer_idx = answer_to_index[answer]
    else:
        print(answer, "not in answer to index")
    
    return answer_idx


def get_citation_as_explain(row_nr, df):
    """
    Extract citation/explanation from a pandas DataFrame row.
    """
    explanation = df.iloc[row_nr, -1].replace('[', '').replace(']', '').replace("'", "")
    return explanation

