"""
Calendar Assistant module for creating calendar events with AI assistance.
Extracted from gradio_calendar_app.py to integrate into the main Study Assistant UI.
"""
import os
import tempfile
import hashlib
import json
from datetime import datetime, timedelta
import zoneinfo
from icalendar import Calendar, Event, vCalAddress, Alarm
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.messages import SystemMessage, HumanMessage

# ===========================
# Calendar Management Functions
# ===========================

def create_calendar_event(summary, start_datetime, duration_hours, 
                         description="", location="", organizer_email="",
                         organizer_name="", reminder_hours=1):
    """Create a single calendar event and return as ICS file"""
    
    cal = Calendar()
    cal.add('prodid', '-//NVIDIA AI Calendar Creator//EN')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    
    event = Event()
    event.add('summary', summary)
    
    # Ensure datetime has timezone (UTC+1)
    if start_datetime.tzinfo is None:
        start_datetime = start_datetime.replace(tzinfo=zoneinfo.ZoneInfo("Europe/Paris"))
    
    event.add('dtstart', start_datetime)
    
    # Calculate end time
    end_datetime = start_datetime + timedelta(hours=duration_hours)
    event.add('dtend', end_datetime)
    
    # Add dtstamp (current time in UTC for compatibility)
    event.add('dtstamp', datetime.now(zoneinfo.ZoneInfo("UTC")))
    
    # Simple UID using timestamp and hash
    uid_base = f"{summary}{start_datetime.isoformat()}"
    uid_hash = hashlib.md5(uid_base.encode()).hexdigest()
    event['uid'] = uid_hash
    
    if location:
        event.add('location', location)
    
    if description:
        event.add('description', description)
    
    if organizer_email:
        organizer = vCalAddress(f'mailto:{organizer_email}')
        if organizer_name:
            organizer.params['CN'] = organizer_name
        event['organizer'] = organizer
    
    # Add reminder alarm if requested
    if reminder_hours > 0:
        alarm = Alarm()
        alarm.add('action', 'DISPLAY')
        alarm.add('trigger', timedelta(hours=-reminder_hours))
        alarm.add('description', f'Reminder: {summary}')
        event.add_component(alarm)
    
    cal.add_component(event)
    
    return cal.to_ical()

def parse_datetime_from_inputs(date_str, time_str):
    """Parse date and time strings into datetime object"""
    try:
        # Handle different date formats
        if 'T' in date_str:  # ISO format
            dt = datetime.fromisoformat(date_str.replace('Z', '+01:00'))
        else:
            # Try parsing date
            dt = datetime.strptime(date_str, '%Y-%m-%d')
        
        # Add time if provided
        if time_str:
            if ':' in time_str:
                hour, minute = map(int, time_str.split(':'))
                dt = dt.replace(hour=hour, minute=minute)
        
        # Add timezone (UTC+1)
        dt = dt.replace(tzinfo=zoneinfo.ZoneInfo("Europe/Paris"))  # UTC+1 (CET/CEST)
        return dt
    except Exception as e:
        # Fallback to current time with UTC+1
        return datetime.now(zoneinfo.ZoneInfo("Europe/Paris"))

# ===========================
# AI Integration Functions
# ===========================

def parse_event_with_ai(user_input, api_key):
    """Use NVIDIA AI to parse natural language into event parameters"""
    
    if not api_key:
        return None, "Please provide NVIDIA API key"
    
    try:
        llm = ChatNVIDIA(
            model="meta/llama-3.1-405b-instruct",
            api_key=api_key,
            temperature=0.3,
            max_completion_tokens=36000
        )
        
        current_date = datetime.now(zoneinfo.ZoneInfo("Europe/Paris")).strftime("%Y-%m-%d")
        system_prompt = f"""You are a calendar assistant. Parse user requests into structured event data.
Return ONLY a valid JSON object with these fields:
{{
    "summary": "Event title",
    "description": "Event description",
    "start_date": "YYYY-MM-DD",
    "start_time": "HH:MM",
    "duration_hours": float,
    "location": "Location (optional)",
    "organizer_email": "email@example.com (optional)",
    "organizer_name": "Name (optional)",
    "reminder_hours": 1
}}

Current date for reference: {current_date}
Note: All times are in UTC+1 timezone (Central European Time)

Example input: "Schedule a team meeting tomorrow at 2pm for 2 hours about Q4 planning"
Example output: {{"summary": "Team Meeting - Q4 Planning", "start_date": "2024-11-29", "start_time": "14:00", "duration_hours": 2.0, "description": "Quarterly planning discussion", "reminder_hours": 1}}

IMPORTANT: Return ONLY the JSON object, no explanations.
"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input)
        ]
        
        response = llm.invoke(messages)
        response_text = response.content.strip()
        
        # Extract JSON
        if '```json' in response_text:
            start = response_text.find('```json') + 7
            end = response_text.find('```', start)
            response_text = response_text[start:end].strip()
        elif '```' in response_text:
            start = response_text.find('```') + 3
            end = response_text.find('```', start)
            response_text = response_text[start:end].strip()
        
        event_data = json.loads(response_text)
        return event_data, None
        
    except Exception as e:
        return None, f"Error parsing with AI: {str(e)}"

# ===========================
# Gradio Interface Functions
# ===========================

def create_event_with_ai(ai_input):
    """Create event using AI parsing"""
    
    if not ai_input:
        return None, "❌ Please describe the event you want to create", ""
    
    # Get API key from environment
    api_key = os.environ.get('NVIDIA_API_KEY')
    if not api_key:
        return None, "❌ NVIDIA_API_KEY not found in environment variables. Please set it first.", ""
    
    try:
        # Parse with AI
        event_data, error = parse_event_with_ai(ai_input, api_key)
        
        if error:
            return None, f"❌ {error}", ""
        
        # Parse datetime
        date_str = event_data['start_date']
        time_str = event_data['start_time']
        start_dt = parse_datetime_from_inputs(date_str, time_str)
        
        # Create ICS
        ics_content = create_calendar_event(
            summary=event_data['summary'],
            start_datetime=start_dt,
            duration_hours=float(event_data['duration_hours']),
            description=event_data.get('description', ''),
            location=event_data.get('location', ''),
            organizer_email=event_data.get('organizer_email', ''),
            organizer_name=event_data.get('organizer_name', ''),
            reminder_hours=float(event_data.get('reminder_hours', 1))
        )
        
        # Save to temp file with descriptive name
        event_name_safe = "".join(c for c in event_data['summary'] if c.isalnum() or c in (' ', '-', '_')).strip()[:50]
        filename = f"event_{event_name_safe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ics"
        temp_file = tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.ics', prefix='')
        temp_file.write(ics_content)
        temp_file.close()
        
        # Format success message
        success_msg = f"""
✅ **Event Parsed and Created Successfully!**

🤖 **AI Interpretation:**
```json
{json.dumps(event_data, indent=2)}
```

📅 **Event Details:**
- **Title:** {event_data['summary']}
- **Date & Time:** {start_dt.strftime('%Y-%m-%d %H:%M')} (UTC+1)
- **Duration:** {event_data['duration_hours']} hours
- **Location:** {event_data.get('location', 'Not specified')}
- **Description:** {event_data.get('description', 'Not specified')}

📥 **How to Add to Your Calendar:**

**Option 1 - Double-click (Easiest):**
1. Click the **Download** button below
2. Find the downloaded `.ics` file (usually in Downloads folder)
3. **Double-click** the file - it should open in Outlook/Calendar automatically!

**Option 2 - Right-click:**
1. Right-click the downloaded `.ics` file
2. Select **"Open with"** → Choose Outlook or your calendar app
3. Confirm to add the event

**Option 3 - Drag & Drop:**
- Drag the `.ics` file directly into Outlook calendar view

💡 **Tip:** The file is named `{filename}` for easy identification!
"""
        
        # Preview content
        preview = ics_content.decode('utf-8')
        
        return temp_file.name, success_msg, preview
        
    except Exception as e:
        return None, f"❌ Error creating event with AI: {str(e)}", ""

