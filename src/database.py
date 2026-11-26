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

# ... (continuar con el resto de funciones - por espacio solo muestro las críticas)

# Export
__all__ = [
    "db", "init_db", "get_setting", "set_setting", "log_event", "log_to_channel",
    "get_config_value", "CHANNELS", "ROLES", "GUILDS", "APPLY_MESSAGES",
    "VERIFIED_ROLE_ID", "get_setting", "set_setting", "log_event", "log_to_channel",
    "get_invite_stats", "upsert_invite", "get_invite_member", "upsert_invite_member",
    "get_suggestion", "create_suggestion", "update_suggestion", "get_user_vote",
    "set_user_vote", "get_vote_count", "apply_vote",
    "get_member_application", "get_pending_application", "create_member_application",
    "remove_giveaway_entry",
    # ... resto de exports
]
