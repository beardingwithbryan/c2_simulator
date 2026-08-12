import time
import c2_client_slack
import c2_client_dns
import c2_client_quic
import argparse
import sys
from factory import load_platform_config
from handlers import HANDLERS

c2_types = ["slack", "dns", "quic"]

parser = argparse.ArgumentParser(description="Client C2 Traffic Simulator")
parser.add_argument("-p", "--platform", required=True, help="Type of C2 traffic to use. E.g. Slack, Graph, etc.", choices=c2_types)
args = parser.parse_args()

EXECUTION_DISPATCH = {
    "slack": c2_client_slack.run_slack_tasks,
    "dns": c2_client_dns.run_dns_tasks,
    "quic": c2_client_quic.run_quic_tasks
}


    
def execute_platform_actions(platform: str, params: dict):

    action_func = EXECUTION_DISPATCH.get(platform.lower())
    
    if not action_func:
        raise ValueError(f"No execution logic defined for platform: '{platform}'")
    
    # Execute the platform-specific logic
    action_func(params)

def main():        
    try:
        # 1. Load typed config via factory
        config_obj = load_platform_config(args.platform)
        
        # 2. Get handler function and retrieve the dictionary of parameters
        handler = HANDLERS[args.platform.lower()]
        params_dict = handler(config_obj)

        execute_platform_actions(args.platform, params_dict)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

