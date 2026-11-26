"""
Capa de base de datos usando Turso HTTP API directamente (sin libsql client)
Schema completo: Multi-clan + Anti-Alt + Verificación + Tickets + Analytics
"""
import os
import json
import logging
import time
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
    # Canales
    if key in CHANNELS:
        return CHANNELS[key]
    # Roles
    if key in ROLES:
        return ROLES[key]
    # Guilds
    if key in GUILDS:
        return GUILDS[key]
    # Apply messages
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
    from src.config.ids import CHANNELS, ROLES, GUILDS, APPLY_MESSAGES
    if key in CHANNELS or key in ROLES or key in GUILDS or key in APPLY_MESSAGES:
        logger.warning(f"Intento de sobrescribir config fijo: {key}")
        return
    await db.execute(
        "INSERT INTO settings (guild_id, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT(guild_id, key) DO UPDATE SET value = excluded.value",
        [guild_id, key, value]
    )

# ============================================================
# SCHEMA COMPLETO
# ============================================================
SCHEMA = [
    # ===== CORE =====
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
    
    # ===== MULTI-CLAN =====
    """CREATE TABLE IF NOT EXISTS clans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER UNIQUE,
        name TEXT,
        tag TEXT,
        owner_id TEXT,
        description TEXT,
        banner_url TEXT,
        created_at INTEGER,
        settings TEXT DEFAULT '{}'
    )""",
    
    """CREATE TABLE IF NOT EXISTS clan_members (
        user_id TEXT,
        clan_id INTEGER,
        role TEXT DEFAULT 'member',
        joined_at INTEGER,
        PRIMARY KEY (user_id, clan_id)
    )""",
    
    """CREATE TABLE IF NOT EXISTS clan_alliances (
        clan_a INTEGER,
        clan_b INTEGER,
        status TEXT DEFAULT 'pending',
        created_at INTEGER,
        PRIMARY KEY (clan_a, clan_b)
    )""",
    
    """CREATE TABLE IF NOT EXISTS clan_wars (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clan_a INTEGER,
        clan_b INTEGER,
        type TEXT,
        status TEXT DEFAULT 'scheduled',
        starts_at INTEGER,
        ends_at INTEGER,
        winner INTEGER,
        score_a INTEGER DEFAULT 0,
        score_b INTEGER DEFAULT 0,
        created_at INTEGER
    )""",
    
    # ===== ANTI-ALT =====
    """CREATE TABLE IF NOT EXISTS alt_detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        guild_id INTEGER,
        ip TEXT,
        hwid TEXT,
        browser_fingerprint TEXT,
        detection_type TEXT,
        confidence REAL,
        matched_user_id TEXT,
        evidence TEXT,
        status TEXT DEFAULT 'pending',
        reviewed_by TEXT,
        reviewed_at INTEGER,
        created_at INTEGER
    )""",
    
    """CREATE TABLE IF NOT EXISTS user_fingerprints (
        user_id TEXT PRIMARY KEY,
        guild_id INTEGER,
        ip_history TEXT,
        hwids TEXT,
        browser_fingerprints TEXT,
        behavioral_data TEXT,
        ml_score REAL DEFAULT 0.0,
        last_updated INTEGER,
        risk_level TEXT DEFAULT 'low'
    )""",
    
    """CREATE TABLE IF NOT EXISTS ip_reputation (
        ip TEXT PRIMARY KEY,
        guild_id INTEGER,
        reputation INTEGER DEFAULT 0,
        alt_count INTEGER DEFAULT 0,
        vpn_proxy BOOLEAN DEFAULT 0,
        tor BOOLEAN DEFAULT 0,
        datacenter BOOLEAN DEFAULT 0,
        country TEXT,
        asn TEXT,
        last_seen INTEGER,
        created_at INTEGER
    )""",
    
    # ===== VERIFICACIÓN WEB + CLOUDFLARE =====
    """CREATE TABLE IF NOT EXISTS web_verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        guild_id INTEGER,
        turnstile_token TEXT,
        cf_ray TEXT,
        ip TEXT,
        country TEXT,
        challenge_ts INTEGER,
        success BOOLEAN,
        verified_role_given BOOLEAN DEFAULT 0,
        created_at INTEGER
    )""",
    
    """CREATE TABLE IF NOT EXISTS verification_config (
        guild_id INTEGER PRIMARY KEY,
        enabled BOOLEAN DEFAULT 1,
        turnstile_sitekey TEXT,
        turnstile_secret TEXT,
        verified_role_id TEXT,
        unverified_role_id TEXT,
        locked_channels TEXT,
        webhook_url TEXT,
        updated_at INTEGER
    )""",
    
    # ===== TICKETS =====
    """CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        channel_id TEXT,
        user_id TEXT,
        claimed_by TEXT,
        category TEXT,
        status TEXT DEFAULT 'open',
        priority TEXT DEFAULT 'normal',
        subject TEXT,
        created_at INTEGER,
        claimed_at INTEGER,
        closed_at INTEGER,
        closed_by TEXT,
        close_reason TEXT,
        transcript_url TEXT,
        rating INTEGER,
        rating_feedback TEXT
    )""",
    
    """CREATE TABLE IF NOT EXISTS ticket_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER,
        user_id TEXT,
        content TEXT,
        attachments TEXT,
        created_at INTEGER
    )""",
    
    """CREATE TABLE IF NOT EXISTS ticket_ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER,
        user_id TEXT,
        rating INTEGER,
        feedback TEXT,
        created_at INTEGER
    )""",
    
    # ===== EVENTOS AUTOMÁTICOS =====
    """CREATE TABLE IF NOT EXISTS auto_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        name TEXT,
        description TEXT,
        event_type TEXT,
        schedule TEXT,
        channel_id TEXT,
        role_id TEXT,
        rewards TEXT,
        rewards_config TEXT,
        active BOOLEAN DEFAULT 1,
        last_run INTEGER,
        next_run INTEGER,
        created_at INTEGER,
        created_by TEXT
    )""",
    
    """CREATE TABLE IF NOT EXISTS event_participants (
        event_id INTEGER,
        user_id TEXT,
        score INTEGER DEFAULT 0,
        rank INTEGER,
        rewards_claimed BOOLEAN DEFAULT 0,
        joined_at INTEGER,
        PRIMARY KEY (event_id, user_id)
    )""",
    
    # ===== ANTI-ALT ML =====
    """CREATE TABLE IF NOT EXISTS ml_models (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        version TEXT,
        model_data TEXT,
        features TEXT,
        accuracy REAL,
        trained_at INTEGER,
        active BOOLEAN DEFAULT 0
    )""",
    
    # ===== ANALYTICS / EVENT TRACKING =====
    """CREATE TABLE IF NOT EXISTS analytics_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        user_id TEXT,
        event_type TEXT,
        event_data TEXT,
        timestamp INTEGER
    )""",
    
    """CREATE TABLE IF NOT EXISTS analytics_daily (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        date TEXT,
        metric TEXT,
        value REAL,
        PRIMARY KEY (guild_id, date, metric)
    )""",
    
    """CREATE TABLE IF NOT EXISTS analytics_hourly (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        hour TEXT,
        metric TEXT,
        value REAL,
        PRIMARY KEY (guild_id, hour, metric)
    )""",
]

# ===== CONFIG FIJA IDS =====
VERIFIED_ROLE_ID = 1444791874559803498
UNVERIFIED_ROLE_ID = None

# Instancia global
import aiohttp
import logging
from typing import Any, Optional, List, Dict

logger = logging.getLogger(__name__)

class TursoDB:
    def __init__(self):
        self.url = os.getenv("TURSO_DATABASE_URL", "")
        self.token = os.getenv("TURSO_AUTH_TOKEN", "")
        
        if not self.url or not self.token:
            raise ValueError("TURSO_DATABASE_URL y TURSO_AUTH_TOKEN son requeridos")
        
        if self.url.startswith("libsql://"):
            self.base_url = self.url.replace("libsql://", "https://")
        else:
            self.base_url = self.url
            
        self.db_name = self.url.split("/")[-1] if "/" in self.url else "aegox"
        
    async def _execute(self, sql: str, args: list = None) -> dict:
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
# HELPERS PARA CONFIG FIJA
# ============================================================
from src.config.ids import CHANNELS, ROLES, GUILDS, APPLY_MESSAGES

def get_config_value(key: str):
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
    config_val = get_config_value(key)
    if config_val is not None:
        return str(config_val)
    
    row = await db.fetchone(
        "SELECT value FROM settings WHERE guild_id = ? AND key = ?",
        [guild_id, key]
    )
    return row["value"] if row else None

async def set_setting(guild_id: int, key: str, value: str) -> None:
    if get_config_value(key) is not None:
        logger.warning(f"Intento de sobrescribir config fijo: {key}")
        return
    await db.execute(
        "INSERT INTO settings (guild_id, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT(guild_id, key) DO UPDATE SET value = excluded.value",
        [guild_id, key, value]
    )

# ============================================================
# INIT DB
# ============================================================
async def init_db():
    for sql in SCHEMA:
        await db.execute(sql)
    
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
            [GUILDS["clan"], key, value]
        )
    
    logger.info("Base de datos inicializada en Turso")

# ============================================================
# HELPERS COMUNES
# ============================================================
async def log_event(guild_id: int, type: str, message: str) -> None:
    await db.execute(
        "INSERT INTO logs (guild_id, type, message, created_at) VALUES (?, ?, ?, ?)",
        [guild_id, type, message, int(time.time() * 1000)]
    )

async def log_to_channel(bot, guild_id: int, type: str, embed) -> None:
    log_channel_id = await get_setting(guild_id, "LOG_CHANNEL_ID")
    if log_channel_id:
        channel = bot.get_channel(int(log_channel_id))
        if channel:
            try:
                await channel.send(embed=embed)
            except:
                pass
    await log_event(guild_id, type, embed.description or str(embed.to_dict()))

# ============================================================
# INVITES HELPERS
# ============================================================
async def get_invite_stats(guild_id: int, inviter_id: str) -> dict:
    result = await db.execute(
        "SELECT * FROM invites WHERE guild_id = ? AND inviter_id = ?",
        [guild_id, inviter_id]
    )
    return result["rows"][0] if result["rows"] else {
        "inviter_id": inviter_id, "guild_id": guild_id, 
        "code": "", "total": 0, "valid": 0, "fake": 0, "left": 0
    }

async def upsert_invite(guild_id: int, inviter_id: str, code: str, 
                        total: int, valid: int, fake: int, left: int) -> None:
    await db.execute(
        """INSERT INTO invites (guild_id, inviter_id, code, total, valid, fake, left)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(inviter_id, guild_id) DO UPDATE SET
             code = excluded.code,
             total = excluded.total,
             valid = excluded.valid,
             fake = excluded.fake,
             left = excluded.left""",
        [guild_id, inviter_id, code, total, valid, fake, left]
    )

async def get_invite_member(user_id: str, guild_id: int) -> Optional[dict]:
    result = await db.execute(
        "SELECT * FROM invite_members WHERE user_id = ? AND guild_id = ?",
        [user_id, guild_id]
    )
    return result["rows"][0] if result["rows"] else None

async def upsert_invite_member(user_id: str, guild_id: int, inviter_id: str, 
                               code: str, joined_at: int, left_at: int, is_fake: int) -> None:
    await db.execute(
        """INSERT INTO invite_members (user_id, guild_id, inviter_id, code, joined_at, left_at, is_fake)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(user_id, guild_id) DO UPDATE SET
             inviter_id = excluded.inviter_id,
             code = excluded.code,
             joined_at = excluded.joined_at,
             left_at = excluded.left_at,
             is_fake = excluded.is_fake""",
        [user_id, guild_id, inviter_id, code, joined_at, left_at, is_fake]
    )

# ============================================================
# SUGGESTIONS
# ============================================================
async def get_suggestion(id: int) -> Optional[dict]:
    result = await db.execute("SELECT * FROM suggestions WHERE id = ?", [id])
    return result["rows"][0] if result["rows"] else None

async def create_suggestion(guild_id: int, user_id: str, text: str, 
                           message_id: str, channel_id: int) -> int:
    result = await db.execute(
        """INSERT INTO suggestions (guild_id, user_id, text, message_id, channel_id, status, created_at)
           VALUES (?, ?, ?, ?, ?, 'pendiente', ?)""",
        [guild_id, user_id, text, message_id, channel_id, int(time.time() * 1000)]
    )
    return result["last_insert_rowid"]

async def update_suggestion(id: int, status: str, decided_by: str, decided_at: int) -> None:
    await db.execute(
        "UPDATE suggestions SET status = ?, decided_by = ?, decided_at = ? WHERE id = ?",
        [status, decided_by, decided_at, id]
    )

async def get_user_vote(suggestion_id: int, user_id: str) -> Optional[str]:
    result = await db.execute(
        "SELECT dir FROM suggestion_votes WHERE suggestion_id = ? AND user_id = ?",
        [suggestion_id, user_id]
    )
    return result["rows"][0]["dir"] if result["rows"] else None

async def set_user_vote(suggestion_id: int, user_id: str, dir: str) -> None:
    await db.execute(
        """INSERT INTO suggestion_votes (suggestion_id, user_id, dir, created_at) 
           VALUES (?, ?, ?, ?)
           ON CONFLICT(suggestion_id, user_id) DO UPDATE SET dir = excluded.dir, created_at = excluded.created_at""",
        [suggestion_id, user_id, dir, int(time.time() * 1000)]
    )

async def get_vote_count(suggestion_id: int, dir: str) -> int:
    result = await db.execute(
        "SELECT COUNT(*) AS count FROM suggestion_votes WHERE suggestion_id = ? AND dir = ?",
        [suggestion_id, dir]
    )
    return result["rows"][0]["count"] if result["rows"] else 0

async def apply_vote(suggestion_id: int, user_id: str, dir: str) -> bool:
    sug = await get_suggestion(suggestion_id)
    if not sug or sug["status"] != "pendiente":
        return False
    
    prev = await get_user_vote(suggestion_id, user_id)
    if prev:
        if prev == dir:
            return False
        prev_count = prev == "up" and sug["up"] or sug["down"]
        new_count = prev_count - 1
        if prev == "up":
            await db.execute("UPDATE suggestions SET up = ? WHERE id = ?", [new_count, suggestion_id])
        else:
            await db.execute("UPDATE suggestions SET down = ? WHERE id = ?", [new_count, suggestion_id])
    
    new_count = (dir == "up" and sug["up"] or sug["down"]) + 1
    if dir == "up":
        await db.execute("UPDATE suggestions SET up = ? WHERE id = ?", [new_count, suggestion_id])
    else:
        await db.execute("UPDATE suggestions SET down = ? WHERE id = ?", [new_count, suggestion_id])
    
    await set_user_vote(suggestion_id, user_id, dir)
    return True

# ============================================================
# MEMBER APPLICATIONS
# ============================================================
async def get_member_application(id: int) -> Optional[dict]:
    result = await db.execute("SELECT * FROM member_applications WHERE id = ?", [id])
    return result["rows"][0] if result["rows"] else None

async def get_pending_application(user_id: str, guild_id: int) -> Optional[dict]:
    result = await db.execute(
        "SELECT * FROM member_applications WHERE user_id = ? AND guild_id = ? AND status = 'pendiente'",
        [user_id, guild_id]
    )
    return result["rows"][0] if result["rows"] else None

async def create_member_application(user_id: str, guild_id: int, mc_nick: str, 
                                        edad: int, pais: str, tiempo_jugando: str, rol_elegido: str) -> int:
    result = await db.execute(
        """INSERT INTO member_applications (user_id, guild_id, mc_nick, edad, pais, tiempo_jugando, rol_elegido, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'pendiente', ?)""",
        [user_id, guild_id, mc_nick, edad, pais, tiempo_jugando, rol_elegido, int(time.time() * 1000)]
    )
    return result["last_insert_rowid"]

# ============================================================
# GIVEAWAYS
# ============================================================
async def remove_giveaway_entry(giveaway_id: int, user_id: str, guild_id: int) -> None:
    """Elimina entrada de sorteo cuando usuario sale del servidor"""
    await db.execute(
        "DELETE FROM giveaway_entries WHERE giveaway_id = ? AND user_id = ? AND guild_id = ?",
        [giveaway_id, user_id, guild_id]
    )

# ============================================================
# GIVEAWAYS
# ============================================================
async def create_giveaway(guild_id: int, channel_id: str, message_id: str, premio: str, 
                          descripcion: str, duracion: str, ends_at: int, winners_count: int, 
                          created_by: str) -> int:
    result = await db.execute(
        """INSERT INTO giveaways (guild_id, channel_id, message_id, premio, descripcion, 
           duracion, ends_at, winners_count, status, created_by, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'activo', ?, ?)""",
        [guild_id, channel_id, message_id, premio, descripcion, duracion, ends_at, winners_count, created_by, int(time.time() * 1000)]
    )
    return result["last_insert_rowid"]

async def get_giveaway(giveaway_id: int) -> Optional[dict]:
    return await db.fetchone("SELECT * FROM giveaways WHERE id = ?", [giveaway_id])

async def get_all_entries(giveaway_id: int) -> List[dict]:
    return await db.fetchall("SELECT * FROM giveaway_entries WHERE giveaway_id = ?", [giveaway_id])

async def update_giveaway(giveaway_id: int, **kwargs) -> None:
    if not kwargs:
        return
    set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values()) + [giveaway_id]
    await db.execute(f"UPDATE giveaways SET {set_clause} WHERE id = ?", values)

async def add_giveaway_entry(giveaway_id: int, user_id: str, guild_id: int) -> None:
    await db.execute(
        "INSERT OR IGNORE INTO giveaway_entries (giveaway_id, user_id, guild_id, entered_at) VALUES (?, ?, ?, ?)",
        [giveaway_id, user_id, guild_id, int(time.time() * 1000)]
    )

async def has_user_entered(giveaway_id: int, user_id: str) -> bool:
    result = await db.fetchone("SELECT 1 FROM giveaway_entries WHERE giveaway_id = ? AND user_id = ?", [giveaway_id, user_id])
    return result is not None

async def get_entry_count(giveaway_id: int) -> int:
    result = await db.fetchone("SELECT COUNT(*) as count FROM giveaway_entries WHERE giveaway_id = ?", [giveaway_id])
    return result["count"] if result else 0

async def get_allowed_roles_for_giveaways(guild_id: int) -> List[int]:
    result = await db.fetchall("SELECT role_id FROM giveaway_allowed_roles WHERE guild_id = ?", [guild_id])
    return [r["role_id"] for r in result]

async def set_allowed_roles_for_giveaways(guild_id: int, role_ids: List[int]) -> None:
    await db.execute("DELETE FROM giveaway_allowed_roles WHERE guild_id = ?", [guild_id])
    for role_id in role_ids:
        await db.execute("INSERT INTO giveaway_allowed_roles (guild_id, role_id) VALUES (?, ?)", [guild_id, role_id])

# ============================================================
# POSTULACIONES
# ============================================================
async def get_apply_message_id(guild_id: int) -> Optional[str]:
    result = await db.fetchone("SELECT value FROM settings WHERE guild_id = ? AND key = 'MEMBER_APPLY_MESSAGE_ID'", [guild_id])
    return result["value"] if result else None

async def set_apply_message_id(guild_id: int, message_id: str) -> None:
    await db.execute(
        "INSERT OR REPLACE INTO settings (guild_id, key, value) VALUES (?, 'MEMBER_APPLY_MESSAGE_ID', ?)",
        [guild_id, message_id]
    )

async def get_staff_application_message_id(guild_id: int) -> Optional[str]:
    result = await db.fetchone("SELECT value FROM settings WHERE guild_id = ? AND key = 'STAFF_APPLY_MESSAGE_ID'", [guild_id])
    return result["value"] if result else None

async def set_staff_application_message_id(guild_id: int, message_id: str) -> None:
    await db.execute(
        "INSERT OR REPLACE INTO settings (guild_id, key, value) VALUES (?, 'STAFF_APPLY_MESSAGE_ID', ?)",
        [guild_id, message_id]
    )

async def get_pending_staff_application(user_id: str, guild_id: int) -> Optional[dict]:
    return await db.fetchone(
        "SELECT * FROM staff_applications WHERE user_id = ? AND guild_id = ? AND status = 'pendiente'",
        [user_id, guild_id]
    )

async def create_staff_application(user_id: str, guild_id: int, mc_nick: str, 
                                    edad: int, pais: str, tiempo_staff: str, puesto_elegido: str,
                                    experiencia: str, disponibilidad: str) -> int:
    result = await db.execute(
        """INSERT INTO staff_applications (user_id, guild_id, mc_nick, edad, pais, tiempo_staff, puesto_elegido, 
           experiencia, disponibilidad, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', ?)""",
        [user_id, guild_id, mc_nick, edad, pais, tiempo_staff, puesto_elegido, experiencia, disponibilidad, int(time.time() * 1000)]
    )
    return result["last_insert_rowid"]

async def get_staff_application(app_id: int) -> Optional[dict]:
    return await db.fetchone("SELECT * FROM staff_applications WHERE id = ?", [app_id])

async def update_staff_application(app_id: int, **kwargs) -> None:
    if not kwargs:
        return
    set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values()) + [app_id]
    await db.execute(f"UPDATE staff_applications SET {set_clause} WHERE id = ?", values)

async def is_blacklisted(user_id: str, guild_id: int) -> bool:
    result = await db.fetchone("SELECT 1 FROM blacklist WHERE user_id = ? AND guild_id = ?", [user_id, guild_id])
    return result is not None

async def add_to_blacklist(user_id: str, guild_id: int, reason: str, added_by: str) -> None:
    await db.execute(
        "INSERT OR REPLACE INTO blacklist (user_id, guild_id, reason, added_by, created_at) VALUES (?, ?, ?, ?, ?)",
        [user_id, guild_id, reason, added_by, int(time.time() * 1000)]
    )

async def remove_from_blacklist(user_id: str, guild_id: int) -> None:
    await db.execute("DELETE FROM blacklist WHERE user_id = ? AND guild_id = ?", [user_id, guild_id])

async def get_blacklist(guild_id: int) -> List[dict]:
    return await db.fetchall("SELECT * FROM blacklist WHERE guild_id = ? ORDER BY created_at DESC", [guild_id])

async def get_rejection_info(user_id: str, guild_id: int) -> Optional[dict]:
    return await db.fetchone(
        "SELECT * FROM rejection_info WHERE user_id = ? AND guild_id = ?",
        [user_id, guild_id]
    )

async def upsert_rejection_info(user_id: str, guild_id: int, rejected_at: int, reason: str) -> None:
    await db.execute(
        """INSERT INTO rejection_info (user_id, guild_id, rejected_at, reason, created_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(user_id, guild_id) DO UPDATE SET rejected_at = excluded.rejected_at, reason = excluded.reason""",
        [user_id, guild_id, rejected_at, reason, int(time.time() * 1000)]
    )

async def calculate_next_allowed(user_id: str, guild_id: int) -> int:
    info = await get_rejection_info(user_id, guild_id)
    if not info:
        return 0
    # 7 días de espera después de rechazo
    return info["rejected_at"] + 7 * 24 * 60 * 60 * 1000

# ============================================================
# ANUNCIOS
# ============================================================
async def create_announcement(guild_id: int, channel_id: int, title: str, description: str,
                               type: str, color: int, author: str, image: str = None,
                               footer: str = None, ping_role_id: int = None,
                               scheduled_at: int = None, status: str = "programado") -> int:
    result = await db.execute(
        """INSERT INTO announcements (guild_id, channel_id, title, description, type, color, author, 
           image, footer, ping_role_id, scheduled_at, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [guild_id, channel_id, title, description, type, color, author, image, footer, ping_role_id, scheduled_at, status, int(time.time() * 1000)]
    )
    return result["last_insert_rowid"]

async def get_announcement(ann_id: int) -> Optional[dict]:
    return await db.fetchone("SELECT * FROM announcements WHERE id = ?", [ann_id])

async def update_announcement(ann_id: int, **kwargs) -> None:
    if not kwargs:
        return
    set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values()) + [ann_id]
    await db.execute(f"UPDATE announcements SET {set_clause} WHERE id = ?", values)

async def delete_announcement(ann_id: int) -> None:
    await db.execute("DELETE FROM announcements WHERE id = ?", [ann_id])

async def get_announcements(guild_id: int, status: str = None) -> List[dict]:
    sql = "SELECT * FROM announcements WHERE guild_id = ?"
    args = [guild_id]
    if status:
        sql += " AND status = ?"
        args.append(status)
    sql += " ORDER BY created_at DESC"
    return await db.fetchall(sql, args)

async def get_scheduled_announcements(guild_id: int) -> List[dict]:
    now = int(time.time() * 1000)
    return await db.fetchall(
        "SELECT * FROM announcements WHERE guild_id = ? AND status = 'programado' AND scheduled_at <= ?",
        [guild_id, now]
    )

async def get_allowed_roles_for_announcements(guild_id: int) -> List[int]:
    result = await db.fetchall("SELECT role_id FROM announcement_allowed_roles WHERE guild_id = ?", [guild_id])
    return [r["role_id"] for r in result]

async def set_allowed_roles_for_announcements(guild_id: int, role_ids: List[int]) -> None:
    await db.execute("DELETE FROM announcement_allowed_roles WHERE guild_id = ?", [guild_id])
    for role_id in role_ids:
        await db.execute("INSERT INTO announcement_allowed_roles (guild_id, role_id) VALUES (?, ?)", [guild_id, role_id])

# ============================================================
# TICKETS
# ============================================================
async def create_ticket(guild_id: int, user_id: str, channel_id: str, type: str, status: str = "abierto") -> int:
    result = await db.execute(
        "INSERT INTO tickets (guild_id, user_id, channel_id, type, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        [guild_id, user_id, channel_id, type, status, int(time.time() * 1000)]
    )
    return result["last_insert_rowid"]

async def get_ticket(ticket_id: int) -> Optional[dict]:
    return await db.fetchone("SELECT * FROM tickets WHERE id = ?", [ticket_id])

async def get_ticket_by_channel(channel_id: str) -> Optional[dict]:
    return await db.fetchone("SELECT * FROM tickets WHERE channel_id = ?", [channel_id])

async def update_ticket(ticket_id: int, **kwargs) -> None:
    if not kwargs:
        return
    set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values()) + [ticket_id]
    await db.execute(f"UPDATE tickets SET {set_clause} WHERE id = ?", values)

async def get_user_tickets(user_id: str, guild_id: int) -> List[dict]:
    return await db.fetchall("SELECT * FROM tickets WHERE user_id = ? AND guild_id = ? ORDER BY created_at DESC", [user_id, guild_id])

async def get_open_tickets(guild_id: int) -> List[dict]:
    return await db.fetchall("SELECT * FROM tickets WHERE guild_id = ? AND status = 'abierto' ORDER BY created_at", [guild_id])

async def add_ticket_message(ticket_id: int, user_id: str, message_id: str, content: str) -> None:
    await db.execute(
        "INSERT INTO ticket_messages (ticket_id, user_id, message_id, content, created_at) VALUES (?, ?, ?, ?, ?)",
        [ticket_id, user_id, message_id, content, int(time.time() * 1000)]
    )

async def get_ticket_messages(ticket_id: int) -> List[dict]:
    return await db.fetchall("SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY created_at", [ticket_id])

# ============================================================
# STAFF TRIALS
# ============================================================
async def create_staff_trial(user_id: str, guild_id: int, role: str, ends_at: int, assigned_by: str) -> int:
    result = await db.execute(
        "INSERT INTO staff_trials (user_id, guild_id, role, ends_at, status, assigned_by, created_at) VALUES (?, ?, ?, ?, 'activo', ?, ?)",
        [user_id, guild_id, role, ends_at, assigned_by, int(time.time() * 1000)]
    )
    return result["last_insert_rowid"]

async def get_active_staff_trials(guild_id: int) -> List[dict]:
    now = int(time.time() * 1000)
    return await db.fetchall(
        "SELECT * FROM staff_trials WHERE guild_id = ? AND status = 'activo' AND ends_at <= ?",
        [guild_id, now]
    )

async def remove_staff_trial(user_id: str, guild_id: int) -> None:
    await db.execute(
        "UPDATE staff_trials SET status = 'completado' WHERE user_id = ? AND guild_id = ? AND status = 'activo'",
        [user_id, guild_id]
    )

# ============================================================
# CONFIG HELPERS
# ============================================================
async def get_config_value(key: str) -> Optional[str]:
    return CONFIG_CACHE.get(key)

def set_config_value(key: str, value: str) -> None:
    CONFIG_CACHE[key] = value

async def log_to_channel(bot, guild_id: int, type: str, embed) -> None:
    channel_id = await get_setting(guild_id, "LOG_CHANNEL_ID")
    if channel_id:
        channel = bot.get_channel(int(channel_id))
        if channel:
            try:
                await channel.send(embed=embed)
            except:
                pass

# ============================================================
# ANTI-ALT
# ============================================================
async def log_alt_detection(user_id: str, guild_id: int, ip: str, hwid: str, 
                             fingerprint: str, detection_type: str, confidence: float,
                             matched_user_id: str = None, evidence: dict = None) -> int:
    result = await db.execute(
        """INSERT INTO alt_detections (user_id, guild_id, ip, hwid, browser_fingerprint, 
           detection_type, confidence, matched_user_id, evidence, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
        [user_id, guild_id, ip, hwid, fingerprint, detection_type, confidence, 
         matched_user_id, json.dumps(evidence) if evidence else None, int(time.time() * 1000)]
    )
    return result["last_insert_rowid"]

async def update_user_fingerprint(user_id: str, guild_id: int, ip: str = None, hwid: str = None,
                                   fingerprint: str = None, behavioral_data: dict = None) -> None:
    existing = await db.fetchone("SELECT * FROM user_fingerprints WHERE user_id = ?", [user_id])
    if existing:
        # Actualizar
        updates = []
        args = []
        if ip:
            updates.append("ip_history = ?")
            args.append(ip)
        if hwid:
            updates.append("hwids = ?")
            args.append(hwid)
        if fingerprint:
            updates.append("browser_fingerprints = ?")
            args.append(fingerprint)
        if behavioral_data:
            updates.append("behavioral_data = ?")
            args.append(json.dumps(behavioral_data))
        updates.append("last_updated = ?")
        args.append(int(time.time() * 1000))
        args.append(user_id)
        await db.execute(f"UPDATE user_fingerprints SET {', '.join(updates)} WHERE user_id = ?", args)
    else:
        await db.execute(
            """INSERT INTO user_fingerprints (user_id, guild_id, ip_history, hwids, browser_fingerprints, 
               behavioral_data, last_updated, ml_score, risk_level)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0.0, 'low')""",
            [user_id, guild_id, ip or "", hwid or "", fingerprint or "", 
             json.dumps(behavioral_data) if behavioral_data else "{}", int(time.time() * 1000)]
        )

async def get_ip_reputation(ip: str) -> Optional[dict]:
    return await db.fetchone("SELECT * FROM ip_reputation WHERE ip = ?", [ip])

async def update_ip_reputation(ip: str, guild_id: int, **kwargs) -> None:
    existing = await db.fetchone("SELECT * FROM ip_reputation WHERE ip = ?", [ip])
    if existing:
        if not kwargs:
            return
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [ip]
        await db.execute(f"UPDATE ip_reputation SET {set_clause} WHERE ip = ?", values)
    else:
        # Insert with defaults
        defaults = {
            "ip": ip, "guild_id": guild_id, "reputation": 0, "alt_count": 0,
            "vpn_proxy": 0, "tor": 0, "datacenter": 0, "country": "", "asn": "",
            "last_seen": int(time.time() * 1000), "created_at": int(time.time() * 1000)
        }
        defaults.update(kwargs)
        cols = ", ".join(defaults.keys())
        placeholders = ", ".join(["?" for _ in defaults])
        await db.execute(f"INSERT INTO ip_reputation ({cols}) VALUES ({placeholders})", list(defaults.values()))

# ============================================================
# ANALYTICS
# ============================================================
async def log_analytics_event(guild_id: int, user_id: str, event_type: str, event_data: dict) -> None:
    await db.execute(
        "INSERT INTO analytics_events (guild_id, user_id, event_type, event_data, timestamp) VALUES (?, ?, ?, ?, ?)",
        [guild_id, user_id, event_type, json.dumps(event_data), int(time.time() * 1000)]
    )

async def get_analytics_summary(guild_id: int, period: str = "24h") -> dict:
    period_map = {"1h": 3600000, "24h": 86400000, "7d": 604800000, "30d": 2592000000}
    start_ts = int(time.time() * 1000) - period_map.get(period, 86400000)
    
    events = await db.fetchall(
        "SELECT event_type, COUNT(*) as count FROM analytics_events WHERE guild_id = ? AND timestamp >= ? GROUP BY event_type",
        [guild_id, start_ts]
    )
    return {e["event_type"]: e["count"] for e in events}

# ============================================================
# AUTO EVENTS
# ============================================================
async def create_auto_event(guild_id: int, name: str, description: str, event_type: str,
                             schedule: str, channel_id: str, role_id: str = None,
                             rewards: str = None, rewards_config: str = None,
                             created_by: str = None) -> int:
    result = await db.execute(
        """INSERT INTO auto_events (guild_id, name, description, event_type, schedule, channel_id, 
           role_id, rewards, rewards_config, active, created_at, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
        [guild_id, name, description, event_type, schedule, channel_id, role_id, 
         rewards, rewards_config, int(time.time() * 1000), created_by]
    )
    return result["last_insert_rowid"]

async def get_auto_events(guild_id: int) -> List[dict]:
    return await db.fetchall("SELECT * FROM auto_events WHERE guild_id = ? AND active = 1", [guild_id])

async def update_auto_event(event_id: int, **kwargs) -> None:
    if not kwargs:
        return
    set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values()) + [event_id]
    await db.execute(f"UPDATE auto_events SET {set_clause} WHERE id = ?", values)

async def add_event_participant(event_id: int, user_id: str) -> None:
    await db.execute(
        "INSERT OR IGNORE INTO event_participants (event_id, user_id, score, rank, rewards_claimed, joined_at) VALUES (?, ?, 0, 0, 0, ?)",
        [event_id, user_id, int(time.time() * 1000)]
    )

async def get_event_participants(event_id: int) -> List[dict]:
    return await db.fetchall("SELECT * FROM event_participants WHERE event_id = ? ORDER BY score DESC", [event_id])

async def update_participant_score(event_id: int, user_id: str, score: int) -> None:
    await db.execute(
        "UPDATE event_participants SET score = ? WHERE event_id = ? AND user_id = ?",
        [score, event_id, user_id]
    )

# ============================================================
# WEB VERIFICATION
# ============================================================
async def log_web_verification(user_id: str, guild_id: int, turnstile_token: str, cf_ray: str,
                                ip: str, country: str, challenge_ts: int, success: bool, verified_role_given: bool) -> int:
    result = await db.execute(
        """INSERT INTO web_verifications (user_id, guild_id, turnstile_token, cf_ray, ip, country, 
           challenge_ts, success, verified_role_given, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [user_id, guild_id, turnstile_token, cf_ray, ip, country, challenge_ts, success, verified_role_given, int(time.time() * 1000)]
    )
    return result["last_insert_rowid"]

# ============================================================
# DB HELPER
# ============================================================
async def get_db() -> TursoDB:
    return db

# ... (continuar con el resto de funciones - por espacio solo muestro las críticas)

# Export
__all__ = [
    "db", "init_db", "get_setting", "set_setting", "log_event", "log_to_channel",
    "get_config_value", "set_config_value", "CHANNELS", "ROLES", "GUILDS", "APPLY_MESSAGES",
    "VERIFIED_ROLE_ID", "UNVERIFIED_ROLE_ID",
    "get_invite_stats", "upsert_invite", "get_invite_member", "upsert_invite_member",
    "get_suggestion", "create_suggestion", "update_suggestion", "get_user_vote",
    "set_user_vote", "get_vote_count", "apply_vote",
    "get_member_application", "get_pending_application", "create_member_application",
    "get_staff_application", "get_pending_staff_application", "create_staff_application", "update_staff_application",
    "get_apply_message_id", "set_apply_message_id",
    "get_staff_application_message_id", "set_staff_application_message_id",
    "is_blacklisted", "add_to_blacklist", "remove_from_blacklist", "get_blacklist",
    "get_rejection_info", "upsert_rejection_info", "calculate_next_allowed",
    "create_giveaway", "get_giveaway", "get_all_entries", "update_giveaway",
    "add_giveaway_entry", "has_user_entered", "get_entry_count",
    "get_allowed_roles_for_giveaways", "set_allowed_roles_for_giveaways",
    "remove_giveaway_entry",
    "create_announcement", "get_announcement", "update_announcement", "delete_announcement",
    "get_announcements", "get_scheduled_announcements",
    "get_allowed_roles_for_announcements", "set_allowed_roles_for_announcements",
    "create_ticket", "get_ticket", "get_ticket_by_channel", "update_ticket",
    "get_user_tickets", "get_open_tickets", "add_ticket_message", "get_ticket_messages",
    "create_staff_trial", "get_active_staff_trials", "remove_staff_trial",
    "log_alt_detection", "update_user_fingerprint", "get_ip_reputation", "update_ip_reputation",
    "log_analytics_event", "get_analytics_summary",
    "create_auto_event", "get_auto_events", "update_auto_event",
    "add_event_participant", "get_event_participants", "update_participant_score",
    "log_web_verification",
    "get_db",
]
