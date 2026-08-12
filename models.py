from dataclasses import dataclass, asdict
@dataclass
class SlackConfig:
    oauth_token: str
    send_channel: str
    recv_channel: str
    bot_name: str
    def to_dict(self) -> dict:
        return asdict(self)
        
@dataclass        
class DNSConfig:
    domain: str
    key: str
    def to_dict(self) -> dict:
        return asdict(self)

@dataclass        
class QUICConfig:
    domain: str
    def to_dict(self) -> dict:
        return asdict(self)
