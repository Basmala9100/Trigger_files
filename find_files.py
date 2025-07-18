# watchdod to monitor the folder for file system events like file creation, modification, and deletion
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
# smtp for sending email notifications(simple email transfer protocol alert system)
import smtplib
# help for formatting email messages like sub, body, and attachments
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import time
from dotenv import load_dotenv
# keep track with the changes if the file is modified
import difflib
import json
import logging


load_dotenv()  # Load environment variables from .env file
# Configuration for email notifications
email_address = os.getenv('email_sender')
email_password = os.getenv('email_password')
to_email_address = os.getenv('email_receiver')

log_file_name = 'file_monitor.log'
# for avoiding multi-emails for modified files
last_modified_files = {}
modification_threshold = 5

file_content = {}


# Set up logging
logging.basicConfig(
    filename=log_file_name,
    filemode='a',
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.getLogger().addHandler(logging.StreamHandler())


def is_text_file(file_path):
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
        return all(c < 128 or c in b'\n\r\t' for c in chunk)  # Check if all bytes are ASCII
    except Exception as e:
        return False


def read_file_content(file_path):
    try:
        if file_path.endswith('.json'):
            with open(file_path, 'r', encoding='utf-8') as f:   
                content = json.load(f)
                content_text = json.dumps(content, indent=4)
                return content_text.splitlines()
        elif is_text_file(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read().splitlines()
        else:
            return None
    except Exception as e:            
        #print(f"[Error] Failed to read file {file_path}: {e}")
        logging.error(f"[Error] Failed to read file {file_path}: {e}")
        return []
    
    
# FindFilesHandler class to handle file system events
class FindFilesHandler(FileSystemEventHandler):
    def __init__(self, directory):
        self.directory = directory
        self.initialize_content()  # Initialize content of files in the directory
        
        
    def initialize_content(self):
        """Initialize the content of files in the directory."""
        count = 0
        for file_name in os.listdir(self.directory):
            if file_name == log_file_name:
                continue  # Skip log file itself

            file_path = os.path.join(self.directory, file_name)
            if os.path.isfile(file_path):
                content = read_file_content(file_path)
                file_content[file_name] = content
                last_modified_files[file_name] = time.time()
                count += 1

        logging.info(f"Initialized content for {count} files in {self.directory}.")
    
    
    def send_email(self, subject, body):
        try:
            msg = MIMEMultipart()
            msg['From'] = email_address
            msg['To'] = to_email_address
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(email_address, email_password)
                server.send_message(msg)

            logging.info(f"[Notification] Email sent: {subject}")
        except Exception as e:
            logging.error(f"[Error] Failed to send email: {e}")

    def process_file(self, event, action):
        if event.is_directory:
            return

        file_name = os.path.basename(event.src_path)
        if file_name == log_file_name:
            return  # Avoid processing the log file

        file_path = event.src_path

        if action == 'created':
            logging.info(f"[Alert] New file created: {file_name}")
            content = read_file_content(file_path)
            file_content[file_name] = content
            last_modified_files[file_name] = time.time()

            if content is None:
                body = f"A new binary file '{file_name}' has been created."
            else:
                body = f"A new text file '{file_name}' has been created."

            self.send_email(f"File Created: {file_name}", body)

        elif action == 'modified':
            current_time = time.time()
            last_time = last_modified_files.get(file_name, 0)

            if current_time - last_time <= modification_threshold:
                logging.info(f"[Info] File {file_name} modified again within threshold, skipping.")
                return

            new_content = read_file_content(file_path)
            old_content = file_content.get(file_name, None)

            if new_content is None:
                logging.info(f"[Binary] {file_name} was modified.")
                self.send_email(f"Binary File Modified: {file_name}", f"{file_name} was modified (binary file, no diff).")
            else:
                if old_content is None:
                    diff_content = '\n'.join(new_content)
                else:
                    diff = difflib.unified_diff(old_content, new_content, fromfile='before_' + file_name, tofile='after_' + file_name, lineterm='')
                    diff_content = '\n'.join(list(diff))

                logging.info(f"[DIFF] Changes in {file_name}:\n{diff_content}")
                self.send_email(f"File Modified: {file_name}", f"Changes in {file_name}:\n\n{diff_content}")

            file_content[file_name] = new_content
            last_modified_files[file_name] = current_time

        elif action == 'deleted':
            logging.info(f"[Alert] File deleted: {file_name}")
            self.send_email(f"File Deleted: {file_name}", f"The file {file_name} has been deleted.")
            file_content.pop(file_name, None)
            last_modified_files.pop(file_name, None)

    def on_created(self, event):
        self.process_file(event, 'created')

    def on_modified(self, event):
        self.process_file(event, 'modified')

    def on_deleted(self, event):
        self.process_file(event, 'deleted')

def monitor_directory(directory):
    event_handler = FindFilesHandler(directory)
    observer = Observer()
    observer.schedule(event_handler, directory, recursive=False)
    observer.start()
    logging.info(f"[Monitoring] Started monitoring {directory}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logging.info("[Monitoring] Stopped monitoring")
    observer.join()

if __name__ == "__main__":
    directory_to_monitor = r"D:\internship_paysky25\Triggers_file"
    monitor_directory(directory_to_monitor)