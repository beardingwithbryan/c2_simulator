# Modern C2 Simulator



This tool can simulate C2 traffic over Slack, DNS over HTTPS and QUIC. This tool is designed strictly for educational purposes, security research, and authorized penetration testing.

---

## Usage

```
pip3 isntall -r requirements.txt
python3 main.py -p <platform>
```
---



## Prerequisites

Before installing, ensure your system meets the following requirements:

| Component | Requirement |
| :--- | :--- |
| **Language** | Python 3.11+ |
| **Dependencies** | Slack Channel, Domain, Internet-Facing Server |

---


## Setup

### Slack

#### Server-Side Setup

Firstly, you will have to create a Slack workspace and one channel for sending commands, and one channel for receiving commands.

1. Create a new app at https://api.slack.com from scratch. 
2. Under Oauth and Permissions, give the app channells:history, channels:read, chat:write, files:write and groups:read permissions
3. Install the app to your workspace and grab the Bot User OAuth Token
4. Add the bot to both your sending and receiving chanels


#### Client-Side Setup

Populate the Slack block of the YAML file with your channel IDs (which can be found in the URL when you visit them) and the OAuth token along with the app's name.
```

slack: 
  oauth_token: "xoxb-..."
  send_channel: "C0..."
  recv_channel: "C0..."
  bot_name: "<bot name>"
  ```

### DNS over HTTPS

#### Server-Side Setup

Firstly, you will need to have a domain and an Internet-facing server that allows traffic on TCP and UDP on port 53. Setup below will use example.com as its domain.

1. Create an A record that points to ns1.example.com. 
2. Create an NS record pointing to the IP address of your server.
3. If you would like to use encryption, you will need to generate a 256 bit key in hex format. It should be a total of 64 hex characters.

You will need to run the dns_server.py script found in the servers folder.

```
python3 dns_server.py -d example.com #Runs without encryption
python3 dns_server.py -d example.com -k <key> #Runs with encryption
```


#### Client-Side Setup

Populate the Slack block of the YAML file with your domain and your key (optional).
```

dns: 
  domainn: "example.com"
  key: "a8cb35..."
  
```  

### QUIC

#### Server-Side Setup

Firstly, you will need to have a domain and an Internet-facing server that allows traffic on TCP on your chosen port (default 443). You will also need to generate a valid SSL certificate and private key.

1. Create an A record that points to your server's IP address. 


You will need to run the quic_server.py script found in the servers folder.

```
python3 quic_server.py -d 0.0.0.0 -p 443 -cert /path/to/cert -key /path/to/key 

```


#### Client-Side Setup

Populate the Slack block of the YAML file with your domain and your key (optional).
```

quic:
  domain: "example.com"
```
