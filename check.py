

import asyncio
import aiohttp

API_URL = "http://37.27.210.13:8080/instagram"
test_url = "https://www.instagram.com/p/DInsfoXtAhU/?utm_source=ig_web_copy_link"

async def fetch(session, idx):
    try:
        async with session.get(API_URL, params={"url": test_url}, timeout=30) as response:
            status = response.status
            try:
                data = await response.json()
            except Exception:
                data = await response.text()
            return f"Request {idx}", status, data
    except Exception as e:
        return f"Request {idx}", "Error", str(e)

async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, i+1) for i in range(1)]
        
        for coro in asyncio.as_completed(tasks):
            req, status, data = await coro
            print(f"\n🔹 {req} -> Status: {status}")
            print(f"📦 Response: {data}")

# if __name__ == "__main__":
#     asyncio.run(main())


