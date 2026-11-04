
import os
import re
import asyncio
import base64
import urllib.parse
import urllib.request
import json

import discord
from discord.ext import commands
from dotenv import load_dotenv
import yt_dlp

from collections import deque

# ==============================
# MUSICCC CONFIGURATION
# ==============================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

PREFIX = "."

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents,
    help_command=None
)

# ==============================
# MUSIC SETTINGS
# ==============================

queues = {}
current_tracks = {}
loop_enabled = {}
volumes = {}

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "default_search": "ytsearch1",
    "source_address": "0.0.0.0",
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


# ==============================
# SPOTIFY INTEGRATION
# ==============================

def get_spotify_track(url):
    match = re.search(
        r"open\.spotify\.com/track/([a-zA-Z0-9]+)",
        url
    )

    if not match:
        raise ValueError("Please provide a valid Spotify track link.")

    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise ValueError("Spotify API credentials are missing.")

    track_id = match.group(1)

    credentials = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()

    token_request = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=urllib.parse.urlencode({
            "grant_type": "client_credentials"
        }).encode(),
        headers={
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )

    with urllib.request.urlopen(token_request, timeout=15) as response:
        token_data = json.loads(response.read())

    access_token = token_data["access_token"]

    track_request = urllib.request.Request(
        f"https://api.spotify.com/v1/tracks/{track_id}",
        headers={
            "Authorization": f"Bearer {access_token}"
        }
    )

    with urllib.request.urlopen(track_request, timeout=15) as response:
        track = json.loads(response.read())

    title = track["name"]
    artists = ", ".join(
        artist["name"] for artist in track["artists"]
    )

    return f"{title} {artists}"


# ==============================
# YOUTUBE AUDIO EXTRACTION
# ==============================

def extract_audio(query):
    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(query, download=False)

        if "entries" in info:
            info = next(
                (entry for entry in info["entries"] if entry),
                None
            )

        if not info:
            raise ValueError("No music found.")

        return {
            "title": info.get("title", "Unknown Track"),
            "url": info["url"],
            "webpage_url": info.get("webpage_url", ""),
            "duration": info.get("duration"),
        }


async def resolve_track(query):
    loop = asyncio.get_running_loop()

    return await loop.run_in_executor(
        None,
        extract_audio,
        query
    )


# ==============================
# MUSIC PLAYER
# ==============================

async def play_next(guild):

    guild_id = guild.id
    voice = guild.voice_client

    if not voice or not voice.is_connected():
        return

    if voice.is_playing() or voice.is_paused():
        return

    queue = queues.setdefault(guild_id, deque())

    if not queue:
        current_tracks.pop(guild_id, None)
        return

    request = queue.popleft()

    try:
        track = await resolve_track(request["query"])

        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(
                track["url"],
                **FFMPEG_OPTIONS
            ),
            volume=volumes.get(guild_id, 0.5)
        )

        current_tracks[guild_id] = {
            **track,
            "requester": request["requester"],
            "query": request["query"],
        }

        def after_playing(error):
            if error:
                print(f"Playback error: {error}")

            if loop_enabled.get(guild_id, False):
                queue.appendleft(request)

            asyncio.run_coroutine_threadsafe(
                play_next(guild),
                bot.loop
            )

        voice.play(source, after=after_playing)

        channel = bot.get_channel(
            request["channel_id"]
        )

        if channel:
            embed = discord.Embed(
                title="🎶 Now Playing",
                description=f"**[{track['title']}]({track['webpage_url']})**",
                color=discord.Color.blurple()
            )

            embed.add_field(
                name="Requested by",
                value=request["requester"],
                inline=True
            )

            embed.set_footer(text="musiccc • Made by RevertedTinz")

            await channel.send(embed=embed)

    except Exception as error:
        print(f"Music error: {error}")

        channel = bot.get_channel(request["channel_id"])

        if channel:
            await channel.send(
                f"❌ Couldn't play **{request['query']}**."
            )

        await play_next(guild)


# ==============================
# BOT EVENTS
# ==============================

@bot.event
async def on_ready():
    print("=" * 35)
    print(f"🎵 musiccc is online!")
    print(f"Bot: {bot.user}")
    print(f"Prefix: {PREFIX}")
    print("Made by RevertedTinz")
    print("=" * 35)


# ==============================
# GENERAL COMMANDS
# ==============================

@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)

    await ctx.send(
        f"🏓 Pong! `{latency}ms`"
    )


@bot.command(name="help")
async def help_command(ctx):

    embed = discord.Embed(
        title="🎵 musiccc | Help",
        description="Your music companion for Discord!",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="🎧 Music Commands",
        value=(
            "`.play <song/link>` — Play music\n"
            "`.pause` — Pause playback\n"
            "`.resume` — Resume playback\n"
            "`.skip` — Skip current track\n"
            "`.stop` — Stop playback\n"
            "`.queue` — View the queue\n"
            "`.nowplaying` — Current track\n"
            "`.loop` — Toggle loop\n"
            "`.volume <0-100>` — Change volume"
        ),
        inline=False
    )

    embed.add_field(
        name="🔊 Voice Commands",
        value=(
            "`.join` — Join your voice channel\n"
            "`.leave` — Leave your voice channel"
        ),
        inline=False
    )

    embed.add_field(
        name="⚙️ General Commands",
        value=(
            "`.ping` — Check bot latency\n"
            "`.help` — Show this menu"
        ),
        inline=False
    )

    embed.set_footer(
        text="musiccc • Made by RevertedTinz"
    )

    await ctx.send(embed=embed)


# ==============================
# VOICE COMMANDS
# ==============================

@bot.command()
async def join(ctx):

    if not ctx.author.voice:
        return await ctx.send(
            "❌ Join a voice channel first!"
        )

    channel = ctx.author.voice.channel

    if ctx.voice_client:
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()

    await ctx.send(
        f"🎧 Joined **{channel.name}**!"
    )


@bot.command()
async def leave(ctx):

    if not ctx.voice_client:
        return await ctx.send(
            "I'm not in a voice channel!"
        )

    queues[ctx.guild.id] = deque()
    current_tracks.pop(ctx.guild.id, None)
    loop_enabled[ctx.guild.id] = False

    await ctx.voice_client.disconnect()

    await ctx.send("👋 Left the voice channel!")


# ==============================
# PLAY COMMAND
# ==============================

@bot.command()
async def play(ctx, *, query: str):

    if not ctx.author.voice:
        return await ctx.send(
            "❌ Join a voice channel first!"
        )

    channel = ctx.author.voice.channel

    if ctx.voice_client:
        if ctx.voice_client.channel != channel:
            await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()

    await ctx.send("🔎 Finding your music...")

    try:
        if "open.spotify.com/track/" in query:
            search_query = await asyncio.to_thread(
                get_spotify_track,
                query
            )
        else:
            search_query = query

        guild_id = ctx.guild.id

        queue = queues.setdefault(
            guild_id,
            deque()
        )

        queue.append({
            "query": search_query,
            "requester": str(ctx.author),
            "channel_id": ctx.channel.id
        })

        embed = discord.Embed(
            title="🎵 Added to Queue",
            description=f"**{search_query}**",
            color=discord.Color.green()
        )

        embed.set_footer(
            text="musiccc • Made by RevertedTinz"
        )

        await ctx.send(embed=embed)

        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            await play_next(ctx.guild)

    except Exception as error:
        await ctx.send(
            f"❌ Error: {error}"
        )


# ==============================
# PAUSE / RESUME
# ==============================

@bot.command()
async def pause(ctx):

    voice = ctx.voice_client

    if voice and voice.is_playing():
        voice.pause()
        await ctx.send("⏸️ Playback paused!")
    else:
        await ctx.send("Nothing is playing!")


@bot.command()
async def resume(ctx):

    voice = ctx.voice_client

    if voice and voice.is_paused():
        voice.resume()
        await ctx.send("▶️ Playback resumed!")
    else:
        await ctx.send("Nothing is paused!")


# ==============================
# SKIP / STOP
# ==============================

@bot.command()
async def skip(ctx):

    voice = ctx.voice_client

    if voice and voice.is_playing():
        voice.stop()
        await ctx.send("⏭️ Skipped!")
    else:
        await ctx.send("Nothing is playing!")


@bot.command()
async def stop(ctx):

    voice = ctx.voice_client

    if not voice:
        return await ctx.send("I'm not playing anything!")

    queues[ctx.guild.id] = deque()
    loop_enabled[ctx.guild.id] = False

    if voice.is_playing() or voice.is_paused():
        voice.stop()

    current_tracks.pop(ctx.guild.id, None)

    await ctx.send("⏹️ Playback stopped and queue cleared!")


# ==============================
# QUEUE COMMAND
# ==============================

@bot.command(name="queue", aliases=["q"])
async def show_queue(ctx):

    guild_id = ctx.guild.id
    queue = queues.get(guild_id, deque())

    embed = discord.Embed(
        title="📃 Music Queue",
        color=discord.Color.blurple()
    )

    current = current_tracks.get(guild_id)

    if current:
        embed.add_field(
            name="🎶 Now Playing",
            value=current["title"],
            inline=False
        )

    if queue:
        upcoming = []

        for index, item in enumerate(list(queue)[:10], 1):
            upcoming.append(
                f"`{index}.` {item['query']}"
            )

        embed.add_field(
            name="⏭️ Up Next",
            value="\n".join(upcoming),
            inline=False
        )
    else:
        embed.add_field(
            name="Queue",
            value="The queue is empty!",
            inline=False
        )

    embed.set_footer(
        text=f"musiccc • {len(queue)} tracks queued • Made by RevertedTinz"
    )

    await ctx.send(embed=embed)


# ==============================
# NOW PLAYING
# ==============================

@bot.command(name="nowplaying", aliases=["np"])
async def nowplaying(ctx):

    track = current_tracks.get(ctx.guild.id)

    if not track:
        return await ctx.send(
            "Nothing is playing right now!"
        )

    embed = discord.Embed(
        title="🎶 Now Playing",
        description=f"**{track['title']}**",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="Requested by",
        value=track["requester"]
    )

    embed.set_footer(
        text="musiccc • Made by RevertedTinz"
    )

    await ctx.send(embed=embed)


# ==============================
# LOOP COMMAND
# ==============================

@bot.command()
async def loop(ctx):

    guild_id = ctx.guild.id

    loop_enabled[guild_id] = not loop_enabled.get(
        guild_id,
        False
    )

    status = (
        "enabled 🔁"
        if loop_enabled[guild_id]
        else "disabled"
    )

    await ctx.send(
        f"Loop is now **{status}**!"
    )


# ==============================
# VOLUME COMMAND
# ==============================

@bot.command()
async def volume(ctx, amount: int):

    if amount < 0 or amount > 100:
        return await ctx.send(
            "Volume must be between 0 and 100!"
        )

    guild_id = ctx.guild.id
    volumes[guild_id] = amount / 100

    voice = ctx.voice_client

    if voice and isinstance(
        voice.source,
        discord.PCMVolumeTransformer
    ):
        voice.source.volume = amount / 100

    await ctx.send(
        f"🔊 Volume set to **{amount}%**!"
    )


# ==============================
# ERROR HANDLING
# ==============================

@bot.event
async def on_command_error(ctx, error):

    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MissingRequiredArgument):
        return await ctx.send(
            f"❌ Missing argument! Use `{PREFIX}help`."
        )

    if isinstance(error, commands.BadArgument):
        return await ctx.send(
            "❌ Invalid argument!"
        )

    print(f"Command error: {error}")

    await ctx.send(
        "❌ Something went wrong while running that command."
    )


# ==============================
# START MUSICCC
# ==============================

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing from your .env file!"
    )

bot.run(TOKEN)
