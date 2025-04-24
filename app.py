from fastapi import FastAPI, Request
from playwright.async_api import async_playwright


app = FastAPI()




# @app.get("/")
# async def root():
#     return {"message": "Hello World"}



# @app.on_event("startup")
# async def startup_event():
#     playwright = await async_playwright().start()
#     browser = await playwright.chromium.launch(headless=True)
#     app.state.playwright = playwright
#     app.state.browser = browser
#     print("Browser ishga tushdi", browser)



# @app.on_event("shutdown")
# async def shutdown_event():
#     await app.state.browser.close()
#     await app.state.playwright.stop()


# @app.get("/screen/")
# async def screen(request: Request):
#     browser = request.app.state.browser
#     context = await browser.new_context()
#     page = await context.new_page()

    
#     await page.goto("https://playwright.dev/")
#     await page.screenshot(path="screenshot.png")
#     return {"message": "Screenshot saved"}

















import re
from fastapi import FastAPI
from playwright.async_api import async_playwright, Page
import asyncio

app = FastAPI()
PAGE_POOL = asyncio.Queue()
MAX_PAGES = 10


@app.on_event("startup")
async def startup():
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False, args=["--no-sandbox"])
    context = await browser.new_context()
    app.state.browser = browser
    app.state.context = context

    # Sahifani yaratib, Instagramga bir marta kirib olamiz
    for _ in range(5):
        page = await context.new_page()
        await page.goto("https://www.instagram.com", wait_until="load")
        await PAGE_POOL.put(page)

    # Avtomatik yangilanish uchun sahifalar qo'shish
    async def add_page_loop():
        while True:
            await asyncio.sleep(2)
            if PAGE_POOL.qsize() < MAX_PAGES:
                page = await context.new_page()
                await page.goto("https://www.instagram.com", wait_until="load")
                await PAGE_POOL.put(page)

    asyncio.create_task(add_page_loop())


@app.on_event("shutdown")
async def shutdown():
    await app.state.browser.close()

import time

@app.get("/instagram")
async def scrape_instagram_post(url: str):
    page = await PAGE_POOL.get()
    try:
        curr_time = time.time()
        result = await get_instagram_image_and_album_and_reels(url, page)
        print(time.time() - curr_time)
        return result

    finally:
        if not page.is_closed():
            await PAGE_POOL.put(page)


async def get_instagram_image_and_album_and_reels(post_url, page: Page):
    print("📥 Media yuklanmoqda...")

    try:
        match = re.search(r'https://www.instagram.com/p/([^/?]+)', post_url)
        if not match:
            return {"error": True, "message": "Invalid URL format"}

        post_path = f"/p/{match.group(1)}/"
        full_url = f"https://www.instagram.com{post_path}"

        await page.evaluate(f"window.location.href = '{full_url}'")

        # Post yuklanishini kutamiz
        await page.mouse.click(10, 10)


        try:
            await page.wait_for_selector("article", timeout=20000)
        except Exception as e:
            print(f"❌ 'section' elementi topilmadi: {e}")
            return {"error": True, "message": "Invalid response from the server"}


        await page.mouse.click(10, 10)
        # await page.wait_for_timeout(1500)

        caption = None
        if (caption_el := await page.query_selector('article span._ap3a')):
            caption = await caption_el.inner_text()

        media_list = []

        while True:
            # 1. RASMLAR faqat article section ichidan olinadi
            images = await page.locator("article ._aagv img").all()
            for img in images:
                src = await img.get_attribute("src")
                if src and not any(m["download_url"] == src for m in media_list):
                    media_list.append({
                        "type": "image",
                        "download_url": src,
                        "thumb": src
                    })

            # 2. VIDEOLAR faqat article section ichidan olinadi
            videos = await page.locator("article video").all()
            for video in videos:
                src = await video.get_attribute("src")
                poster = await video.get_attribute("poster")
                if src and not any(m["download_url"] == src for m in media_list):
                    media_list.append({
                        "type": "video",
                        "download_url": src,
                        "thumb": poster or src  # fallback
                    })

            # 3. Keyingi media (album ichidagi)
            try:
                next_btn = page.locator("button[aria-label='Next']")
                await next_btn.wait_for(timeout=500)
                await next_btn.click()
                await page.wait_for_timeout(500)
            except Exception:
                break

        if not media_list:
            print({"error": True, "message": "Hech qanday media topilmadi"})
            return {"error": True, "message": "Invalid response from the server"}


        # Shortcode ni URL dan olamiz
        match = re.search(r'/p/([^/]+)/', post_url)
        shortcode = match.group(1) if match else "unknown"

        return {
            "error": False,
            "shortcode": shortcode,
            "hosting": "instagram",
            "type": "album" if len(media_list) > 1 else media_list[0]["type"],
            "url": post_url,
            "title": caption,
            "medias": media_list
        }

    except Exception as e:
        print(f"❗ Xatolik: {e}")
        return {"error": True, "message": "Server error"}

    finally:
        # await PAGE_POOL.put(page)
        await page.close()
