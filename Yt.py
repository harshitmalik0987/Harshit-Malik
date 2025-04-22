import os
import re
import logging
import tempfile
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from yt_dlp import YoutubeDL

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Telegram User Configuration (Replace with your actual credentials)
API_ID = 22815674  # Replace with your API ID
API_HASH = '3aa83fb0fe83164b9fee00a1d0b31e5f'  # Replace with your API Hash
PHONE_NUMBER = '+919350050226'  # Replace with your phone number

# Initialize Telegram Client with user session
client = TelegramClient('user_session', API_ID, API_HASH)  # Session file will be 'user_session.session'

# Store user data
user_links = {}  # {chat_id: youtube_url}

# YouTube URL pattern
YOUTUBE_RE = re.compile(r'(?i)https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[^\s]+')

# Define supported formats in order of preference
SUPPORTED_FORMATS = [
    {'label': '720p', 'height': 720},
    {'label': '1080p', 'height': 1080},
    {'label': '480p', 'height': 480},
    {'label': '360p', 'height': 360},
    {'label': '144p', 'height': 144}
]

async def get_supported_format(url):
    """Find the best available format, preferring 720p."""
    try:
        with YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            video_formats = [
                f for f in formats
                if f.get('ext') == 'mp4' and f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('height') in [fmt['height'] for fmt in SUPPORTED_FORMATS]
            ]
            if not video_formats:
                return None, info.get('title', 'Video')

            # Try formats in order of preference
            for fmt in SUPPORTED_FORMATS:
                matching_formats = [f for f in video_formats if f.get('height') == fmt['height']]
                if matching_formats:
                    selected_format = min(matching_formats, key=lambda x: x.get('filesize', float('inf')))
                    return {
                        'format_id': selected_format['format_id'],
                        'filesize': selected_format.get('filesize') or selected_format.get('filesize_approx'),
                        'label': fmt['label']
                    }, info.get('title', 'Video')
            return None, info.get('title', 'Video')
    except Exception as e:
        logger.exception(f"Error checking formats: {e}")
        return None, None

@client.on(events.NewMessage(pattern=YOUTUBE_RE, incoming=True))
async def handle_link(event):
    """Handle YouTube links and download in 720p or next best format."""
    chat_id = event.chat_id
    url = event.raw_text.strip()

    # Store the link
    user_links[chat_id] = url

    # Check for supported format
    format_details, video_title = await get_supported_format(url)
    if not format_details:
        await event.respond(
            f"❌ No supported video formats (720p, 1080p, 480p, 360p, 144p) found for '{video_title}' or invalid link."
        )
        return

    format_id = format_details['format_id']
    filesize = format_details.get('filesize')
    format_label = format_details['label']

    # Check file size (50MB = 50 * 1024 * 1024 bytes)
    if filesize and filesize > 50 * 1024 * 1024:
        await event.respond(
            f"❌ The {format_label} video for '{video_title}' is too large (>50MB). Please message me personally for assistance."
        )
        return

    # Start downloading
    await event.respond(f"⏳ Downloading '{video_title}' in {format_label}...", parse_mode="markdown")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                'format': format_id,
                'outtmpl': os.path.join(tmpdir, 'file.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'merge_output_format': 'mp4'
            }
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Find the downloaded file
            for fname in os.listdir(tmpdir):
                if fname.endswith('.mp4'):
                    filepath = os.path.join(tmpdir, fname)
                    actual_size = os.path.getsize(filepath)

                    # Verify file size after download
                    if actual_size > 50 * 1024 * 1024:
                        await event.respond(
                            f"❌ Downloaded file for '{video_title}' in {format_label} is too large (>50MB). Please message me personally."
                        )
                        return

                    # Send the file
                    await client.send_file(
                        chat_id,
                        filepath,
                        caption=f"✅ Downloaded '{video_title}' in {format_label}!",
                        progress_callback=lambda current, total: logger.debug(f"Uploading: {current}/{total} bytes")
                    )
                    await event.respond(f"✅ File sent in {format_label}!", parse_mode="markdown")
                    break
            else:
                await event.respond("❌ No supported file format found after download.")
    except Exception as e:
        logger.exception(f"Download error: {e}")
        await event.respond(f"❌ Failed to download '{video_title}' in {format_label}. Please try again or check the link.")
    finally:
        # Clean up user data
        user_links.pop(chat_id, None)

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    """Handle /start command."""
    await event.respond(
        "👋 Welcome to the YouTube Downloader!\n"
        "Send a YouTube link, and I'll automatically download it in 720p or the next best supported format (1080p, 480p, 360p, 144p).\n"
        "Note: Files larger than 50MB are not supported."
    )

async def main():
    """Main function to start the client."""
    await client.start(phone=PHONE_NUMBER)
    if not await client.is_user_authorized():
        await client.send_code_request(PHONE_NUMBER)
        code = input("Enter the verification code: ")
        await client.sign_in(PHONE_NUMBER, code)
    logger.info("User session started.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    client.loop.run_until_complete(main())