import os
import io
from PIL import Image
import aiohttp
from pokemontcgsdk import Card

DATA_DIR = os.environ.get("CARD_IMAGES_DIR", "data/images")

def _image_path(card_id):
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, f"{card_id}.webp")


def _tco_url(card_id):
    """Build a direct image URL from the card ID using the Pokemon TCG API pattern."""
    # IDs are like base1-1, swsh1-1, sm1-1, etc.
    parts = card_id.split("-")
    if len(parts) >= 2:
        set_code = "-".join(parts[:-1])
        number = parts[-1]
        return f"https://images.pokemontcg.io/{set_code}/{number}_hires.png"
    return None


async def get_card_image_path(card_id):
    """Return the local path to a card's image, fetching it if needed."""
    path = _image_path(card_id)
    if os.path.exists(path):
        return path

    # Try fetching from the API
    url = _tco_url(card_id)
    if url is None:
        return None

    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    img = Image.open(io.BytesIO(data))
                    # Convert to RGBA for webp transparency support, then save
                    if img.mode != "RGBA":
                        img = img.convert("RGBA")
                    img.save(path, "webp", quality=85)
                    return path
    except Exception:
        pass

    # Fallback: try the SDK
    try:
        card = Card.find(card_id)
        if hasattr(card, "images") and card.images:
            large_url = card.images.large or card.images.small
            if large_url:
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(large_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            img = Image.open(io.BytesIO(data))
                            if img.mode != "RGBA":
                                img = img.convert("RGBA")
                            img.save(path, "webp", quality=85)
                            return path
    except Exception:
        pass

    return None
