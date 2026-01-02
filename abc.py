import asyncio
import httpx
import requests

# Config
NATIONS_API = "https://api.earthpol.com/astra/nations"
MAX_CONCURRENT = 50

# Fetch all nations
def fetch_nations():
    resp = requests.get(NATIONS_API)
    resp.raise_for_status()
    return resp.json()

# Async HEAD request to check if flag exists
async def head_request(client, name):
    name_url = "_".join(name.split())
    url = f"https://cdn.earthpol.com/nations/{name_url}.png"
    try:
        resp = await client.head(url, timeout=5)
        return resp.status_code == 200
    except httpx.RequestError:
        return False

# Check flags concurrently
async def check_flags(nations):
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=MAX_CONCURRENT)) as client:
        tasks = []
        for n in nations:
            async def task(n=n):
                async with sem:
                    has_flag = await head_request(client, n["name"])
                    return n, has_flag
            tasks.append(task())
        return await asyncio.gather(*tasks)

# Main debug function
def main():
    nations = fetch_nations()

    # Optionally filter some nations to reduce output
    query = input("Filter query (or press Enter to skip): ").strip().lower()
    if query:
        nations = [n for n in nations if query in n['name'].lower().replace("_", " ")]

    # Only take first 50 for quick testing
    nations = nations[:50]

    paired = asyncio.run(check_flags(nations))

    print("\nFlag status for each nation:")
    for n, has_flag in paired:
        print(f"{n['name']:30} -> Flag: {has_flag}")

    # Sort nations with flags first
    sorted_nations = [n for n, has_flag in sorted(paired, key=lambda x: x[1], reverse=True)]

    print("\nOrder after sorting (flags first):")
    for n in sorted_nations:
        display_name = " ".join(n["name"].split("_"))
        print(display_name)

if __name__ == "__main__":
    main()
