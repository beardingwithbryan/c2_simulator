from models import SlackConfig, DNSConfig, QUICConfig

def get_slack_params(config) -> dict:
    return config.to_dict()
    
def get_dns_params(config) -> dict:
    return config.to_dict()
    
def get_quic_params(config) -> dict:
    return config.to_dict()    


# Dispatch table mapping platform names to functions
HANDLERS = {
    "slack": get_slack_params,
    "dns": get_dns_params,
    "quic": get_quic_params
}
