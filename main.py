import os
import dominions
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

bot = commands.Bot(command_prefix='!')

activeGames = []

@bot.command(name='add', help='Adds a new game to the active list.')
async def bot_add(ctx):
    await ctx.send('Add command')

@bot.command(name="test", help="Test command.")
async def bot_test(ctx, game):
    game_status = dominions.get_game_status(game)
    await ctx.send(game_status)

bot.run(TOKEN)