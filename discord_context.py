import discord


def clean_message_content(message: discord.Message, bot_user: discord.ClientUser) -> str:
    content = message.content
    mention_patterns = (
        f"<@{bot_user.id}>",
        f"<@!{bot_user.id}>",
    )

    for pattern in mention_patterns:
        content = content.replace(pattern, "")

    return " ".join(content.split())


def format_discord_message(
    message: discord.Message,
    bot_user: discord.ClientUser,
) -> str:
    channel_name = getattr(message.channel, "name", "direct-message")
    guild_name = message.guild.name if message.guild else "direct-message"
    clean_content = clean_message_content(message, bot_user)

    return (
        "Discord message\n"
        f"guild: {guild_name} ({message.guild.id if message.guild else 'dm'})\n"
        f"channel: {channel_name} ({message.channel.id})\n"
        f"author: {message.author.display_name} ({message.author.id})\n"
        f"content: {clean_content or message.content}"
    )
