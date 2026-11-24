"""
Cog: Invites
"""
import discord
from discord import app_commands
from src.config import config
from src.database import get_setting, get_invite_stats
from src.utils.logger import logger

class InvitesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="invites", description="Consulta las invites de AEGOX")
    @app_commands.describe(usuario="Usuario a consultar (opcional, solo owner para ver de otros)")
    async def invites(self, interaction: discord.Interaction, usuario: discord.User = None):
        target = usuario or interaction.user
        is_owner = interaction.user.id == config.OWNER_ID
        
        if target.id != interaction.user.id and not is_owner:
            return await interaction.response.send_message("No tenés permisos para ver las invites de otro usuario.", ephemeral=True)
        
        from src.database import get_invite_stats
        stats = await get_invite_stats(interaction.guild_id, str(target.id))
        
        embed = discord.Embed(
            title=f"📊 Invites de {target.display_name}",
            color=0x8B00FF,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="✅ Válidas", value=str(stats.get("valid", 0)), inline=True)
        embed.add_field(name="👻 Fakes", value=str(stats.get("fake", 0)), inline=True)
        embed.add_field(name="🚪 Se fueron", value=str(stats.get("left", 0)), inline=True)
        embed.add_field(name="📊 Total", value=str(stats.get("total", 0)), inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="top-invites", description="Ver top de invitadores")
    async def top_invites(self, interaction: discord.Interaction):
        from src.database import db
        guild_id = interaction.guild_id
        
        rows = await db.fetchall(
            "SELECT inviter_id, code, total, valid, fake, left FROM invites WHERE guild_id = ? ORDER BY valid DESC LIMIT 10",
            [interaction.guild_id]
        )
        
        embed = discord.Embed(
            title="🏆 Top Invitadores AEGOX",
            color=0x8B00FF,
            description="Los mejores invitadores del clan (solo cuentan miembros que siguen en el DC)"
        )
        
        if not rows:
            embed.description = "Todavía no hay invites registrados."
        else:
            for i, row in enumerate(rows, 1):
                inviter = interaction.guild.get_member(int(row["inviter_id"]))
                name = inviter.display_name if inviter else f"Usuario {row['inviter_id']}"
                embed.add_field(
                    name=f"#{i} {name}",
                    value=f"✅ {row['valid']} | 👻 {row['fake']} | 🚪 {row['left']} | 📊 {row['total']}",
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    from src.config import config
    await bot.add_cog(InvitesCog(bot))