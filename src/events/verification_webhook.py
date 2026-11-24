"""
Webhook handler para verificación web (Cloudflare Turnstile callback)
"""
from aiohttp import web
import json
import time
from src.utils.web_verification import web_verification_system
from src.utils.logger import logger

async def verification_webhook(request):
    """Endpoint para recibir callback de verificación web"""
    try:
        data = await request.json()
        
        user_id = data.get("user_id")
        guild_id = data.get("guild_id")
        token = data.get("token")
        user_ip = data.get("ip")
        cf_ray = data.get("cf_ray")
        country = data.get("country")
        
        if not all([user_id, guild_id, token, user_ip]):
            return web.json_response({"error": "Datos incompletos"}, status=400)
        
        # Procesar verificación
        result = await web_verification_system.process_verification(
            guild_id, user_id, token, user_ip, cf_ray, country
        )
        
        return web.json_response(result)
    
    except Exception as e:
        logger.error(f"Error en webhook de verificación: {e}")
        return web.json_response({"error": "Error interno"}, status=500)

async def cloudflare_webhook(request):
    """Webhook genérico de Cloudflare"""
    try:
        data = await request.json()
        logger.info(f"Cloudflare webhook: {json.dumps(data)}")
        return web.json_response({"status": "ok"})
    except Exception as e:
        logger.error(f"Error en cloudflare webhook: {e}")
        return web.json_response({"error": "Error interno"}, status=500)

def setup_webhooks(app: web.Application):
    """Registra rutas de webhooks"""
    app.router.add_post("/webhook/verify", verification_webhook)
    app.router.add_post("/webhook/cloudflare", cloudflare_webhook)