import requests
import base64
import argparse
import os, re

def is_base64(s):
    if not s or not isinstance(s, str):
        return False
    try:
        # Try decoding with validation
        decoded = base64.b64decode(s, validate=True)
        # Re-encode and compare without padding
        encoded = base64.b64encode(decoded).decode('utf-8')
        return encoded.rstrip('=') == s.rstrip('=')
    except Exception:
        return False

def is_base64_regex(s):
    pattern = re.compile(r'^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)?$')
    return bool(pattern.match(s))

# Encode local image as base64
def img2base64_str(img_file_loc):
    with open(img_file_loc, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode()
        return image_base64

def audio2base64_str(audio_path):

    with open(audio_path, 'rb') as f:
        binary_audio = f.read()
        base64_audio = base64.b64encode(binary_audio).decode('utf-8')

    #print(base64_audio)
    return base64_audio


def query_qwen_vllm_served(query, image_file_loc, sys_prompt, audio_path):
    url = "http://vllm:8901/v1/chat/completions"    
    print(is_base64_regex(image_file_loc),is_base64(image_file_loc)) 
    if is_base64_regex(image_file_loc) or is_base64(image_file_loc):        
        base64_img_str=image_file_loc 
        already_base_64_img_flag=True
        img_file_exist_flag = True
        
    else:
        
        base64_img_str=None 
        already_base_64_img_flag=False
        img_file_exist_flag = os.path.exists(image_file_loc) if image_file_loc is not None else False # Ensure image file exists
        print("image_file_exist_flag=", img_file_exist_flag)
        
    audio_file_exist_flag = os.path.exists(audio_path) if audio_path is not None else False  # Ensure audio file exists
    
    if audio_file_exist_flag and img_file_exist_flag :        
        if already_base_64_img_flag:
            image_base64=base64_img_str
        else:
            image_base64=img2base64_str(image_file_loc)
        audio_base64_str=audio2base64_str(audio_path)
        payload = {    
            "messages": [
                {
                    "role": "system",
                    "content": [
                        {"type": "text", "text": sys_prompt}
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": query},
                        # Use base64 for local media (server must accept it)
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                        {"type": "input_audio", "input_audio": {"data": f"{audio_base64_str}", "format": "wav"}},

                    ]
                }
            ]
        }
    elif img_file_exist_flag: 
        if already_base_64_img_flag:
            image_base64=base64_img_str
        else:
            image_base64=img2base64_str(image_file_loc)
        payload = {    
            "messages": [
                {
                    "role": "system",
                    "content": [
                        {"type": "text", "text": sys_prompt}
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": query},
                        # Use base64 for local media (server must accept it)
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},                        

                    ]
                }
            ]
        }
    elif audio_file_exist_flag:
        audio_base64_str=audio2base64_str(audio_path)
        payload = {    
            "messages": [
                {
                    "role": "system",
                    "content": [
                        {"type": "text", "text": sys_prompt}
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": query},
                        # Use base64 for local media (server must accept it)                    
                        {"type": "input_audio", "input_audio": {"data": f"{audio_base64_str}", "format": "wav"}},

                    ]
                }
            ]
        }
    else: # only text query 
        payload = {    
            "messages": [
                {
                    "role": "system",
                    "content": [
                        {"type": "text", "text": sys_prompt}
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": query},                      

                    ]
                }
            ]
        }
    response = requests.post(url, json=payload)
    print("response=\n", response)
    output=response.json()["choices"][0]["message"]["content"]
    return output



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
                        prog='ProgramName',
                        description='What the program does',
                        epilog='Text at the bottom of help')
    parser.add_argument('--query', help='user inpute query')
    parser.add_argument('--img_loc', help='location of the image file', default=None)
    parser.add_argument('--audio_loc', help='location of the audio file', default=None)
    parser.add_argument('-system_prompt', help='system_prompt', default="You are a study buddy who will go above and beyound to help user to learn about a topic he/she is interested in.")    

    args = parser.parse_args()
    query=args.query
    image_file_loc=args.img_loc if args.img_loc is not None else None
    audio_path = args.audio_loc if args.audio_loc is not None else None
    sys_prompt=args.system_prompt
    output=query_qwen_vllm_served(query,image_file_loc, sys_prompt, audio_path)
    print(output)
