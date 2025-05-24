from telethon import TelegramClient, events
import asyncio
import os

# 1. Fill these in from https://my.telegram.org
API_ID = 22815674
API_HASH = '3aa83fb0fe83164b9fee00a1d0b31e5f'
SESSION_NAME = 'dup_del_bot'  # this will create dup_del_bot.session

# 2. The channel you want to monitor (by username or ID)
CHANNEL = 'Govt_JobNotification'

# 3. (Optional) If you want persistence across restarts, set PERSIST_DB = True and install sqlite3
PERSIST_DB = False

if PERSIST_DB:
    import sqlite3
    conn = sqlite3.connect('seen_msgs.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS seen(text_hash TEXT PRIMARY KEY)')
    conn.commit()

seen_texts = set()

async def add_seen(text_hash):
    if PERSIST_DB:
        try:
            c.execute('INSERT INTO seen VALUES (?)', (text_hash,))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
    else:
        seen_texts.add(text_hash)

async def is_seen(text_hash):
    if PERSIST_DB:
        c.execute('SELECT 1 FROM seen WHERE text_hash=?', (text_hash,))
        return c.fetchone() is not None
    else:
        return text_hash in seen_texts

async def main():
    # Create the client and connect
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()

    @client.on(events.NewMessage(chats=CHANNEL))
    async def handler(event):
        msg = event.message
        # Only consider text messages
        if not msg.message:
            return

        text = msg.message.strip()
        # Use a simple hash (you can use hashlib.sha256 for more robustness)
        text_hash = str(hash(text))

        if await is_seen(text_hash):
            # Duplicate detected: delete it
            try:
                await msg.delete()
                print(f"Deleted duplicate message: {text[:50]}...")
            except Exception as e:
                print(f"Failed to delete message: {e}")
        else:
            # First time we see it: keep and record
            await add_seen(text_hash)
            print(f"Recorded message: {text[:50]}...")

    print("Bot is up and running, monitoring channel for duplicates...")
    await client.run_until_disconnected()

if name == 'main':
    asyncio.run(main())
