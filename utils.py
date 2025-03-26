import spacy
from transformers import pipeline
import re
import base64
from bs4 import BeautifulSoup
from plyer import notification
from dateutil import parser
import json

# Load spaCy model for NER
nlp = spacy.load("en_core_web_sm")

# Load summarization pipeline with BART model
try:
    summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
except RuntimeError as e:
    print(f"Error loading summarizer: {e}. Falling back to basic summarization.")
    summarizer = None

def get_email_body(payload):
    """Extract the email body from the payload."""
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
            elif part['mimeType'] == 'text/html' and 'data' in part['body']:
                html = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                soup = BeautifulSoup(html, 'html.parser')
                return soup.get_text()
        return ''  # Return empty string if no text parts are found
    else:
        if 'body' in payload and 'data' in payload['body']:
            return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
        return ''  # Return empty string if no body data

def is_job_related(email_text):
    """Check if the email is job-related, including appointment letters."""
    job_keywords = [
        'job', 'career', 'position', 'hiring', 'apply', 'interview', 'opportunity',
        'joining', 'role', 'manager', 'team', 'start', 'welcome', 'appoint', 'employment'
    ]
    email_lower = email_text.lower()
    result = any(keyword in email_lower for keyword in job_keywords)
    print(f"Job-related check: {result} (Text: {email_lower[:100]}...)")
    return result

def extract_key_info(email_text):
    """Extract key job-related information, including joining date for appointment letters."""
    doc = nlp(email_text)
    
    entities = {
        "company": [ent.text for ent in doc.ents if ent.label_ == "ORG"],
        "location": [ent.text for ent in doc.ents if ent.label_ == "GPE"]
    }
    
    # Job title patterns for appointment letters
    job_title_patterns = [
        r'appoint you as\s*([^\n]+)',  # "appoint you as Sr. Developer"
        r'position\s*:\s*([^\n]+)',
        r'joining as\s*([^\n]+)'
    ]
    for pattern in job_title_patterns:
        match = re.search(pattern, email_text, re.IGNORECASE)
        if match:
            entities["job_title"] = match.group(1).strip()
            break
    
    # Salary (CTC) pattern
    salary_pattern = r'(?:CTC|salary|compensation)\s*(?:will be|of)?\s*₹?\$?([\d,]+(?:-\d+,\d+)?)'
    salary_match = re.search(salary_pattern, email_text, re.IGNORECASE)
    if salary_match:
        entities["salary"] = salary_match.group(1)
    
    # Job type
    job_type_keywords = ['full-time', 'part-time', 'remote', 'contract', 'internship', 'work at home']
    for keyword in job_type_keywords:
        if keyword in email_text.lower():
            entities["job_type"] = keyword
            break
    
    # Application link (if present)
    link_pattern = r'(https?://[^\s]+)'
    link_match = re.search(link_pattern, email_text)
    if link_match:
        entities["application_link"] = link_match.group(0)
    
    # Joining date (or deadline)
    date_patterns = [
        r'join(?:ing)?\s*(?:us\s*)?on\s*([^\n]+)',
        r'deadline\s*:\s*([^\n]+)',
        r'apply by\s*([^\n]+)',
        r'submit by\s*([^\n]+)'
    ]
    for pattern in date_patterns:
        match = re.search(pattern, email_text, re.IGNORECASE)
        if match:
            date_str = match.group(1).strip()
            try:
                key_date = parser.parse(date_str, fuzzy=True)
                entities["key_date"] = key_date
                break
            except ValueError:
                continue
    
    return entities

def summarize_email(email_text):
    """Summarize the email, tailored for appointment letters and job opportunities."""
    if not email_text.strip():
        return "No content to summarize.", None
    
    key_info = extract_key_info(email_text)
    
    if summarizer:
        summary = summarizer(email_text, max_length=150, min_length=50, do_sample=False)[0]['summary_text']
    else:
        summary = email_text[:200] + '...' if len(email_text) > 200 else email_text
    
    structured_summary = "Job Opportunity Summary:\n"
    if "job_title" in key_info:
        structured_summary += f"Title: {key_info['job_title']}\n"
    if "company" in key_info and key_info["company"]:
        structured_summary += f"Company: {', '.join(key_info['company'])}\n"
    if "location" in key_info and key_info["location"]:
        structured_summary += f"Location: {', '.join(key_info['location'])}\n"
    if "key_date" in key_info:
        structured_summary += f"Joining Date: {key_info['key_date'].strftime('%Y-%m-%d')}\n"
    if "salary" in key_info:
        structured_summary += f"Salary: ₹{key_info['salary']}\n"  # Assuming INR for this sample
    if "job_type" in key_info:
        structured_summary += f"Type: {key_info['job_type'].capitalize()}\n"
    if "application_link" in key_info:
        structured_summary += f"Apply Here: {key_info['application_link']}\n"
    structured_summary += f"\nDetails: {summary}"
    
    key_date = key_info.get("key_date")
    return structured_summary, key_date

def save_notification(title, message):
    """Save the notification to a file for later access."""
    with open('notifications.txt', 'a') as f:
        f.write(f"{title}: {message}\n")

def send_notification(title, full_message):
    """Send a desktop notification and save the full message."""
    MAX_MESSAGE_LENGTH = 256
    if len(full_message) > MAX_MESSAGE_LENGTH:
        truncated = ""
        for line in full_message.split('\n'):
            if any(x in line for x in ["Title:", "Company:", "Joining Date:", "Apply Here:"]):
                truncated += line + "\n"
            if len(truncated) >= MAX_MESSAGE_LENGTH - 20:
                break
        message = truncated.strip() + "..." if truncated else full_message[:MAX_MESSAGE_LENGTH - 3] + "..."
    else:
        message = full_message
    
    notification.notify(
        title=title,
        message=message,
        app_name='Job Email Filter',
        timeout=10
    )
    save_notification(title, full_message)

def load_notification_schedule():
    """Load the notification schedule from a JSON file."""
    try:
        with open('notification_schedule.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_notification_schedule(schedule):
    """Save the notification schedule to a JSON file."""
    with open('notification_schedule.json', 'w') as f:
        json.dump(schedule, f)