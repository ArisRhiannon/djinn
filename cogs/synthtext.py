"""
Cog: SynthText — Genera GIFs animados con texto en escenas temáticas.

/texto escena:<synthwave|lluvia|dream|infierno> principal:<texto> [subtexto] [imagen]

- synthwave: outrun retro (original renderer, 24fps, full effects)
- lluvia/dream/infierno: isometric 3D pixel art (15fps, voxel engine)
"""
from __future__ import annotations

import asyncio
import io
import math
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageFont
import numpy as np

_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="synth")

SCENE_CHOICES = [
    app_commands.Choice(name="Synthwave (retro outrun)", value="synthwave"),
    app_commands.Choice(name="Lluvia (cozy pixel art)", value="lluvia"),
    app_commands.Choice(name="Dream (floating islands)", value="dream"),
]


def _generate_gif(scene_name: str, title_text: str, sub_text: str, user_image_bytes: Optional[bytes]) -> bytes:
    """Generate full GIF in thread pool."""
    user_img = None
    if user_image_bytes:
        user_img = Image.open(io.BytesIO(user_image_bytes)).convert('RGBA')
        user_img.thumbnail((256, 256), Image.LANCZOS)

    frames = []

    if scene_name == "synthwave":
        # Original synthwave renderer (24fps, full post-processing pipeline)
        from utils import scene_synthwave as scene

        FPS_S = 24
        N_S = int(FPS_S * 4.0)
        FW, FH = 640 * 2, 360 * 2

        FONT_SUB = "/usr/share/fonts/truetype/lato/Lato-BlackItalic.ttf"
        if not os.path.exists(FONT_SUB):
            FONT_SUB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"

        for i in range(N_S):
            t = i / N_S
            bg, horizon_y = scene.build_background(t)
            canvas = bg
            canvas = Image.alpha_composite(canvas, scene.stars_layer(t))
            canvas = Image.alpha_composite(canvas, scene.grid_layer(t, horizon_y))
            canvas = Image.alpha_composite(canvas, scene.particles_layer(t))

            # Title
            fs = int(FW * 0.185)
            if len(title_text) > 6:
                fs = int(fs * 6 / len(title_text))
            depth = max(6, int(fs * 0.22))
            title_img = scene.make_extruded_title(title_text.upper(), fs, depth=depth, dx=-2, dy=2)
            scale = 1.0 + 0.015 * math.sin(2 * math.pi * 2 * t)
            ty = int(4 * 2 * math.sin(2 * math.pi * t))
            tx = int(2 * 2 * math.sin(2 * math.pi * t + math.pi / 2))
            tw0, th0 = title_img.size
            tw, th = max(1, int(tw0 * scale)), max(1, int(th0 * scale))
            title_scaled = title_img.resize((tw, th), Image.LANCZOS)
            shadow_mask = title_scaled.split()[3].filter(ImageFilter.GaussianBlur(12))
            sh_arr = np.zeros((th, tw, 4), dtype=np.uint8)
            sh_arr[:, :, 3] = (np.array(shadow_mask) * 0.7).astype(np.uint8)
            shadow = Image.fromarray(sh_arr, 'RGBA')
            title_x = (FW - tw) // 2 + tx
            title_y = int(FH * 0.28) + ty
            canvas.alpha_composite(shadow, (title_x + 8, title_y + 16))
            canvas.alpha_composite(title_scaled, (title_x, title_y))

            # Subtitle
            if sub_text:
                sub_font = ImageFont.truetype(FONT_SUB, int(FW * 0.062))
                if len(sub_text) > 12:
                    sub_font = ImageFont.truetype(FONT_SUB, int(FW * 0.062 * 12 / len(sub_text)))
                bb = ImageDraw.Draw(Image.new('RGBA', (4, 4))).textbbox((0, 0), sub_text, font=sub_font, stroke_width=int(FW * 0.004))
                sw, sh_ = bb[2] - bb[0], bb[3] - bb[1]
                sub_img = Image.new('RGBA', (sw + 40, sh_ + 40), (0, 0, 0, 0))
                ImageDraw.Draw(sub_img).text((20 - bb[0], 20 - bb[1]), sub_text, font=sub_font,
                        fill=(255, 225, 240, 255), stroke_width=max(2, int(FW * 0.004)), stroke_fill=(60, 10, 80, 255))
                glow_sub = sub_img.filter(ImageFilter.GaussianBlur(6))
                glow_sub = ImageChops.multiply(glow_sub, Image.new('RGBA', glow_sub.size, (255, 150, 255, 180)))
                sub_compose = Image.alpha_composite(glow_sub, sub_img)
                canvas.alpha_composite(sub_compose, ((FW - sub_compose.width) // 2, title_y + th - int(FH * 0.01) + int(6 * math.sin(2 * math.pi * t + math.pi))))

            # User image (top-right, after title so it's visible)
            if user_img:
                ph_size = int(FW * 0.13)
                photo = user_img.resize((ph_size, ph_size), Image.LANCZOS)
                glow = Image.new('RGBA', (ph_size + 20, ph_size + 20), (0, 0, 0, 0))
                ImageDraw.Draw(glow).rectangle([0, 0, ph_size + 19, ph_size + 19], fill=(100, 220, 255, 40))
                glow = glow.filter(ImageFilter.GaussianBlur(8))
                glow.alpha_composite(photo, (10, 10))
                canvas.alpha_composite(glow, (int(FW * 0.82), int(FH * 0.05) + int(5 * math.sin(2 * math.pi * t))))

            # Lens flare
            flare_cx = int(-0.2 * FW + t * 1.4 * FW)
            flare = scene.lens_flare(FW, int(FH * 0.35), flare_cx, intensity=0.9)
            canvas.alpha_composite(flare, (0, title_y + th // 2 - flare.height // 2))

            # Post-processing
            rgb = canvas.convert('RGB').resize((640, 360), Image.LANCZOS)
            rgb = scene.add_bloom(rgb, threshold=165, blur=10, strength=0.42)
            rgb = scene.chromatic_aberration(rgb, shift_px=1)
            final = scene.apply_scanlines_vignette(rgb)
            frames.append(final.convert('RGB'))

        fps_out = FPS_S
    else:
        # Pixel art scenes (isometric voxel)
        if scene_name == "lluvia":
            from utils import scene_rainy as scene_mod
        elif scene_name == "dream":
            from utils import scene_dreamland as scene_mod
        else:
            raise ValueError(f"Unknown scene: {scene_name}")

        n_frames = scene_mod.N_FRAMES
        for i in range(n_frames):
            frames.append(scene_mod.render_frame(i, title_text, sub_text, user_img))
        fps_out = scene_mod.FPS

    # Encode GIF
    buf = io.BytesIO()
    frames[0].save(buf, format='GIF', save_all=True, append_images=frames[1:],
                   duration=int(1000 / fps_out), loop=0, optimize=True)
    return buf.getvalue()


class SynthTextCog(commands.Cog, name="SynthText"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="texto", description="Genera un GIF animado con texto en una escena temática")
    @app_commands.describe(
        escena="Escena visual",
        principal="Texto principal (grande)",
        subtexto="Texto secundario (opcional)",
        imagen="Imagen para incluir en la escena (opcional)",
    )
    @app_commands.choices(escena=SCENE_CHOICES)
    async def texto_command(
        self,
        interaction: discord.Interaction,
        escena: str,
        principal: str,
        subtexto: str = "",
        imagen: discord.Attachment | None = None,
    ):
        if len(principal) > 30:
            await interaction.response.send_message("Máximo 30 caracteres.", ephemeral=True)
            return
        if len(subtexto) > 40:
            await interaction.response.send_message("Máximo 40 caracteres para subtexto.", ephemeral=True)
            return

        from utils.security import can_use_youkai_nl
        is_staff = await can_use_youkai_nl(interaction.user, self.bot.db) if self.bot.db else False
        if not is_staff:
            from utils.credit_economy import can_spend
            ok, reason, _ = await can_spend(self.bot.db, interaction.user.id, interaction.guild.id, 600)
            if not ok:
                await interaction.response.send_message(f"⛔ {reason} (cuesta 600 créditos)", ephemeral=True)
                return
            await self.bot.db.spend_credits(interaction.user.id, interaction.guild.id, 600, reason="synth")

        await interaction.response.defer()

        img_bytes = None
        if imagen:
            try:
                img_bytes = await imagen.read()
            except Exception:
                pass

        try:
            loop = asyncio.get_running_loop()
            gif_bytes = await loop.run_in_executor(
                _pool, _generate_gif, escena, principal, subtexto, img_bytes
            )
            file = discord.File(io.BytesIO(gif_bytes), filename=f"{escena}.gif")
            await interaction.followup.send(file=file)
        except Exception as exc:
            logger.exception("SynthText: error generando GIF")
            await interaction.followup.send(f"Error: {exc}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SynthTextCog(bot))
