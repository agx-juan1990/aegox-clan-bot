"""
Dashboard Web - FastAPI + Vue 3
API REST + WebSocket para dashboard en tiempo real
"""
import os
import jwt
import time
import json
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from src.config import config
from src.config.ids import TURNSTILE_SITEKEY
from src.database import db, get_setting, get_db
from src.utils.analytics import analytics_collector, metrics_endpoint
from src.utils.web_verification import web_verification_system
from src.utils.logger import logger

app = FastAPI(title="AEGOX Dashboard API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()
SECRET_KEY = os.getenv("DASHBOARD_SECRET", "aegox-secret-change-me")
ALGORITHM = "HS256"

# WebSocket connections
active_connections: List[WebSocket] = []

# ============================================================
# MODELS
# ============================================================
class TokenData(BaseModel):
    user_id: str
    guild_id: int
    is_owner: bool
    exp: int

class LoginRequest(BaseModel):
    discord_id: str
    guild_id: int

class ClanCreate(BaseModel):
    name: str
    tag: str
    description: str = ""
    banner_url: str = ""

class TicketCreate(BaseModel):
    user_id: str
    category: str
    subject: str

class TicketUpdate(BaseModel):
    status: Optional[str] = None
    claimed_by: Optional[str] = None
    priority: Optional[str] = None

class AnnouncementCreate(BaseModel):
    type: str
    title: str
    description: str
    author: str
    image: Optional[str] = None
    footer: Optional[str] = None
    scheduled_at: Optional[int] = None

class GiveawayCreate(BaseModel):
    prize: str
    description: str
    duration: str
    winners: int
    requirements: str = ""

# ============================================================
# AUTH
# ============================================================
def create_token(user_id: str, guild_id: int, is_owner: bool) -> str:
    payload = {
        "user_id": str(user_id),
        "guild_id": guild_id,
        "is_owner": is_owner,
        "exp": int(time.time()) + 86400 * 7  # 7 días
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> TokenData:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenData(**payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

# ============================================================
# WEBSOCKET
# ============================================================
@app.websocket("/ws/{guild_id}")
async def websocket_endpoint(websocket: WebSocket, guild_id: int):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo para testing
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        active_connections.remove(websocket)

async def broadcast(guild_id: int, event: str, data: dict):
    """Broadcast evento a todas las conexiones del guild"""
    message = json.dumps({"event": event, "data": data, "timestamp": int(time.time())})
    for ws in active_connections[:]:
        try:
            await ws.send_text(message)
        except:
            active_connections.remove(ws)

# ============================================================
# AUTH ENDPOINTS
# ============================================================
@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """Login via Discord OAuth (simulado para testing)"""
    # En producción: validar código OAuth de Discord
    # Por ahora: token directo si owner
    is_owner = request.discord_id == config.OWNER_ID
    token = create_token(request.discord_id, request.guild_id, is_owner)
    return {"token": token, "user_id": request.discord_id, "is_owner": is_owner}

@app.get("/api/auth/me")
async def get_me(current_user: TokenData = Depends(verify_token)):
    return {
        "user_id": current_user.user_id,
        "guild_id": current_user.guild_id,
        "is_owner": current_user.is_owner
    }

# ============================================================
# CLANS
# ============================================================
@app.get("/api/clans")
async def list_clans(current_user: TokenData = Depends(verify_token)):
    clans = await db.fetchall("SELECT * FROM clans WHERE guild_id = ?", [current_user.guild_id])
    return {"clans": clans}

@app.post("/api/clans")
async def create_clan(clan: ClanCreate, current_user: TokenData = Depends(verify_token)):
    if not current_user.is_owner:
        raise HTTPException(403, "Solo owner")
    
    result = await db.execute(
        """INSERT INTO clans (guild_id, name, tag, owner_id, description, banner_url, created_at, settings)
           VALUES (?, ?, ?, ?, ?, ?, ?, '{}')""",
        [current_user.guild_id, clan.name, clan.tag, current_user.user_id, 
         clan.description, clan.banner_url, int(time.time() * 1000)]
    )
    clan_id = result["last_insert_rowid"]
    
    # Agregar owner como miembro
    await db.execute(
        "INSERT INTO clan_members (user_id, clan_id, role, joined_at) VALUES (?, ?, 'owner', ?)",
        [current_user.user_id, clan_id, int(time.time() * 1000)]
    )
    
    return {"id": clan_id, "message": "Clan creado"}

@app.get("/api/clans/{clan_id}")
async def get_clan(clan_id: int, current_user: TokenData = Depends(verify_token)):
    clan = await db.fetchone("SELECT * FROM clans WHERE id = ? AND guild_id = ?", [clan_id, current_user.guild_id])
    if not clan:
        raise HTTPException(404, "Clan no encontrado")
    
    members = await db.fetchall(
        "SELECT cm.*, u.username FROM clan_members cm LEFT JOIN users u ON cm.user_id = u.user_id WHERE cm.clan_id = ?",
        [clan_id]
    )
    clan["members"] = members
    return clan

@app.post("/api/clans/{clan_id}/members")
async def add_clan_member(clan_id: int, user_id: str, role: str = "member", current_user: TokenData = Depends(verify_token)):
    # Verificar permisos (owner/officer del clan)
    clan = await db.fetchone("SELECT * FROM clans WHERE id = ?", [clan_id])
    if not clan or clan["owner_id"] != current_user.user_id:
        raise HTTPException(403, "Sin permisos")
    
    await db.execute(
        "INSERT OR REPLACE INTO clan_members (user_id, clan_id, role, joined_at) VALUES (?, ?, ?, ?)",
        [user_id, clan_id, role, int(time.time() * 1000)]
    )
    return {"message": "Miembro agregado"}

# ============================================================
# TICKETS
# ============================================================
@app.get("/api/tickets")
async def list_tickets(guild_id: int, status: str = None, current_user: TokenData = Depends(verify_token)):
    sql = "SELECT * FROM tickets WHERE guild_id = ?"
    args = [guild_id]
    if status:
        sql += " AND status = ?"
        args.append(status)
    tickets = await db.fetchall(sql + " ORDER BY created_at DESC", args)
    return {"tickets": tickets}

@app.post("/api/tickets")
async def create_ticket(ticket: TicketCreate, current_user: TokenData = Depends(verify_token)):
    from src.utils.tickets import TicketSystem
    ts = TicketSystem()
    guild = None  # Obtener del bot
    channel = await ts.create_ticket(guild, current_user, ticket.category, ticket.subject)
    return {"channel_id": str(channel.id) if channel else None}

@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int, current_user: TokenData = Depends(verify_token)):
    ticket = await db.fetchone("SELECT * FROM tickets WHERE id = ?", [ticket_id])
    if not ticket:
        raise HTTPException(404, "Ticket no encontrado")
    
    messages = await db.fetchall(
        "SELECT tm.*, u.username FROM ticket_messages tm LEFT JOIN users u ON tm.user_id = u.user_id WHERE tm.ticket_id = ? ORDER BY tm.created_at",
        [ticket_id]
    )
    ticket["messages"] = messages
    return ticket

@app.patch("/api/tickets/{ticket_id}")
async def update_ticket(ticket_id: int, update: TicketUpdate, current_user: TokenData = Depends(verify_token)):
    ticket = await db.fetchone("SELECT * FROM tickets WHERE id = ?", [ticket_id])
    if not ticket:
        raise HTTPException(404, "Ticket no encontrado")
    
    # Verificar permisos
    can_manage = (ticket["user_id"] == current_user.user_id or 
                  ticket["claimed_by"] == current_user.user_id)
    if not can_manage:
        raise HTTPException(403, "Sin permisos")
    
    fields = []
    values = []
    for key, value in update.dict(exclude_unset=True).items():
        fields.append(f"{key} = ?")
        values.append(value)
    
    if fields:
        values.append(ticket_id)
        await db.execute(f"UPDATE tickets SET {', '.join(fields)} WHERE id = ?", values)
    
    return {"message": "Ticket actualizado"}

@app.post("/api/tickets/{ticket_id}/messages")
async def add_ticket_message(ticket_id: int, user_id: str, content: str, current_user: TokenData = Depends(verify_token)):
    from src.utils.tickets import TicketSystem
    ts = TicketSystem()
    await ts.add_message(ticket_id, current_user.user_id, content)
    return {"message": "Mensaje agregado"}

# ============================================================
# ANNOUNCEMENTS
# ============================================================
@app.get("/api/announcements")
async def list_announcements(guild_id: int, limit: int = 20, current_user: TokenData = Depends(verify_token)):
    announcements = await db.fetchall(
        "SELECT * FROM announcements WHERE guild_id = ? ORDER BY created_at DESC LIMIT ?",
        [guild_id, limit]
    )
    return {"announcements": announcements}

@app.post("/api/announcements")
async def create_announcement(ann: AnnouncementCreate, current_user: TokenData = Depends(verify_token)):
    if not current_user.is_owner:
        # Verificar permisos via roles
        pass
    
    result = await db.execute(
        """INSERT INTO announcements (guild_id, type, channel_id, title, description, author, image, footer, ping_role_id, status, scheduled_at, created_by, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [current_user.guild_id, ann.type, ann.channel_id, ann.title, ann.description,
         ann.author, ann.image, ann.footer, ann.ping_role_id, 
         "programado" if ann.scheduled_at else "publicado",
         ann.scheduled_at, current_user.user_id, int(time.time() * 1000)]
    )
    return {"id": result["last_insert_rowid"], "message": "Anuncio creado"}

# ============================================================
# GIVEAWAYS
# ============================================================
@app.get("/api/giveaways")
async def list_giveaways(guild_id: int, status: str = None, current_user: TokenData = Depends(verify_token)):
    sql = "SELECT * FROM giveaways WHERE guild_id = ?"
    args = [guild_id]
    if status:
        sql += " AND status = ?"
        args.append(status)
    giveaways = await db.fetchall(sql + " ORDER BY created_at DESC", args)
    return {"giveaways": giveaways}

# ============================================================
# ANALYTICS
# ============================================================
@app.get("/api/analytics/summary")
async def analytics_summary(guild_id: int, period: str = "24h", current_user: TokenData = Depends(verify_token)):
    period_map = {"1h": 3600000, "24h": 86400000, "7d": 604800000, "30d": 2592000000}
    start_ts = int(time.time() * 1000) - period_map.get(period, 86400000)
    
    dau = await db.fetchone(
        "SELECT COUNT(DISTINCT user_id) as count FROM analytics_events WHERE guild_id = ? AND timestamp >= ?",
        [guild_id, start_ts]
    )
    
    commands = await db.fetchall(
        "SELECT event_data, COUNT(*) as count FROM analytics_events WHERE guild_id = ? AND event_type = 'command_used' AND timestamp >= ? GROUP BY event_data ORDER BY count DESC LIMIT 10",
        [guild_id, start_ts]
    )
    
    anti_alt = await db.fetchall(
        "SELECT risk_level, COUNT(*) as count FROM alt_detections WHERE guild_id = ? AND created_at >= ? GROUP BY risk_level",
        [guild_id, start_ts]
    )
    
    return {
        "dau": dau["count"] if dau else 0,
        "top_commands": [{"command": json.loads(r["event_data"]).get("command"), "count": r["count"]} for r in commands],
        "anti_alt": [{"risk_level": r["risk_level"], "count": r["count"]} for r in anti_alt]
    }

@app.get("/api/analytics/events")
async def get_events(guild_id: int, event_type: str = None, limit: int = 100, current_user: TokenData = Depends(verify_token)):
    sql = "SELECT * FROM analytics_events WHERE guild_id = ?"
    args = [guild_id]
    if event_type:
        sql += " AND event_type = ?"
        args.append(event_type)
    sql += " ORDER BY timestamp DESC LIMIT ?"
    args.append(limit)
    events = await db.fetchall(sql, args)
    return {"events": events}

# ============================================================
# PROMETHEUS METRICS
# ============================================================
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# ============================================================
# VERIFICACIÓN WEB (Cloudflare Turnstile)
# ============================================================
from src.config.ids import TURNSTILE_SITEKEY

@app.get("/verify")
async def verification_page(guild: int, user: str):
    """Página de verificación con widget Turnstile"""
    from src.utils.web_verification import get_verification_html
    from src.config.ids import TURNSTILE_SITEKEY
    html = get_verification_html(TURNSTILE_SITEKEY)
    return HTMLResponse(content=html)

@app.post("/api/verify")
async def verify_token(request: Request):
    """Verifica token de Turnstile y asigna rol"""
    try:
        data = await request.json()
        token = data.get("token")
        guild_id = int(data.get("guild_id", 0))
        user_id = data.get("user_id", "")
        user_ip = data.get("ip", "")
        
        if not token or not guild_id or not user_id:
            return {"success": False, "error": "Datos incompletos"}
        
        from src.utils.web_verification import web_verification_system
        await web_verification_system.initialize(int(guild_id))
        result = await web_verification_system.process_verification(
            guild_id, user_id, token, user_ip
        )
        return result
    except Exception as e:
        logger.error(f"Error en verificación: {e}")
        return {"success": False, "error": "Error interno"}

# ============================================================
# WEBHOOK PARA CLOUDFLARE TURNSTILE CALLBACK
# ============================================================
from aiohttp import web as aiohttp_web
from src.utils.web_verification import web_verification_system
from src.utils.logger import logger

# Agregar ruta para webhook de Cloudflare (si se usa)
# Nota: FastAPI no maneja webhooks de aiohttp directamente
# Se recomienda usar un servidor separado o ngrok para desarrollo

# ============================================================
# HEALTH CHECK
# ============================================================
@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": int(time.time() * 1000)}

# ============================================================
# STARTUP
# ============================================================
@app.on_event("startup")
async def startup():
    await init_db()
    await analytics_collector.start()
    logger.info("Dashboard API iniciada")

@app.on_event("shutdown")
async def shutdown():
    await analytics_collector.stop()

# Servir frontend Vue (en producción)
app.mount("/", StaticFiles(directory="src/web/static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)