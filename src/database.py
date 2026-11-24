"""
Capa de base de datos usando Turso HTTP API directamente (sin libsql client)
"""
import os
import json
import logging
from typing import Any, Optional, List, Dict
from src.config.ids import CHANNELS, ROLES, GUILDS, APPLY_MESSAGES

logger = logging.getLogger(__name__)

class TursoDB:
    def __init__(self):
        self.url = os.getenv("TURSO_DATABASE_URL", "")
        self.token = os.getenv("TURSO_AUTH_TOKEN", "")
        
        if not self.url or not self.token:
            raise ValueError("TURSO_DATABASE_URL y TURSO_AUTH_TOKEN son requeridos")
        
        # Convert libsql:// to https://
        if self.url.startswith("libsql://"):
            self.base_url = self.url.replace("libsql://", "https://")
        else:
            self.base_url = self.url
            
        self.db_name = self.url.split("/")[-1] if "/" in self.url else "aegox"
        
    async def _execute(self, sql: str, args: list = None) -> dict:
        """Ejecuta una query SQL via Turso HTTP API"""
        import aiohttp
        
        formatted_args = []
        for arg in (args or []):
            if arg is None:
                formatted_args.append({"type": "null"})
            elif isinstance(arg, bool):
                formatted_args.append({"type": "integer", "value": "1" if arg else "0"})
            elif isinstance(arg, int):
                formatted_args.append({"type": "integer", "value": str(arg)})
            elif isinstance(arg, float):
                formatted_args.append({"type": "float", "value": str(arg)})
            else:
                formatted_args.append({"type": "text", "value": str(arg)})
        
        payload = {
            "requests": [{
                "type": "execute",
                "stmt": {"sql": sql, "args": formatted_args}
            }]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v2/pipeline",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json"
                },
                json=payload
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    raise Exception(f"Turso HTTP {resp.status}: {error}")
                
                data = await resp.json()
                result = data["results"][0]
                
                if result.get("error"):
                    raise Exception(f"Turso SQL error: {result['error']['message']}")
                
                return {
                    "rows": result.get("response", {}).get("result", {}).get("rows", []),
                    "last_insert_rowid": result.get("response", {}).get("result", {}).get("last_insert_rowid"),
                    "rows_affected": result.get("response", {}).get("result", {}).get("rows_affected"),
                }

    async def execute(self, sql: str, args: list = None) -> dict:
        return await self._execute(sql, args)

    async def fetchone(self, sql: str, args: list = None) -> Optional[dict]:
        result = await self._execute(sql, args)
        return result["rows"][0] if result["rows"] else None

    async def fetchall(self, sql: str, args: list = None) -> List[dict]:
        result = await self._execute(sql, args)
        return result["rows"]

# Instancia global
db = TursoDB()

# ============================================================
# HELPERS PARA CONFIG FIJA (canales, roles, etc.)
# ============================================================
from src.config.ids import CHANNELS, ROLES, GUILDS, APPLY_MESSAGES

CONFIG_CACHE = {}

def get_config_value(key: str):
    """Obtiene valores de configuración fija (canales, roles, guilds)"""
    if key in CHANNELS:
        return CHANNELS[key]
    if key in ROLES:
        return ROLES[key]
    if key in GUILDS:
        return GUILDS[key]
    if key in APPLY_MESSAGES:
        return APPLY_MESSAGES[key]
    return None

async def get_setting(guild_id: int, key: str) -> Optional[str]:
    """Obtiene setting: primero config fija, luego DB"""
    # Config fija
    config_val = get_config_value(key)
    if config_val is not None:
        return str(config_val)
    
    # DB para settings dinámicos
    row = await db.fetchone(
        "SELECT value FROM settings WHERE guild_id = ? AND key = ?",
        [guild_id, key]
    )
    return row["value"] if row else None

async def set_setting(guild_id: int, key: str, value: str) -> None:
    """Guarda setting en DB (no permite sobrescribir config fija)"""
    if get_config_value(key) is not None:
        logger.warning(f"Intento de sobrescribir config fijo: {key}")
        return
    await db.execute(
        "INSERT INTO settings (guild_id, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT(guild_id, key) DO UPDATE SET value = excluded.value",
        [key, value]
    )

# ============================================================
# SCHEMA & INIT
# ============================================================
SCHEMA = [
    """CREATE TABLE IF NOT EXISTS settings (
        guild_id INTEGER,
        key TEXT,
        value TEXT,
        PRIMARY KEY (guild_id, key)
    )""",
    """CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        guild_id INTEGER,
        username TEXT,
        joined_at INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        type TEXT,
        message TEXT,
        created_at INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS invites (
        inviter_id TEXT,
        guild_id INTEGER,
        code TEXT,
        total INTEGER DEFAULT 0,
        valid INTEGER DEFAULT 0,
        fake INTEGER DEFAULT 0,
        left INTEGER DEFAULT 0,
        PRIMARY KEY (inviter_id, guild_id)
    )""",
    """CREATE TABLE IF NOT EXISTS invite_members (
        user_id TEXT,
        guild_id INTEGER,
        inviter_id TEXT,
        code TEXT,
        joined_at INTEGER,
        left_at INTEGER,
        is_fake INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, guild_id)
    )""",
    """CREATE TABLE IF NOT EXISTS invite_top_message (
        guild_id INTEGER PRIMARY KEY,
        channel_id TEXT,
        message_id TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        user_id TEXT,
        text TEXT,
        message_id TEXT,
        channel_id TEXT,
        status TEXT DEFAULT 'pendiente',
        up INTEGER DEFAULT 0,
        down INTEGER DEFAULT 0,
        created_at INTEGER,
        decided_by TEXT,
        decided_at INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS suggestion_votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        suggestion_id INTEGER,
        user_id TEXT,
        dir TEXT,
        created_at INTEGER,
        UNIQUE (suggestion_id, user_id)
    )""",
    """CREATE TABLE IF NOT EXISTS member_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        guild_id INTEGER,
        mc_nick TEXT,
        edad INTEGER,
        pais TEXT,
        tiempo_jugando TEXT,
        rol_elegido TEXT,
        status TEXT DEFAULT 'pendiente',
        message_id TEXT,
        created_at INTEGER,
        decided_by TEXT,
        decided_at INTEGER,
        motivo TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS application_rejections (
        user_id TEXT,
        guild_id INTEGER,
        type TEXT,
        count INTEGER,
        last_rejected_at INTEGER,
        next_allowed_at INTEGER,
        PRIMARY KEY (user_id, guild_id, type)
    )""",
    """CREATE TABLE IF NOT EXISTS blacklist (
        user_id TEXT PRIMARY KEY,
        guild_id INTEGER,
        reason TEXT,
        by_user TEXT,
        created_at INTEGER,
        type TEXT DEFAULT 'postulaciones'
    )""",
    """CREATE TABLE IF NOT EXISTS staff_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        guild_id INTEGER,
        puesto TEXT,
        status TEXT DEFAULT 'pendiente',
        answers TEXT,
        message_id TEXT,
        created_at INTEGER,
        decided_by TEXT,
        decided_at INTEGER,
        motivo TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS staff_trials (
        user_id TEXT PRIMARY KEY,
        guild_id INTEGER,
        puesto TEXT,
        started_at INTEGER,
        ends_at INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        type TEXT,
        channel_id TEXT,
        message_id TEXT,
        title TEXT,
        description TEXT,
        author TEXT,
        image TEXT,
        footer TEXT,
        ping_role_id TEXT,
        status TEXT DEFAULT 'publicado',
        scheduled_at INTEGER,
        created_by TEXT,
        created_at INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS giveaways (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        channel_id TEXT,
        message_id TEXT,
        premio TEXT,
        descripcion TEXT,
        duracion TEXT,
        ends_at INTEGER,
        winners_count INTEGER,
        status TEXT DEFAULT 'activo',
        created_by TEXT,
        created_at INTEGER,
        winners TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS giveaway_entries (
        giveaway_id INTEGER,
        user_id TEXT,
        guild_id INTEGER,
        entered_at INTEGER,
        PRIMARY KEY (giveaway_id, user_id)
    )""",
]

async def init_db():
    """Inicializa la base de datos ejecutando el schema"""
    for sql in SCHEMA:
        await db.execute(sql)
    
    # Settings por defecto (solo los dinámicos)
    defaults = [
        ("WELCOME_RULES_DISCORD", "#reglas-discord"),
        ("WELCOME_RULES_MC", "#reglas-minecraft"),
        ("WELCOME_ALERTS", "#alertas"),
        ("MEMBER_APPLY_MESSAGE_ID", ""),
        ("STAFF_APPLY_MESSAGE_ID", ""),
    ]
    
    for key, value in defaults:
        await db.execute(
            "INSERT OR IGNORE INTO settings (guild_id, key, value) VALUES (?, ?, ?)",
            [1444791873955958878, key, value]  # guildIdClan
        )
    
    logger.info("Base de datos inicializada en Turso")

# ============================================================
# HELPERS COMUNES
# ============================================================

async def log_event(guild_id: int, type: str, message: str) -> None:
    await db.execute(
        "INSERT INTO logs (guild_id, type, message, created_at) VALUES (?, ?, ?, ?)",
        [guild_id, type, message, int(__import__('time').time() * 1000)]
    )

async def log_to_channel(bot, guild_id: int, type: str, embed) -> None:
    """Log a canal de Discord + DB"""
    log_channel_id = await get_setting(guild_id, "LOG_CHANNEL_ID")
    if log_channel_id:
        channel = bot.get_channel(int(log_channel_id))
        if channel:
            try:
                await channel.send(embed=embed)
            except:
                pass
    await log_event(guild_id, type, embed.description or str(embed.to_dict()))

async def create_backup_auto() -> str:
    """Crea backup automático de la DB"""
    import shutil
    from datetime import datetime
    import os
    
    backup_dir = "./backups"
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = f"aegox-{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_name)
    
    # Para Turso, hacemos dump via SQL
    # Como usamos HTTP API, exportamos via queries
    from src.database import db
    
    tables = ["settings", "users", "logs", "invites", "invite_members", 
              "invite_top_message", "suggestions", "suggestion_votes",
              "member_applications", "application_rejections", "blacklist",
              "staff_applications", "staff_trials", "announcements",
              "giveaways", "giveaway_entries"]
    
    dump_lines = []
    for table in tables:
        result = await db.execute(f"SELECT * FROM {table}")
        if result["rows"]:
            columns = list(result["rows"][0].keys()) if result["rows"] else []
            for row in result["rows"]:
                values = ", ".join(f"'{str(v).replace('\'', '\'\'')}'" if v is not None else "NULL" for v in row.values())
                cols = ", ".join(columns)
                dump_lines.append(f"INSERT INTO {table} ({cols}) VALUES ({values});")
    
    dump_content = "\n".join(dump_lines)
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(dump_content)
    
    # Mantener solo últimos 7 backups
    backups = sorted([f for f in os.listdir("./backups") if f.startswith("aegox-") and f.endswith(".db")])
    for old in backups[:-7]:
        os.remove(os.path.join("./backups", old))
    
    logger.info(f"Backup automático creado: {backup_path}")
    return backup_path

# Export
__all__ = [
    "db", "init_db", "get_setting", "set_setting", "log_event", "log_to_channel",
    "get_config_value", "create_backup_auto", "CHANNELS", "ROLES", "GUILDS", "APPLY_MESSAGES",
]