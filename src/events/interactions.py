"""
Manejo de interacciones: botones, modales, comandos slash
"""
import discord
import time
import json
from src.database import db, get_setting, log_event, log_to_channel
from src.config.ids import CHANNELS, ROLES, GUILDS, VERIFIED_ROLE_ID
from src.utils.logger import logger
from src.utils.anti_alt import anti_alt_detector
from src.utils.web_verification import web_verification_system
from src.config import config

async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.application_command:
        return  # Manejado por bot.tree
    
    if interaction.type == discord.InteractionType.component:
        await handle_button(interaction)
    elif interaction.type == discord.InteractionType.modal_submit:
        await handle_modal(interaction)

async def handle_button(interaction):
    custom_id = interaction.custom_id
    
    try:
        # ===== SUGERENCIAS =====
        if custom_id.startswith("sugvote:") or custom_id.startswith("sugdec:"):
            await handle_suggestion_button(interaction)
        
        # ===== POSTULACIONES MIEMBRO =====
        elif custom_id.startswith("member_apply_start"):
            from src.cogs.clan_applications import start_member_application
            await start_member_application(interaction)
        
        elif custom_id.startswith("member_approve:"):
            app_id = int(custom_id.split(":")[1])
            from src.cogs.clan_applications import handle_member_approve
            await handle_member_approve(interaction, app_id)
        
        elif custom_id.startswith("member_reject:"):
            app_id = int(custom_id.split(":")[1])
            from src.cogs.clan_applications import show_member_reject_modal
            await show_member_reject_modal(interaction, app_id)
        
        # ===== POSTULACIONES STAFF =====
        elif custom_id.startswith("staff_apply_start"):
            from src.cogs.staff_applications import start_staff_application
            await start_staff_application(interaction)
        
        elif custom_id.startswith("staff_approve:"):
            app_id = int(custom_id.split(":")[1])
            from src.cogs.staff_applications import handle_staff_approve
            await handle_staff_approve(interaction, app_id)
        
        elif custom_id.startswith("staff_reject:"):
            app_id = int(custom_id.split(":")[1])
            from src.cogs.staff_applications import show_staff_reject_modal
            await show_staff_reject_modal(interaction, app_id)
        
        # ===== SORTEOS =====
        elif custom_id.startswith("gw_join:"):
            gw_id = int(custom_id.split(":")[1])
            from src.cogs.giveaways import handle_giveaway_join
            await handle_giveaway_join(interaction, gw_id)
        
        elif custom_id.startswith("gw_reroll:"):
            gw_id = int(custom_id.split(":")[1])
            from src.cogs.giveaways import handle_giveaway_reroll
            await handle_giveaway_reroll(interaction, gw_id)
        
        # ===== TICKETS =====
        elif custom_id.startswith("ticket_close:"):
            ticket_id = int(custom_id.split(":")[1])
            from src.cogs.tickets import handle_ticket_close
            await handle_ticket_close(interaction, ticket_id)
        
        elif custom_id.startswith("ticket_claim:"):
            ticket_id = int(custom_id.split(":")[1])
            from src.cogs.tickets import handle_ticket_claim
            await handle_ticket_claim(interaction, ticket_id)
        
        elif custom_id.startswith("ticket_transcript:"):
            ticket_id = int(custom_id.split(":")[1])
            from src.cogs.tickets import handle_ticket_transcript
            await handle_ticket_transcript(interaction, ticket_id)
        
        # ===== ANUNCIOS =====
        elif custom_id.startswith("spoiler_view:"):
            ann_id = int(custom_id.split(":")[1])
            from src.cogs.announcements import handle_spoiler_view
            await handle_spoiler_view(interaction, ann_id)
        
        elif custom_id.startswith("announce_edit:"):
            ann_id = int(custom_id.split(":")[1])
            from src.cogs.announcements import show_announcement_edit_modal
            await show_announcement_edit_modal(interaction, ann_id)
        
        # ===== VERIFICACIÓN =====
        elif custom_id == "verify_start":
            from src.cogs.verification import start_verification
            await start_verification(interaction)
    
    except Exception as e:
        logger.error(f"Error en botón {custom_id}: {e}")
        try:
            await interaction.response.send_message("❌ Error procesando la acción", ephemeral=True)
        except:
            pass

async def handle_modal(interaction):
    custom_id = interaction.custom_id
    
    try:
        if custom_id.startswith("member_reject_modal:"):
            app_id = int(custom_id.split(":")[1])
            motivo = interaction.data["components"][0]["components"][0]["value"]
            from src.cogs.clan_applications import handle_member_reject_modal
            await handle_member_reject_modal(interaction, app_id, motivo)
        
        elif custom_id.startswith("staff_reject_modal:"):
            app_id = int(custom_id.split(":")[1])
            motivo = interaction.data["components"][0]["components"][0]["value"]
            from src.cogs.staff_applications import handle_staff_reject_modal
            await handle_staff_reject_modal(interaction, app_id, motivo)
        
        elif custom_id.startswith("announce_create:"):
            from src.cogs.announcements import handle_announcement_create_modal
            await handle_announcement_create_modal(interaction)
        
        elif custom_id.startswith("announce_schedule:"):
            from src.cogs.announcements import handle_announcement_schedule_modal
            await handle_announcement_schedule_modal(interaction)
        
        elif custom_id.startswith("announce_edit:"):
            from src.cogs.announcements import handle_announcement_edit_modal
            await handle_announcement_edit_modal(interaction)
        
        elif custom_id == "gw_create_modal":
            from src.cogs.giveaways import handle_giveaway_create_modal
            await handle_giveaway_create_modal(interaction)
        
        elif custom_id == "ticket_close_modal":
            ticket_id = int(interaction.custom_id.split(":")[1])
            motivo = interaction.data["components"][0]["components"][0]["value"]
            from src.cogs.tickets import handle_ticket_close_modal
            await handle_ticket_close_modal(interaction, ticket_id, motivo)
        
        elif custom_id == "verification_modal":
            from src.cogs.verification import handle_verification_modal
            await handle_verification_modal(interaction)
    
    except Exception as e:
        logger.error(f"Error en modal {custom_id}: {e}")
        try:
            await interaction.response.send_message("❌ Error procesando formulario", ephemeral=True)
        except:
            pass

# Helpers para sugerencias
async def handle_suggestion_button(interaction):
    from src.database import db, get_suggestion, update_suggestion, get_user_vote, set_user_vote, get_vote_count, apply_vote
    from src.utils.logger import logger
    
    parts = interaction.custom_id.split(":")
    action = parts[0]
    sub = parts[1]
    suggestion_id = int(parts[2])
    
    suggestion = await get_suggestion(suggestion_id)
    if not suggestion:
        return await interaction.response.send_message("Sugerencia no encontrada.", ephemeral=True)
    
    if action == "sugvote":
        await apply_vote(suggestion_id, interaction.user.id, sub)
        updated = await get_suggestion(suggestion_id)
        embed = discord.Embed(
            title=f"Sugerencia #{suggestion_id}",
            description=suggestion["text"],
            color=0xFFFF00 if suggestion["status"] == "pendiente" else (0x00FF00 if suggestion["status"] == "aprobada" else 0xFF0000),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Estado", value="⏳ Pendiente" if suggestion["status"] == "pendiente" else ("✅ Aprobada" if suggestion["status"] == "aprobada" else "❌ Rechazada"), inline=True)
        embed.add_field(name="Votos", value=f"👍 {updated['up']} | 👎 {updated['down']}", inline=True)
        await interaction.message.edit(embed=embed, view=discord.ui.View())
        return
    
    if action == "sugdec":
        reviewer_role = config.roles["reviewer_member"]
        if not (interaction.user.id == config.OWNER_ID or 
               any(r.id == reviewer_role for r in interaction.user.roles)):
            return await interaction.response.send_message("No tenés permisos.", ephemeral=True)
        
        status = sub == "aprobar" and "aprobada" or "rechazada"
        color = 0x00FF00 if sub == "aprobar" else 0xFF0000
        await update_suggestion(suggestion_id, status, interaction.user.id, int(time.time() * 1000))
        updated = await get_suggestion(suggestion_id)
        
        embed = discord.Embed(
            title=f"Sugerencia #{suggestion_id}",
            description=updated["text"],
            color=color,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Estado", value="✅ Aprobada" if status == "aprobada" else "❌ Rechazada", inline=True)
        embed.add_field(name="Votos", value=f"👍 {updated['up']} | 👎 {updated['down']}", inline=True)
        
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="👍 A favor", style=discord.ButtonStyle.success, custom_id=f"sugvote:up:{suggestion_id}", disabled=True))
        view.add_item(discord.ui.Button(label="👎 En contra", style=discord.ButtonStyle.danger, custom_id=f"sugvote:down:{suggestion_id}", disabled=True))
        view.add_item(discord.ui.Button(label="✅ Aprobar", style=discord.ButtonStyle.primary, custom_id=f"sugdec:aprobar:{suggestion_id}", disabled=True))
        view.add_item(discord.ui.Button(label="❌ Rechazar", style=discord.ButtonStyle.danger, custom_id=f"sugdec:rechazar:{suggestion_id}", disabled=True))
        
        await interaction.message.edit(embed=embed, view=discord.ui.View())
        
        from src.database import log_event
        await log_event(interaction.guild_id, "suggestion", f"Sugerencia #{suggestion_id} {status} por {interaction.user.mention}")
        
        try:
            author = await interaction.client.fetch_user(suggestion["user_id"])
            await author.send(f"Tu sugerencia #{suggestion_id} fue {status}.")
        except:
            pass