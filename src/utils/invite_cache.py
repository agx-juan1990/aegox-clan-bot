"""
Cache de invites en memoria para tracking rápido
"""
from typing import Dict, Optional

invite_cache: Dict[int, Dict[str, dict]] = {}

def update_invite_cache(guild_id: int, code: str, inviter_id: Optional[str], uses: int) -> None:
    if guild_id not in invite_cache:
        invite_cache[guild_id] = {}
    invite_cache[guild_id][code] = {
        "code": code,
        "inviter_id": inviter_id,
        "uses": uses
    }

def delete_invite_cache(guild_id: int, code: str) -> None:
    if guild_id in invite_cache:
        invite_cache[guild_id].pop(code, None)

def get_invites(guild_id: int) -> dict:
    return invite_cache.get(guild_id, {})

async def fetch_and_cache_guild_invites(guild) -> dict:
    try:
        invites = await guild.invites()
        cache = {}
        for invite in invites:
            cache[invite.code] = {
                "code": invite.code,
                "inviter_id": str(invite.inviter.id) if invite.inviter else None,
                "uses": invite.uses or 0,
            }
        invite_cache[guild.id] = cache
        return cache
    except Exception as e:
        from src.utils.logger import logger
        logger.error(f"No se pudo cachear invites para guild {guild.id}: {e}")
        return {}