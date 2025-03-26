import schedule
import time
from datetime import datetime, timedelta
from auth import get_gmail_service
from utils import (get_email_body, is_job_related, summarize_email, send_notification, 
                  load_notification_schedule, save_notification_schedule)
from gui import start_viewer
import threading

def process_emails():
    """Process new emails and schedule notifications for key dates."""
    service = get_gmail_service()
    try:
        with open('last_run.txt', 'r') as f:
            last_run = f.read().strip()
    except FileNotFoundError:
        last_run = None
    
    query = f'after:{last_run}' if last_run else ''
    results = service.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])
    
    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
        email_text = get_email_body(msg_data['payload'])
        if is_job_related(email_text):
            summary, key_date = summarize_email(email_text)
            send_notification('New Job Email', summary)
            if key_date:
                schedule_key_date_notifications(key_date, summary)
    
    with open('last_run.txt', 'w') as f:
        f.write(str(int(time.time())))

def schedule_key_date_notifications(key_date, summary):
    """Schedule notifications for one week and one day before the key date."""
    today = datetime.now().date()
    week_before = (key_date - timedelta(days=7)).date()
    day_before = (key_date - timedelta(days=1)).date()
    
    week_message = f"Reminder: Joining date for job is in one week.\n{summary}"
    day_message = f"Reminder: Joining date for job is tomorrow.\n{summary}"
    
    schedule_list = load_notification_schedule()
    
    if week_before >= today:
        schedule_list.append({"date": week_before.strftime('%Y-%m-%d'), "message": week_message})
    if day_before >= today:
        schedule_list.append({"date": day_before.strftime('%Y-%m-%d'), "message": day_message})
    
    save_notification_schedule(schedule_list)

def check_deadline_notifications():
    """Check and send notifications if their scheduled date has arrived."""
    today = datetime.now().date()
    schedule_list = load_notification_schedule()
    new_schedule = []
    for entry in schedule_list:
        notification_date = datetime.strptime(entry["date"], '%Y-%m-%d').date()
        if notification_date <= today:
            send_notification("Joining Date Reminder", entry["message"])
        else:
            new_schedule.append(entry)
    save_notification_schedule(new_schedule)

def run_tasks():
    """Run scheduled tasks in a background thread."""
    schedule.every(10).minutes.do(process_emails)
    schedule.every(10).minutes.do(check_deadline_notifications)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    task_thread = threading.Thread(target=run_tasks)
    task_thread.daemon = True
    task_thread.start()

    start_viewer()