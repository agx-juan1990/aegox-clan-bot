import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Discord
    TOKEN: str = os.getenv("DISCORD_TOKEN", "")
    CLIENT_ID: str = os.getenv("CLIENT_ID", "")
    OWNER_ID: str = os.getenv("OWNER_ID", "")
    
    # Guilds
    GUILD_ID_CLAN: int = int(os.getenv("GUILD_ID_CLAN", "1444791873955958878"))
    GUILD_ID_STAFF: int = int(os.getenv("GUILD_ID_STAFF", "1445833036007739576"))
    
    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./data/aegox.db")
    TURSO_DATABASE_URL: str = os.getenv("TURSO_DATABASE_URL", "")
    TURSO_AUTH_TOKEN: str = os.getenv("TURSO_AUTH_TOKEN", "")
    
    # Environment
    NODE_ENV: str = os.getenv("NODE_ENV", "development")
    AUTO_DEPLOY: bool = os.getenv("AUTO_DEPLOY", "true").lower() == "true"
    
    @classmethod
    def validate(cls) -> None:
        if not cls.TOKEN:
            raise ValueError("DISCORD_TOKEN es requerido")
        if not cls.CLIENT_ID:
            raise ValueError("CLIENT_ID es requerido")

config = Config()