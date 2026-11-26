"""
Verificación Web + Cloudflare Turnstile + Auto-asignación de rol verificado
Usa el widget existente de Turnstile (existing widget flow)
"""
import aiohttp
import time
from typing import Optional, Dict
from src.database import db, get_setting, log_event
from src.config.ids import CHANNELS, ROLES, VERIFIED_ROLE_ID, TURNSTILE_SITEKEY

class WebVerificationSystem:
    def __init__(self):
        self.turnstile_sitekey = TURNSTILE_SITEKEY
        self.turnstile_secret = None
    
    async def initialize(self, guild_id: int):
        """Carga configuración de verificación para el guild"""
        from src.database import get_setting
        self.turnstile_secret = await get_setting(guild_id, "TURNSTILE_SECRET")
    
    def get_sitekey(self) -> str:
        """Retorna el sitekey de Turnstile"""
        return self.turnstile_sitekey
    
    async def verify_turnstile(self, token: str, user_ip: str) -> Dict:
        """Verifica token de Cloudflare Turnstile"""
        if not self.turnstile_secret:
            return {"success": False, "error": "No configurado"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                    data={
                        "secret": self.turnstile_secret,
                        "response": token,
                        "remoteip": user_ip
                    }
                ) as resp:
                    result = await resp.json()
                    return {
                        "success": result.get("success", False),
                        "challenge_ts": result.get("challenge_ts"),
                        "hostname": result.get("hostname"),
                        "error_codes": result.get("error-codes", [])
                    }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def process_verification(self, guild_id: int, user_id: str, 
                                  token: str, user_ip: str, 
                                  cf_ray: str = None, country: str = None) -> Dict:
        """Procesa verificación completa"""
        # Verificar Turnstile
        result = await self.verify_turnstile(token, user_ip)
        
        # Guardar registro
        await db.execute(
            """INSERT INTO web_verifications 
               (user_id, guild_id, turnstile_token, cf_ray, ip, country, 
                challenge_ts, success, verified_role_given, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                user_id, guild_id, token, cf_ray, user_ip, "XX",
                int(time.time()), True, False,
                int(time.time() * 1000)
            ]
        )
        
        if not result.get("success"):
            return {"success": False, "error": "Verificación fallida"}
        
        # Asignar rol verificado
        guild = self._get_guild(guild_id)
        if guild:
            member = guild.get_member(user_id)
            if member:
                verified_role = guild.get_role(VERIFIED_ROLE_ID)
                if verified_role and verified_role not in member.roles:
                    try:
                        await member.add_roles(verified_role, reason="Verificación web completada")
                        
                        # Remover rol no verificado si existe
                        from src.config.ids import ROLES
                        unverified = ROLES.get("unverified_role")
                        if unverified:
                            unv_role = guild.get_role(unverified)
                            if unv_role and unv_role in member.roles:
                                await member.remove_roles(unv_role, reason="Verificado")
                        
                        # Actualizar registro
                        await db.execute(
                            "UPDATE web_verifications SET verified_role_given = 1 WHERE user_id = ? AND guild_id = ?",
                            [user_id, guild_id]
                        )
                        
                        return {"success": True, "role_given": True}
        
        return {"success": True, "role_given": False}
    
    def _get_guild(self, guild_id: int):
        import src.commands.ping as ping_cmd
        return ping_cmd.bot.get_guild(guild_id) if ping_cmd.bot else None

# Instancia global
web_verification_system = WebVerificationSystem()

# HTML para la página de verificación (existing widget flow)
VERIFICATION_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verificación AEGOX - Cloudflare Turnstile</title>
    <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
            min-height: 100vh; 
            display: flex; 
            align-items: center; 
            justify-content: center;
            color: #e6edf3;
            padding: 20px;
        }
        .container { 
            background: #161b22; 
            border: 1px solid #30363d; 
            border-radius: 12px; 
            padding: 40px; 
            max-width: 400px; 
            width: 100%;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        .logo { text-align: center; margin-bottom: 24px; }
        .logo svg { width: 80px; height: 80px; }
        h1 { font-size: 1.5rem; margin-bottom: 8px; text-align: center; }
        .subtitle { color: #8b949e; text-align: center; margin-bottom: 32px; font-size: 0.95rem; }
        .turnstile-container { margin: 24px 0; }
        .btn { 
            width: 100%; 
            padding: 14px; 
            border: none; 
            border-radius: 8px; 
            font-size: 1rem; 
            font-weight: 600; 
            cursor: pointer;
            background: linear-gradient(135deg, #1f6feb 0%, #8b5cf6 100%);
            color: white;
            transition: opacity 0.2s;
        }
        .btn:hover { opacity: 0.9; }
        .btn:disabled { opacity: 0.6; cursor: not-allowed; }
        .footer { 
            margin-top: 24px; 
            text-align: center; 
            color: #8b949e; 
            font-size: 0.75rem;
        }
        .spinner { 
            display: inline-block; 
            width: 20px; height: 20px; 
            border: 3px solid #30363d; 
            border-top-color: #1f6feb; 
            border-radius: 50%; 
            animation: spin 1s linear infinite; 
            display: none; 
            margin-right: 8px; 
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .status { text-align: center; margin-top: 16px; min-height: 24px; }
        .success { color: #3fb950; }
        .error { color: #f85149; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:#1f6feb"/>
                        <stop offset="100%" style="stop-color:#8b5cf6"/>
                    </linearGradient>
                </defs>
                <circle cx="50" cy="50" r="45" fill="url(#grad)"/>
                <text x="50" y="62" text-anchor="middle" fill="white" font-size="35" font-weight="bold">A</text>
            </svg>
        </div>
        <h1>Verificación AEGOX</h1>
        <p class="subtitle">Completa la verificación para acceder al servidor</p>
        
        <div class="turnstile-container">
            <div class="cf-turnstile" data-sitekey="{{SITEKEY}}" data-callback="onTurnstileSuccess" data-expired-callback="onTurnstileExpired" data-error-callback="onTurnstileError"></div>
        </div>
        
        <button class="btn" id="verifyBtn" disabled>
            <span class="spinner" id="spinner"></span>
            <span id="btnText">Verificando...</span>
        </button>
        
        <div class="status" id="status"></div>
        
        <div class="footer">
            AEGOX CLAN • Verificación Segura con Cloudflare Turnstile
        </div>
    </div>

    <script>
        let turnstileToken = null;
        
        function onTurnstileSuccess(token) {
            turnstileToken = token;
            document.getElementById('verifyBtn').disabled = false;
            document.getElementById('btnText').textContent = 'Verificar';
            document.getElementById('spinner').style.display = 'none';
            document.getElementById('status').innerHTML = '<span class="success">✅ Verificación exitosa. Redirigiendo...</span>';
            
            // Enviar token al servidor
            verifyToken(token);
        }
        
        function onTurnstileExpired() {
            turnstileToken = null;
            document.getElementById('verifyBtn').disabled = true;
            document.getElementById('btnText').textContent = 'Verificando...';
            document.getElementById('status').innerHTML = '<span class="error">⚠️ Verificación expirada. Intenta de nuevo.</span>';
        }
        
        function onTurnstileError() {
            document.getElementById('verifyBtn').disabled = true;
            document.getElementById('btnText').textContent = 'Verificando...';
            document.getElementById('status').innerHTML = '<span class="error">❌ Error en la verificación. Intenta de nuevo.</span>';
        }
        
        async function verifyToken(token) {
            try {
                const response = await fetch('/api/verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token })
                });
                const result = await response.json();
                if (result.success) {
                    if (result.role_given) {
                        document.getElementById('status').innerHTML = '<span class="success">✅ ¡Verificación exitosa! Rol asignado. Puedes cerrar esta ventana.</span>';
                    } else {
                        document.getElementById('status').innerHTML = '<span class="success">✅ Verificación exitosa.</span>';
                    }
                } else {
                    document.getElementById('verifyBtn').disabled = false;
                    document.getElementById('btnText').textContent = 'Verificando...';
                    document.getElementById('status').innerHTML = '<span class="error">❌ ' + (result.error || 'Error en la verificación') + '</span>';
                }
            } catch (e) {
                document.getElementById('verifyBtn').disabled = false;
                document.getElementById('btnText').textContent = 'Verificando...';
                document.getElementById('status').innerHTML = '<span class="error">❌ Error de conexión</span>';
            }
        }
    </script>
</body>
</html>
"""

def get_verification_html(sitekey: str) -> str:
    """Genera el HTML de verificación con el sitekey"""
    return VERIFICATION_HTML.replace("{{SITEKEY}}", sitekey)

# Instancia global
web_verification_system = WebVerificationSystem()