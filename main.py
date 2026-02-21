from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
import asyncio
import os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

QUERIES = {
    "used_cars": ["used car dealer", "used cars for sale", "pre-owned vehicles", "auto sales used"],
    "used_machinery": ["used equipment dealer", "heavy equipment used", "used machinery dealer", "construction equipment used"]
}

async def get_coords(zip_code):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    async with httpx.AsyncClient() as c:
        r = await c.get(url, params={"address": f"{zip_code} USA", "key": GOOGLE_API_KEY})
        d = r.json()
    if d["status"] == "OK":
        loc = d["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"], d["results"][0]["formatted_address"]
    return None, None, None

async def get_place_details(client, place_id):
    """Obtiene teléfono y website de un negocio específico"""
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "formatted_phone_number,website,international_phone_number",
        "key": GOOGLE_API_KEY
    }
    try:
        r = await client.get(url, params=params, timeout=15)
        d = r.json()
        if d.get("status") == "OK":
            result = d.get("result", {})
            return {
                "phone": result.get("formatted_phone_number", "N/A"),
                "phone_international": result.get("international_phone_number", "N/A"),
                "website": result.get("website", "N/A")
            }
    except Exception as e:
        print(f"Error getting details for {place_id}: {e}")
    return {"phone": "N/A", "phone_international": "N/A", "website": "N/A"}

async def search_places(query, lat, lng, page_token=None):
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": query, "location": f"{lat},{lng}", "radius": 50000, "key": GOOGLE_API_KEY}
    if page_token:
        params["pagetoken"] = page_token
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(url, params=params)
        return r.json()

async def get_all_for_query(query, lat, lng):
    results, token = [], None
    for _ in range(3):
        data = await search_places(query, lat, lng, token)
        results += data.get("results", [])
        token = data.get("next_page_token")
        if not token:
            break
        await asyncio.sleep(2)
    return results

@app.get("/search")
async def search(
    zip_code: str = Query(...),
    business_type: str = Query("both"),
    include_phone: bool = Query(False)  # ← NUEVO PARÁMETRO
):
    lat, lng, address = await get_coords(zip_code)
    if not lat:
        return {"error": "ZIP no válido", "businesses": []}

    seen, all_biz = set(), []

    for category, queries in QUERIES.items():
        if business_type != "both" and business_type != category:
            continue
        for q in queries:
            places = await get_all_for_query(q, lat, lng)
            for p in places:
                pid = p.get("place_id")
                if pid and pid not in seen:
                    seen.add(pid)
                    all_biz.append({
                        "category": "Used Cars" if category == "used_cars" else "Used Machinery",
                        "name": p.get("name", ""),
                        "address": p.get("formatted_address", ""),
                        "rating": p.get("rating", "N/A"),
                        "reviews": p.get("user_ratings_total", 0),
                        "status": p.get("business_status", ""),
                        "phone": "N/A",
                        "phone_international": "N/A",
                        "website": "N/A",
                        "maps_link": f"https://www.google.com/maps/place/?q=place_id:{pid}",
                        "place_id": pid
                    })

    # Si se pidieron teléfonos, hace las llamadas adicionales en paralelo
    if include_phone and all_biz:
        print(f">>> Obteniendo detalles para {len(all_biz)} negocios...")

        # Procesa en grupos de 10 para no saturar la API
        async with httpx.AsyncClient() as client:
            for i in range(0, len(all_biz), 10):
                batch = all_biz[i:i+10]
                tasks = [get_place_details(client, b["place_id"]) for b in batch]
                details_list = await asyncio.gather(*tasks)

                for business, details in zip(batch, details_list):
                    business["phone"] = details["phone"]
                    business["phone_international"] = details["phone_international"]
                    business["website"] = details["website"]

                # Pequeña pausa entre grupos para no saturar
                if i + 10 < len(all_biz):
                    await asyncio.sleep(0.5)

        print(f">>> Detalles completados")

    # Limpia el place_id del resultado final (no es necesario mostrarlo)
    for b in all_biz:
        b.pop("place_id", None)

    return {
        "zip_code": zip_code,
        "location": address,
        "total": len(all_biz),
        "used_cars": sum(1 for b in all_biz if b["category"] == "Used Cars"),
        "used_machinery": sum(1 for b in all_biz if b["category"] == "Used Machinery"),
        "phones_included": include_phone,
        "businesses": all_biz
    }

@app.get("/")
async def root():
    return {
        "status": "running",
        "api_key_loaded": bool(GOOGLE_API_KEY)
    }

