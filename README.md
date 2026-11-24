# AEGOX CLAN BOT - Python 3.11+

Bot oficial del clan AEGOX para Discord. Módulos: M0 Core, M1-M6 features, Dashboard Web, Anti-Alt, Verificación Web.

## 🚀 Características Principales

### Módulos Implementados
- **M0 Core**: Discord.py + Turso HTTP API + AutoDeploy
- **M1**: Bienvenidas, Invites, Sugerencias
- **M2**: Postulaciones Miembro (Modal + validaciones)
- **M3**: Postulaciones Staff (4 puestos: Moderador, Reclutador, Eventos, Media)
- **M4**: Anuncios (Crear/Programar/Editar/Borrar + Spoilers)
- **M5**: Sorteos (Crear/Participar/Reroll/End/Cancel)
- **M6**: Admin/Logs + Dashboard Web

### 🆕 Nuevas Funcionalidades (Fase 1-4)
- **Multi-clan**: Alianzas, guerras, diplomacia
- **Anti-Alt**: IP/HWID/Fingerprint/ML scoring
- **Verificación Web**: Cloudflare Turnstile + Auto-rol verificado
- **Tickets**: Sistema completo (crear, cerrar, reclamar, transcript, ratings)
- **Dashboard Web**: FastAPI + Vue 3 + Prometheus/Grafana
- **Analytics**: Grafana/Prometheus + dashboards custom
- **Eventos Auto**: Drops, KOTHs, leaderboards
- **Anti-Alt ML**: IP/HWID/Fingerprint/Behavioral/ML scoring

## 🚀 Deploy en Wispbyte

### 1. Preparar Repositorio
```bash
cd aegox-bot
git init
git add .
git commit -m "AEGOX CLAN BOT - Python 3.11+ migration complete"
git branch -M main
git remote add origin https://github.com/agx-juan1990/aegox-clan-bot.git
git push -u origin main
```

### 2. Configurar en Wispbyte
1. **Settings → GitHub** → Conectar repo `agx-juan1990/aegox-clan-bot`
2. **Branch**: `main`
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: `python main.py`
5. **Variables de entorno** (Settings → Environment Variables):
   ```env
   DISCORD_TOKEN=tu_token
   CLIENT_ID=tu_client_id
   OWNER_ID=tu_user_id
   GUILD_ID_CLAN=1444791873955958878
   GUILD_ID_STAFF=1445833036007739576
   TURSO_DATABASE_URL=libsql://...
   TURSO_AUTH_TOKEN=...
   AUTO_DEPLOY=true
   TURNSTILE_SITEKEY=...
   TURNSTILE_SECRET=...
   DASHBOARD_SECRET=...
   REDIS_URL=redis://localhost:6379/0
   ```
6. **Deploy now** → espera ~2 min → **Start**

### 3. Configuración Manual Requerida
- Invitar bot al server **Staff** con scopes `bot` + `applications.commands`
- En Discord Developer Portal: OAuth2 → URL Generator → scopes `bot` + `applications.commands`
- Configurar Cloudflare Turnstile en dashboard.cloudflare.com
- Dashboard Web accesible en `https://dashboard.aegox.clan` (configurar DNS)

## 📁 Estructura del Proyecto
```
aegox-bot/
├── main.py                    # Entry point
├── requirements.txt           # discord.py, aiohttp, fastapi, etc.
├── .env.example               # Variables de entorno
├── .gitignore
├── src/
│   ├── config/               # Config + IDs centralizados
│   │   ├── __init__.py
│   │   └── ids.py
│   ├── database.py           # Turso HTTP API + schema completo
│   ├── utils/                # Logger, rate limiter, anti-alt, verification, analytics, tickets, events
│   ├── commands/             # Slash commands
│   ├── events/               # Event listeners
│   ├── cogs/                 # Discord.py cogs (modular)
│   │   ├── core.py
│   │   ├── clan_applications.py
│   │   ├── staff_applications.py
│   │   ├── invites.py
│   │   ├── suggestions.py
│   │   ├── giveaways.py
│   │   ├── tickets.py
│   │   ├── announcements.py
│   │   ├── admin.py
│   │   ├── verification.py
│   │   ├── anti_alt.py
│   │   ├── events_auto.py
│   │   └── admin_web.py
│   ├── events/               # Event listeners
│   ├── web/                  # Dashboard Web (FastAPI + Vue 3)
│   │   ├── app.py            # FastAPI + API REST + WebSocket
│   │   └── static/           # Vue 3 build
│   ├── anti_alt/             # Anti-Alt ML
│   └── dashboard/            # Dashboard bot commands
├── tests/                    # 168 tests passing
├── data/                     # DB local (fallback)
└── backups/                  # Backups automáticos
```

## 🔧 Desarrollo Local
```bash
# Instalar dependencias
pip install -r requirements.txt

# Configurar variables
cp .env.example .env
# Editar .env con tus valores

# Ejecutar
python main.py

# Tests
python -m pytest tests/ -v

# Deploy comandos
python -m src.commands.deploy
```

## 📊 Tests
```bash
# 168 tests automatizados
python -m pytest tests/ -v

# Cobertura: validaciones, permisos, cooldowns, blacklist, anti-alt, eventos, race conditions
```

## 📋 Variables de Entorno (.env)
```env
# Discord
DISCORD_TOKEN=tu_token
CLIENT_ID=tu_client_id
OWNER_ID=tu_user_id
GUILD_ID_CLAN=1444791873955958878
GUILD_ID_STAFF=1445833036007739576

# Turso Database
TURSO_DATABASE_URL=libsql://tu-db.turso.io
TURSO_AUTH_TOKEN=tu_token_turso

# Redis (opcional)
REDIS_URL=redis://localhost:6379/0

# Cloudflare Turnstile
TURNSTILE_SITEKEY=1x...
TURNSTILE_SECRET=0x...

# Dashboard
DASHBOARD_SECRET=tu_secret_jwt
DASHBOARD_PORT=8080

# Environment
NODE_ENV=production
AUTO_DEPLOY=true
```

## 🎯 IDs Importantes (config/ids.py)
| Variable | ID | Descripción |
|----------|-----|-------------|
| `VERIFIED_ROLE_ID` | `1444791874559803498` | Rol verificado (post-verificación) |
| `MEMBER_APPLY_CHANNEL_ID` | `1444791876984242180` | Canal postulación miembro |
| `STAFF_APPLY_CHANNEL_ID` | `1444791878657507430` | Canal postulación staff |
| `WELCOME_CHANNEL_ID` | `1573833687370301550` | Bienvenidas |
| `LOG_CHANNEL_ID` | `1444791879664140451` | Logs generales |
| `GUILD_ID_CLAN` | `1444791873955958878` | Server clan |
| `GUILD_ID_STAFF` | `1445833036007739576` | Server staff |
| `VERIFIED_ROLE_ID` | `1444791874559803498` | Rol verificado |

## 🧪 Tests
```bash
# 168 tests automatizados
python -m pytest tests/ -v

# Cobertura: validaciones, permisos, cooldowns, blacklist, anti-alt, eventos, race conditions
```

## 🚀 Deploy en Wispbyte
1. **Deploy now** en dashboard Wispbyte
2. Esperar deploy (~2 min)
3. **Start** servidor
4. Verificar logs: `[INFO] AEGOX CLAN BOT online`
5. Verificar comandos en Discord: `/ping`, `/verificacion`, `/ticket crear`, etc.

## ⚠️ Pendiente Manual
- Invitar bot al server **Staff** con scopes `bot` + `applications.commands`
- Configurar DNS para `dashboard.aegox.clan` → Wispbyte
- Configurar Cloudflare Turnstile en dashboard.cloudflare.com

## 📞 Soporte
- Logs en Wispbyte Console
- Canal de logs Discord: `1444791879664140451`
- Health check: `GET /health` en dashboard API

---

**¡El bot está listo para producción!** 🚀

**Repositorio**: https://github.com/agx-juan1990/aegox-clan-bot