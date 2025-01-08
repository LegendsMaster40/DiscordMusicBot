import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import os
from discord import FFmpegPCMAudio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve the bot token from the environment variable
TOKEN = os.getenv('DISCORD_TOKEN')

# Setting up bot and prefix
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)  # Disable default help command

# Global Variables
queue = []
vc = None  # Voice client instance
ytdl_opts = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioquality': 1,
    'outtmpl': 'downloads/%(id)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'quiet': True,
}

ffmpeg_opts = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

# Search for song and return URL
async def search_song(query):
    with youtube_dl.YoutubeDL(ytdl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
        return {
            'url': info['url'],
            'title': info['title'],
            'id': info['id']
        }

# Play function
async def play(interaction):
    global vc
    if vc is None or not vc.is_connected():
        await join_voice_channel(interaction)

    if len(queue) > 0:
        song = queue.pop(0)
        vc.play(FFmpegPCMAudio(song['url'], **ffmpeg_opts), after=lambda e: asyncio.run_coroutine_threadsafe(play(interaction), bot.loop))

        embed = discord.Embed(
            title="Now Playing",
            description=f"[{song['title']}]({song['url']})",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=f"https://img.youtube.com/vi/{song['id']}/hqdefault.jpg")

        view = MusicControls(vc, interaction)
        await interaction.followup.send(embed=embed, view=view)
    else:
        await interaction.followup.send("No songs in the queue.\n\nUse `/help` to view all commands.")

# Join voice channel
async def join_voice_channel(interaction):
    global vc
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        vc = await channel.connect()
    else:
        await interaction.response.send_message("You need to join a voice channel first.", ephemeral=True)

# Button View
class MusicControls(discord.ui.View):
    def __init__(self, vc, interaction):
        super().__init__(timeout=None)
        self.vc = vc
        self.interaction = interaction

    @discord.ui.button(label="", emoji="⏸️", style=discord.ButtonStyle.grey)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.vc.is_playing():
            self.vc.pause()
            await interaction.response.send_message("Music paused.", ephemeral=True)
        else:
            await interaction.response.send_message("No music is playing.", ephemeral=True)

    @discord.ui.button(label="", emoji="▶️", style=discord.ButtonStyle.grey)
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.vc.is_paused():
            self.vc.resume()
            await interaction.response.send_message("Music resumed.", ephemeral=True)
        else:
            await interaction.response.send_message("Music is not paused.", ephemeral=True)

    @discord.ui.button(label="", emoji="⏭️", style=discord.ButtonStyle.grey)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.vc.is_playing():
            self.vc.stop()
            await interaction.response.send_message("Skipped to the next song.", ephemeral=True)
            await play(self.interaction)
        else:
            await interaction.response.send_message("No music is playing.", ephemeral=True)

    @discord.ui.button(label="", emoji="⏹️", style=discord.ButtonStyle.grey)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.vc:
            await self.vc.disconnect()
            await interaction.response.send_message("Stopped and disconnected.", ephemeral=True)
        else:
            await interaction.response.send_message("Bot is not connected.", ephemeral=True)

# Slash commands
@bot.tree.command(name="play", description="Play a song.")
async def play_command(interaction: discord.Interaction, search: str):
    await interaction.response.defer()  # Defer response as this might take time
    song = await search_song(search)
    queue.append(song)
    if vc is None or not vc.is_connected():
        await play(interaction)
    else:
        embed = discord.Embed(
            title=f"Added to queue: {song['title']}",
            description=f"[Click here to watch on YouTube]({song['url']})",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=f"https://img.youtube.com/vi/{song['id']}/hqdefault.jpg")
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="pause", description="Pause the currently playing song.")
async def pause_command(interaction: discord.Interaction):
    if vc.is_playing():
        vc.pause()
        await interaction.response.send_message("Paused the music.")
    else:
        await interaction.response.send_message("No music is playing.", ephemeral=True)

@bot.tree.command(name="resume", description="Resume paused music.")
async def resume_command(interaction: discord.Interaction):
    if vc.is_paused():
        vc.resume()
        await interaction.response.send_message("Resumed the music.")
    else:
        await interaction.response.send_message("No music is paused.", ephemeral=True)

@bot.tree.command(name="skipf", description="Skip to the next song in the queue.")
async def skipforward_command(interaction: discord.Interaction):
    if vc.is_playing():
        vc.stop()
        await play(interaction)
    else:
        await interaction.response.send_message("No music is playing.", ephemeral=True)

@bot.tree.command(name="stop", description="Stop and disconnect the bot.")
async def stop_command(interaction: discord.Interaction):
    global vc
    if vc:
        await vc.disconnect()
        await interaction.response.send_message("Disconnected from the voice channel.")
        vc = None
    else:
        await interaction.response.send_message("I am not in a voice channel.", ephemeral=True)

@bot.tree.command(name="join", description="Join the voice channel of the user.")
async def join_command(interaction: discord.Interaction):
    await join_voice_channel(interaction)

@bot.tree.command(name="queue", description="Show the current song queue.")
async def queue_command(interaction: discord.Interaction):
    if queue:
        queue_list = "\n".join([song['title'] for song in queue])
        await interaction.response.send_message(f"Queue:\n{queue_list}")
    else:
        await interaction.response.send_message("Queue is empty.")

@bot.tree.command(name="help", description="Show help information.")
async def help_command(interaction: discord.Interaction):
    help_message = """
    **Bot Commands:**

    `/play <song name>` - Play a song.
    `/pause` - Pause the currently playing song.
    `/resume` - Resume paused music.
    `/skipf` - Skip forward to the next song.
    `/stop` - Stop and disconnect from the voice channel.
    `/join` - Join the voice channel.
    `/queue` - Display the current queue of songs.
    `/help` - Show this help message.
    """
    await interaction.response.send_message(help_message)

@bot.event
async def on_ready():
    await bot.tree.sync()  # Sync the slash commands with Discord
    print(f'Logged in as {bot.user}')

# Run the bot
bot.run(TOKEN)
