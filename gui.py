import tkinter as tk
from tkinter import scrolledtext

def load_notifications():
    """Load notifications from the file."""
    try:
        with open('notifications.txt', 'r') as f:
            return f.read()
    except FileNotFoundError:
        return "No notifications found."

def refresh(text_area):
    """Refresh the text area with the latest notifications."""
    text_area.delete('1.0', tk.END)
    text_area.insert(tk.END, load_notifications())

def start_viewer():
    """Start the Tkinter GUI for viewing notifications."""
    root = tk.Tk()
    root.title("Notification Viewer")

    text_area = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=60, height=20)
    text_area.pack(padx=10, pady=10)

    refresh_button = tk.Button(root, text="Refresh", command=lambda: refresh(text_area))
    refresh_button.pack(pady=5)

    refresh(text_area)
    root.mainloop()