"""Interactive officer controls attached to each spam notice.

Three buttons: **Kick** (remove them; they can rejoin), **Ban** (permanent block),
and **Not spam** (dismiss a false positive). All are gated to officers who hold
Kick/Ban permission, and clicking any one resolves the notice — it records who
acted and disables the buttons so two officers don't double-act.
Manual officer actions remain available in dry-run mode.

Note: the view is bound to the running bot process. If the bot restarts, buttons
on old notices stop responding (Discord shows "interaction failed"); officers can
still kick/ban manually. Persisting them across restarts isn't worth the complexity
for a club-sized server.
"""

from __future__ import annotations

import logging

import discord

logger = logging.getLogger(__name__)


class OfficerActionView(discord.ui.View):
    def __init__(self, *, target_user_id: int, target_label: str) -> None:
        super().__init__(timeout=None)
        self._target_user_id = target_user_id
        self._target_label = target_label

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        perms = getattr(interaction.user, "guild_permissions", None)
        if perms and (perms.ban_members or perms.kick_members):
            return True
        await interaction.response.send_message(
            "You need Kick or Ban Members permission to use these controls.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(label="Kick", style=discord.ButtonStyle.primary, emoji="👢")
    async def kick(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("No guild context.", ephemeral=True)
            return
        try:
            await guild.kick(
                discord.Object(id=self._target_user_id),
                reason=f"Spam joiner — kicked by {interaction.user} via spam-remover",
            )
        except discord.HTTPException:
            logger.exception("Kick failed for user %s", self._target_user_id)
            await interaction.response.send_message(
                "Kick failed — they may already be gone, or I need Kick Members "
                "permission with my role above the target.",
                ephemeral=True,
            )
            return
        await self._resolve(interaction, f"👢 Kicked by {interaction.user.mention}")

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, emoji="🔨")
    async def ban(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("No guild context.", ephemeral=True)
            return
        try:
            await guild.ban(
                discord.Object(id=self._target_user_id),
                reason=f"Spam joiner — banned by {interaction.user} via spam-remover",
            )
        except discord.HTTPException:
            logger.exception("Ban failed for user %s", self._target_user_id)
            await interaction.response.send_message(
                "Ban failed — check that I have Ban Members permission and that my "
                "role is above the target.",
                ephemeral=True,
            )
            return
        await self._resolve(interaction, f"🔨 Banned by {interaction.user.mention}")

    @discord.ui.button(label="Not spam", style=discord.ButtonStyle.secondary, emoji="✅")
    async def not_spam(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._resolve(
            interaction, f"✅ Marked **not spam** by {interaction.user.mention}"
        )

    async def _resolve(self, interaction: discord.Interaction, note: str) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        self.stop()

        message = interaction.message
        embed = message.embeds[0] if message and message.embeds else None
        if embed is not None:
            embed.add_field(name="Resolution", value=note, inline=False)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.edit_message(view=self)
