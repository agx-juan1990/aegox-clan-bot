"""
Eventos de miembros: join, remove
"""
import discord
import time
from src.database import db, get_setting, log_event, upsert_invite, get_invite_stats, upsert_invite_member, get_invite_member, remove_giveaway_entry
from src.utils.invite_cache import invite_cache, fetch_and_cache_guild_invites
from src.utils.logger import logger
from src.config.ids import CHANNELS, ROLES, VERIFIED_ROLE_ID, UNVERIFIED_ROLE_ID

async def on_guild_member_add(member):
    """Bienvenida + tracking de invites + rol verificado"""
    guild = member.guild
    guild_id = guild.id
    user_id = str(member.id)
    joined_at = int(time.time() * 1000)
    
    # 1. Rol automático
    auto_role_id = await get_setting(guild_id, "AUTO_ROLE_ID")
    if auto_role_id:
        try:
            role = guild.get_role(auto_role_id)
            if role:
                await member.roles.add(role, reason="AEGOX Auto Role")
        except Exception as e:
            logger.error(f"No se pudo dar rol auto: {e}")
    
    # 2. Guardar usuario
    await db.execute(
        """INSERT INTO users (user_id, guild_id, username, joined_at) VALUES (?, ?, ?, ?)
           ON CONFLICT(user_id, guild_id) DO UPDATE SET username = excluded.username, joined_at = excluded.joined_at""",
        [user_id, guild_id, member.name, joined_at]
    )
    
    # 3. Log bienvenida
    from src.database import log_event
    await log_event(guild_id, "welcome", f"{member.name} ({user_id}) se unió al servidor.")
    
    # 4. Embed bienvenida
    welcome_embed = discord.Embed(
        title="Bienvenido(a) a AEGOX",
        color=0x8b00ff,
        description=(
            f"👋 Hola {member.mention} bienvenido(a) a AEGOX!\n"
            "Recuerda leer las reglas para evitar inconvenientes.\n"
            "¡Activa las alertas para estar al día de todo!"
        )
    ).set_thumbnail(member.display_avatar.url).set_footer(text=f"Bienvenido el {datetime.now().strftime('%d/%m/%Y')}")
    
    welcome_channel_id = await get_setting(guild_id, "WELCOME_CHANNEL_ID")
    if welcome_channel_id:
        welcome_channel = guild.get_channel(welcome_channel_id)
        if welcome_channel and welcome_channel.is_text_based():
            try:
                await welcome_channel.send(embed=welcome_embed)
            except Exception as e:
                logger.error(f"No se pudo enviar bienvenida: {e}")
    
    # DM de bienvenida
    try:
        await member.send(embed=welcome_embed)
    except:
        pass
    
    # Tracking de invites
    try:
        fresh_invites = await member.guild.invites()
        from src.utils.invite_cache import get_invites
        cache = get_invites(guild_id)
        
        used_invite = None
        for invite in fresh_invites:
            cached = cache.get(invite.code)
            uses_after = invite.uses or 0
            uses_before = cached.get("uses", 0) if cached else 0
            if uses_after > uses_before:
                used_invite = {
                    "code": invite.code,
                    "inviter_id": str(invite.inviter.id) if invite.inviter else None,
                    "uses": uses_after,
                }
                break
        
        # Actualizar cache
        new_cache = {}
        for invite in fresh_invites:
            new_cache[invite.code] = {
                "code": invite.code,
                "inviter_id": str(invite.inviter.id) if invite.inviter else None,
                "uses": invite.uses or 0,
            }
        invite_cache[guild_id] = new_cache
        
        inviter_id = used_invite["inviter_id"] if used_invite else None
        account_age = time.time() * 1000 - member.created_at.timestamp() * 1000
        is_fake = account_age < 3 * 24 * 60 * 60 * 1000
        
        # Guardar en invite_members
        from src.database import upsert_invite_member
        await upsert_invite_member(
            user_id, guild_id, inviter_id, 
            used_invite["code"] if used_invite else None, 
            joined_at, None, 1 if is_fake else 0
        )
        
        # Actualizar stats del inviter
        if inviter_id:
            from src.database import get_invite_stats, upsert_invite
            stats = await get_invite_stats(guild_id, inviter_id)
            total = (stats.get("total", 0) or 0) + 1
            valid = is_fake * (stats.get("valid", 0) or 0) + (not is_fake) * ((stats.get("valid", 0) or 0) + 1)
            fake = is_fake * ((stats.get("fake", 0) or 0) + 1) + (not is_fake) * (stats.get("fake", 0) or 0)
            
            from src.database import upsert_invite
            code = used_invite["code"] if used_invite else stats.get("code", "")
            await upsert_invite(guild_id, inviter_id, code, total, valid, fake, stats.get("left", 0))
        
        # Log invite
        invite_log_channel_id = await get_setting(guild_id, "INVITE_LOG_CHANNEL_ID")
        invite_log_channel = member.guild.get_channel(invite_log_channel_id) if invite_log_channel_id else None
        
        if inviter_id:
            stats = await get_invite_stats(guild_id, inviter_id)
            if invite_log_channel and invite_log_channel.is_text_based():
                await invite_log_channel.send(f"<@{user_id}> fue invitado por <@{inviter_id}> quien ahora tiene {stats.get('valid', 0)} invites.")
            await log_event(guild_id, "invite", f"<@{user_id}> fue invitado por <@{inviter_id}> quien ahora tiene {stats.get('valid', 0)} invites.")
        else:
            if invite_log_channel and invite_log_channel.is_text_based():
                await invite_log_channel.send(f"<@{user_id}> entró sin invite.")
            await log_event(guild_id, "invite", f"<@{user_id}> entró sin invite.")
        
        # Verificar si tiene rol verificado (sistema web)
        from src.config.ids import VERIFIED_ROLE_ID
        verified_role = member.guild.get_role(VERIFIED_ROLE_ID)
        if verified_role and verified_role not in member.roles:
            # Usuario no verificado - aplicar rol no verificado
            from src.config.ids import ROLES
            unverified_role_id = ROLES.get("unverified_role")
            if unverified_role_id:
                unverified_role = member.guild.get_role(unverified_role_id)
                if unverified_role:
                    try:
                        await member.add_roles(unverified_role, reason="Usuario no verificado")
                    except:
                        pass
    
    except Exception as e:
        logger.error(f"Error en on_guild_member_add: {e}")

async def on_guild_member_remove(member):
    """Salida de miembro + limpieza invites + giveaways"""
    guild = member.guild
    guild_id = guild.id
    user_id = str(member.id)
    
    from src.database import db, get_setting, log_event, get_invite_stats, upsert_invite, remove_giveaway_entry
    
    member_row = await db.fetchone(
        "SELECT * FROM invite_members WHERE user_id = ? AND guild_id = ?",
        [user_id, guild_id]
    )
    
    if member_row and member_row["inviter_id"]:
        stats = await get_invite_stats(guild_id, member_row["inviter_id"])
        valid = member_row["is_fake"] * (stats.get("valid", 0) or 0) + (1 - member_row["is_fake"]) * max(0, (stats.get("valid", 0) or 0) - 1)
        left = (stats.get("left", 0) or 0) + 1
        
        await upsert_invite(guild_id, member_row["inviter_id"], member_row["code"] or "", stats.get("total", 0), valid, stats.get("fake", 0), left)
    
    await db.execute(
        "UPDATE invite_members SET left_at = ? WHERE user_id = ? AND guild_id = ?",
        [int(time.time() * 1000), user_id, guild_id]
    )
    
    # Remover entradas de giveaway
    try:
        entries = await db.fetchall(
            "SELECT giveaway_id FROM giveaway_entries WHERE user_id = ? AND guild_id = ?",
            [user_id, guild_id]
        )
        for entry in entries:
            from src.database import remove_giveaway_entry
            await remove_giveaway_entry(entry["giveaway_id"], user_id, guild_id)
    except Exception as e:
        logger.error(f"Error removiendo entradas de giveaway: {e}")
    
    # Log
    invite_log_channel_id = await get_setting(guild_id, "INVITE_LOG_CHANNEL_ID")
    invite_log_channel = invite_log_channel_id and guild.channels.get(int(invite_log_channel_id))
    
    if invite_log_channel and invite_log_channel.is_text_based():
        if member_row and member_row["inviter_id"]:
            stats = await get_invite_stats(guild_id, member_row["inviter_id"])
            await invite_log_channel.send(f"<@{user_id}> salió. {stats.get('valid', 0)} invites válidas.")
        else:
            await invite_log_channel.send(f"<@{user_id}> salió del servidor.")
    
    await log_event(guild_id, "invite_leave", f"<@{user_id}> (@{member_row['inviter_id'] if member_row and member_row.get('inviter_id') else user_id}) salió del servidor.")