import discord
from discord.ext import tasks
from src.database import (
    db, get_setting, log_to_channel, CHANNELS, ROLES, GUILDS
)
from src.utils.logger import logger
from src.utils.rate_limiter import rate_limiter
from src.commands.giveaway_commands import process_expired_giveaways, process_cancelled_giveaways

async def ensure_member_apply_message(bot, guild):
    """Verifica y envía mensaje de postulación de miembro"""
    try:
        channel_id = await bot.get_channel(CHANNELS["member_apply"])
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return
        
        # Verificar si ya existe el mensaje
        message_id = await get_apply_message_id(guild.id)
        if message_id:
            try:
                existing = await channel.fetch_message(message_id)
                if existing:
                    logger.info(f"Mensaje de postulación miembro ya existe en {channel.id}")
                    return
            except:
                logger.warning(f"Mensaje de postulación miembro no encontrado, reenviando...")
        
        embed = discord.Embed(
            title="🟣 Postulación a Miembro AEGOX",
            color=0x8B00FF,
            description=(
                "🟣 ¿Querés ser parte de AEGOX?\n\n"
                "¿Tenés ganas de competir, construir y dominar GolemMC con un clan organizado?\n\n"
                "En AEGOX tenemos roles reales, rangos, ascensos, guerras, KOTHs y eventos todas las semanas.\n\n"
                "📋 REQUISITOS RÁPIDOS\n"
                "• Tener 13+ años\n"
                "• Estar en el Discord de AEGOX\n"
                "• Llevar mínimo 3 días en el Discord\n"
                "• Tener actividad en GolemMC\n"
                "• No estar en blacklist\n\n"
                "🎯 ELEGÍ TU ROL\n"
                "⚔️ Guerrero - PvP, guerras y KOTHs\n"
                "🏗️ Builder - Construcción y bases\n"
                "🌾 Farmer - Granjas y economía\n\n"
                "Apretá el botón de abajo y completá tu postulación por DM. El staff la revisa en 24-48hs.\n\n"
                "AEGOX | GolemMC • FUERZA. HONOR. VICTORIA."
            ),
            footer=discord.Footer(text="AEGOX CLAN")
        )
        
        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="Postularse",
            style=discord.ButtonStyle.success,
            custom_id="member_apply_start",
            emoji="📝"
        ))
        
        message = await channel.send(embed=embed, view=view)
        
        # Guardar message_id en DB
        from src.database import db
        await db.execute(
            "INSERT OR REPLACE INTO settings (guild_id, key, value) VALUES (?, ?, ?)",
            [guild.id, "MEMBER_APPLY_MESSAGE_ID", str(message.id)]
        )
        logger.info(f"Mensaje de postulación miembro enviado en {channel.id}")
        
    except Exception as e:
        logger.error(f"Error en ensure_member_apply_message: {e}")

async def ensure_staff_apply_message(bot, guild):
    """Verifica y envía mensaje de postulación de staff"""
    try:
        channel_id = CHANNELS["staff_apply"]
        channel = guild.get_channel(channel_id)
        if not channel:
            return
        
        # Verificar si ya existe
        # (implementar check similar al de miembro)
        
        embed = discord.Embed(
            title="🛡️ Postulación a Staff AEGOX",
            color=0xFF6B00,
            description=(
                "🛡️ ¿Querés ser Staff de AEGOX?\n\n"
                "¿Ya sos parte de AEGOX y querés ayudar a que el clan crezca?\n\n"
                "Ser Staff no es solo tener rango, es ayudar, moderar, revisar postulaciones y representar al clan.\n\n"
                "📋 REQUISITOS RÁPIDOS\n"
                "• Ser miembro de AEGOX hace mínimo 14 días\n"
                "• Tener 15+ años\n"
                "• Llevar mínimo 20 días en el Discord\n"
                "• Tener actividad alta en Discord y GolemMC\n"
                "• No tener sanciones graves\n"
                "• Tener buena comunicación y respeto\n\n"
                "🎯 PUESTOS DE STAFF\n"
                "🛡️ Moderador - Modera chat y ayuda a miembros\n"
                "📋 Reclutador - Revisa postulaciones de miembros\n"
                "🎬 Staff de Eventos - Organiza KOTHs y eventos\n"
                "🎥 Staff Media - Clips, TikToks y publicidad\n\n"
                "Apretá el botón de abajo y completá tu postulación por DM. Solo el staff superior la puede ver.\n\n"
                "AEGOX | GolemMC • Solo para miembros de AEGOX"
            ),
            footer=discord.Footer(text="AEGOX CLAN")
        )
        
        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="Postularse a Staff",
            style=discord.ButtonStyle.primary,
            custom_id="staff_apply_start",
            emoji="⚔️"
        ))
        
        channel_id = CHANNELS["staff_apply"]
        channel = guild.get_channel(channel_id)
        if channel:
            message = await channel.send(embed=embed, view=discord.ui.View())
            logger.info(f"Mensaje de postulación staff enviado en {channel.id}")
    except Exception as e:
        logger.error(f"Error en ensure_staff_apply_message: {e}")

async def setup_presence(bot):
    """Configura la presencia del bot"""
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="al mejor clan de golemmc"
        )
    )
    try:
        await bot.user.edit(username="BOT DEL MEJOR CLAN DE GOLEMMC")
    except:
        pass  # Ignorar si no puede cambiar nombre

async def setup_apply_messages(bot):
    """Verifica y envía mensajes de postulación al arrancar"""
    guild = bot.get_guild(GUILDS["clan"])
    if guild:
        await ensure_member_apply_message(bot, guild)
        await ensure_staff_apply_message(bot, guild)

# ============================================================
# EVENTO READY
# ============================================================

async def on_ready(bot):
    logger.info(f"AEGOX CLAN BOT online - {bot.user} conectado a {len(bot.guilds)} servidor(es).")
    
    # Configurar presencia
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="al mejor clan de golemmc"
        )
    )
    try:
        await bot.user.edit(username="BOT DEL MEJOR CLAN DE GOLEMMC")
    except:
        pass
    
    # Verificar y enviar mensajes de postulación
    for guild in bot.guilds:
        await ensure_member_apply_message(bot, guild)
        await ensure_staff_apply_message(bot, guild)
    
    # Iniciar tareas en background
    giveaway_task.start(bot)
    trial_task.start()
    announce_task.start()
    backup_task.start()
    invite_cache_task.start()
    top_invites_task.start()

# ============================================================
# TAREAS PROGRAMADAS (LOOPS)
# ============================================================

@tasks.loop(seconds=30)
async def giveaway_task(bot):
    """Procesa sorteos expirados y cancelados cada 30s"""
    for guild in bot.guilds:
        try:
            await process_expired_giveaways(guild)
            await process_cancelled_giveaways(guild)
        except Exception as e:
            logger.error(f"Error en giveaway_task para guild: {e}")

@tasks.loop(hours=24)
async def trial_task():
    """Procesa trials de staff expirados cada 24h"""
    from src.database import db
    for guild_id in [GUILDS["clan"], GUILDS["staff"]]:
        try:
            expired_trials = await db.fetchall(
                "SELECT * FROM staff_trials WHERE guild_id = ? AND ends_at <= ?",
                [guild_id, int(__import__('time').time() * 1000)]
            )
            # ... procesar trials
        except Exception as e:
            logger.error(f"Error en trial_task para guild: {e}")

@tasks.loop(minutes=1)
async def announce_task():
    """Publica anuncios programados cada minuto"""
    from src.database import db
    for guild_id in [GUILDS["clan"], GUILDS["staff"]]:
        try:
            scheduled = await db.fetchall(
                "SELECT * FROM announcements WHERE guild_id = ? AND status = 'programado' AND scheduled_at <= ?",
                [guild_id, int(__import__('time').time() * 1000)]
            )
            for ann in scheduled:
                await publish_scheduled_announcement(guild_id, ann)
        except Exception as e:
            logger.error(f"Error en announce_task para guild: {e}")

@tasks.loop(hours=1)
async def invite_cache_task():
    """Actualiza cache de invites cada hora"""
    # Se actualiza via eventos inviteCreate/inviteDelete/inviteUpdate
    pass

@tasks.loop(hours=1)
async def top_invites_task():
    """Actualiza top de invites cada hora"""
    for guild_id in [GUILDS["clan"]]:
        try:
            await update_top_invites_embed(guild_id)
        except Exception as e:
            logger.error(f"Error actualizando top invites: {e}")

@tasks.loop(time=discord.time(hour=3, minute=0))
async def backup_task():
    """Backup diario a las 03:00"""
    try:
        await create_backup_auto()
    except Exception as e:
        logger.error(f"Error en backup automático: {e}")

# Funciones auxiliares para tasks
async def process_expired_giveaways(guild):
    from src.database import db
    expired = await db.fetchall(
        "SELECT * FROM giveaways WHERE guild_id = ? AND status = 'activo' AND ends_at <= ?",
        [guild.id, int(__import__('time').time() * 1000)]
    )
    for giveaway in expired:
        # ... procesar sorteo finalizado
        pass

async def process_cancelled_giveaways(guild):
    from src.database import db
    expired = await db.fetchall(
        "SELECT * FROM giveaways WHERE guild_id = ? AND status = 'activo' AND ends_at <= ?",
        [guild.id, int(__import__('time').time() * 1000)]
    )
    for giveaway in expired:
        entries = await db.fetchall(
            "SELECT user_id FROM giveaway_entries WHERE giveaway_id = ? AND guild_id = ?",
            [giveaway["id"], guild.id]
        )
        if not entries:
            # Cancelar por falta de participantes
            pass

def setup_events(bot):
    """Registra todos los event listeners"""
    bot.add_listener(on_ready, "on_ready")
    bot.add_listener(on_guild_member_add, "on_member_join")
    bot.add_listener(on_guild_member_remove, "on_member_remove")
    bot.add_listener(on_interaction, "on_interaction")
    bot.add_listener(on_invite_create, "on_invite_create")
    bot.add_listener(on_invite_delete, "on_invite_delete")
    bot.add_listener(on_invite_update, "on_invite_update")
    
    # Registrar tasks
    giveaway_task.start()
    trial_task.start()
    announce_task.start()
    backup_task.start()
    top_invites_task.start()

# Handlers de eventos
async def on_ready(bot):
    logger.info(f"AEGOX CLAN BOT online - {bot.user} conectado a {len(bot.guilds)} servidor(es).")
    
    # Presencia
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="al mejor clan de golemmc"
        )
    )
    try:
        await bot.user.edit(username="BOT DEL MEJOR CLAN DE GOLEMMC")
    except:
        pass
    
    # Mensajes de postulación
    for guild in bot.guilds:
        await ensure_member_apply_message(bot, guild)
        await ensure_staff_apply_message(bot, guild)
    
    # Iniciar loops
    giveaway_task.start()
    trial_task.start()
    announce_task.start()
    backup_task.start()
    top_invites_task.start()

async def on_guild_member_add(member):
    """Bienvenida + tracking de invites"""
    guild = member.guild
    guild_id = guild.id
    user_id = str(member.id)
    joined_at = int(__import__('time').time() * 1000)
    
    # Rol automático
    auto_role_id = ROLES["auto_role"]
    role = member.guild.get_role(auto_role_id)
    if role:
        try:
            await member.add_roles(role, reason="AEGOX Auto Role")
        except:
            pass
    
    # Guardar usuario
    from src.database import db
    await db.execute(
        "INSERT OR REPLACE INTO users (user_id, guild_id, username, joined_at) VALUES (?, ?, ?, ?)",
        [str(member.id), guild_id, member.name, int(__import__('time').time() * 1000)]
    )
    
    # Log bienvenida
    from src.database import log_event
    await log_event(guild_id, "welcome", f"{member.name} ({user_id}) se unió al servidor.")
    
    # Embed bienvenida
    from src.config.ids import CHANNELS
    welcome_embed = discord.Embed(
        title="Bienvenido(a) a AEGOX",
        color=0x8b00ff,
        description=(
            f"👋 Hola {member.mention} bienvenido(a) a AEGOX!\n"
            "Recuerda leer las reglas para evitar inconvenientes.\n"
            "Activa las alertas para estar al día de todo!"
        )
        .set_thumbnail(member.display_avatar.url)
        .set_footer(text=f"Bienvenido el {datetime.now().strftime('%d/%m/%Y')}")
    
    welcome_channel = member.guild.get_channel(CHANNELS["welcome"])
    if welcome_channel:
        await welcome_channel.send(embed=welcome_embed)
    
    # DM
    try:
        await member.send(embed=welcome_embed)
    except:
        pass
    
    # Tracking de invites
    try:
        fresh_invites = await guild.invites()
        from src.utils.invite_cache import invite_cache
        cache = invite_cache.get(guild_id, {})
        
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
        
        # Actualizar cache
        new_cache = {}
        for invite in fresh_invites:
            new_cache[invite.code] = {
                "code": invite.code,
                "inviter_id": str(invite.inviter.id) if invite.inviter else None,
                "uses": invite.uses or 0,
            }
        from src.utils.invite_cache import invite_cache
        invite_cache[guild_id] = new_cache
        
        inviter_id = used_invite["inviter_id"] if used_invite else None
        account_age = __import__('time').time() * 1000 - member.created_at.timestamp() * 1000
        is_fake = account_age < 3 * 24 * 60 * 60 * 1000
        
        # Guardar en invite_members
        await db.execute(
            """INSERT INTO invite_members (user_id, guild_id, inviter_id, code, joined_at, left_at, is_fake)
               VALUES (?, ?, ?, ?, ?, NULL, ?)
               ON CONFLICT(user_id, guild_id) DO UPDATE SET
                 inviter_id = excluded.inviter_id,
                 code = excluded.code,
                 joined_at = excluded.joined_at,
                 left_at = NULL,
                 is_fake = excluded.is_fake""",
            [user_id, guild_id, inviter_id, used_invite["code"] if used_invite else None, 
             int(__import__('time').time() * 1000), 1 if is_fake else 0]
        )
        
        # Actualizar stats del inviter
        if inviter_id:
            stats = await get_invite_stats(guild_id, inviter_id)
            total = (stats.get("total", 0) or 0) + 1
            valid = is_fake * (stats.get("valid", 0) or 0) + (not is_fake) * ((stats.get("valid", 0) or 0) + 1)
            fake = is_fake * ((stats.get("fake", 0) or 0) + 1) + (not is_fake) * (stats.get("fake", 0) or 0)
            
            await upsert_invite(guild_id, inviter_id, used_invite["code"], total, valid, fake, stats.get("left", 0))
        
        # Log invite
        invite_log_channel = guild.get_channel(CHANNELS["invites_log"])
        if invite_log_channel:
            if inviter_id:
                stats = await get_invite_stats(guild_id, inviter_id)
                await invite_log_channel.send(f"<@{member.id}> fue invitado por <@{inviter_id}> quien ahora tiene {stats.get('valid', 0)} invites.")
            else:
                await invite_log_channel.send(f"<@{member.id}> entró sin invite.")
    except Exception as e:
        logger.error(f"Error en on_guild_member_add: {e}")

async def on_guild_member_remove(member):
    """Salida de miembro + limpieza invites + giveaways"""
    guild = member.guild
    guild_id = guild.id
    user_id = str(member.id)
    
    from src.database import db, log_event, get_invite_stats, upsert_invite, remove_giveaway_entry
    
    member_row = await db.fetchone(
        "SELECT * FROM invite_members WHERE user_id = ? AND guild_id = ?",
        [user_id, guild_id]
    )
    
    if member_row and member_row["inviter_id"]:
        stats = await get_invite_stats(guild_id, member_row["inviter_id"])
        valid = member_row["is_fake"] * (stats.get("valid", 0) or 0) + (1 - member_row["is_fake"]) * max(0, (stats.get("valid", 0) or 0) - 1)
        left = (stats.get("left", 0) or 0) + 1
        
        await upsert_invite(guild_id, member_row["inviter_id"], member_row["code"] or "", 
                           stats.get("total", 0), valid, stats.get("fake", 0), left)
    
    await db.execute(
        "UPDATE invite_members SET left_at = ? WHERE user_id = ? AND guild_id = ?",
        [int(__import__('time').time() * 1000), user_id, guild_id]
    )
    
    # Remover entradas de giveaway
    try:
        entries = await db.fetchall(
            "SELECT giveaway_id FROM giveaway_entries WHERE user_id = ? AND guild_id = ?",
            [user_id, guild_id]
        )
        for entry in entries:
            await remove_giveaway_entry(entry["giveaway_id"], user_id, guild_id)
    except Exception as e:
        logger.error(f"Error removiendo entradas de giveaway: {e}")
    
    # Log
    invite_log_channel = member.guild.get_channel(CHANNELS["invites_log"])
    if invite_log_channel and invite_log_channel.is_text():
        if member_row and member_row["inviter_id"]:
            stats = await get_invite_stats(guild_id, member_row["inviter_id"])
            await invite_log_channel.send(f"<@{user_id}> salió. {stats.get('valid', 0)} invites válidas.")
        else:
            await invite_log_channel.send(f"<@{user_id}> salió del servidor.")
    
    await log_event(member.guild.id, "invite_leave", f"<@{user_id}> salió del servidor.")

async def on_interaction(interaction):
    """Maneja todas las interacciones (botones, modales, comandos)"""
    if interaction.type == discord.InteractionType.application_command:
        # Comandos slash - manejados por bot.tree
        return
    
    if interaction.type == discord.InteractionType.component:
        await handle_button(interaction)
    elif interaction.type == discord.InteractionType.modal_submit:
        await handle_modal(interaction)

async def on_invite_create(invite):
    from src.utils.invite_cache import update_invite_cache
    update_invite_cache(invite.guild.id, invite.code, invite.inviter.id if invite.inviter else None, invite.uses)

async def on_invite_delete(invite):
    from src.utils.invite_cache import delete_invite_cache
    delete_invite_cache(invite.guild.id, invite.code)

async def on_invite_update(invite):
    from src.utils.invite_cache import update_invite_cache
    update_invite_cache(invite.guild.id, invite.code, invite.inviter.id if invite.inviter else None, invite.uses)

# Import necesarios al final para evitar imports circulares
from src.database import (
    db, get_setting, set_setting, log_event, log_to_channel,
    get_invite_stats, upsert_invite, get_invite_member, upsert_invite_member,
    get_invite_stats, upsert_invite, get_invite_top_message, save_invite_top_message,
    get_invite_member, upsert_invite_member, get_suggestion, create_suggestion,
    update_suggestion, update_suggestion_message, get_user_vote, set_user_vote,
    get_vote_count, apply_vote, get_member_application, get_pending_application,
    create_member_application, update_member_application, set_application_message_id,
    get_apply_message_id, get_rejection_info, upsert_rejection_info, calculate_next_allowed,
    is_blacklisted, add_to_blacklist, remove_from_blacklist, get_blacklist,
    get_staff_application, get_pending_staff_application, create_staff_application,
    update_staff_application, set_staff_application_message_id,
    get_staff_application_message_id, create_staff_trial, get_active_staff_trials,
    remove_staff_trial, get_staff_trial,
    create_announcement, get_announcement, get_announcement_by_message_id,
    get_announcements, update_announcement, delete_announcement,
    get_scheduled_announcements, get_allowed_roles_for_announcements,
    create_giveaway, get_giveaway, get_giveaway_by_message_id, get_active_giveaways,
    get_all_giveaways, update_giveaway, add_giveaway_entry, remove_giveaway_entry,
    has_user_entered, get_entry_count, get_all_entries, get_allowed_roles_for_giveaways,
    get_apply_message_id, set_apply_message_id, get_staff_application_message_id,
    set_staff_application_message_id
)
from src.utils.logger import logger
from src.config.ids import CHANNELS, ROLES, GUILDS, APPLY_MESSAGES
from src.utils.rate_limiter import rate_limiter, COMMAND_COOLDOWN, SUGGESTION_APPLICATION_COOLDOWN
from src.utils.invite_cache import invite_cache, update_invite_cache, delete_invite_cache, get_invites