import yaml
from models import SlackConfig, DNSConfig, QUICConfig

CONFIG_FACTORIES = {
    "slack": lambda data: SlackConfig(
        oauth_token=data["oauth_token"],
        send_channel=data["send_channel"],
        recv_channel=data.get("recv_channel"),
        bot_name=data.get("bot_name")
    ),
    "dns": lambda data: DNSConfig(
        domain=data["domain"],
        key=data["key"],
    ),
    "quic": lambda data: QUICConfig(
        domain=data["domain"],
        
    )

}

def load_platform_config(platform):
    with open("c2_params.yaml", "r", encoding="utf-8") as f:
        full_yaml = yaml.safe_load(f)
    
    raw_block = full_yaml.get(platform)
    if not raw_block:
        raise ValueError(f"No configuration block found for platform '{platform}' in config file")
    
    factory = CONFIG_FACTORIES.get(platform.lower())
    if not factory:
        raise ValueError(f"Unsupported platform: '{platform}'")
    
    return factory(raw_block)
