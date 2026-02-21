from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
import asyncio
import os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Lee la API Key desde variables de entorno (más seguro)
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
        if not token: break
        await asyncio.sleep(2)
    return results

@app.get("/search")
async def search(zip_code: str = Query(...), business_type: str = Query("both")):
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
                        "maps_link": f"https://www.google.com/maps/place/?q=place_id:{pid}"
                    })

    return {
        "zip_code": zip_code,
        "location": address,
        "total": len(all_biz),
        "used_cars": sum(1 for b in all_biz if b["category"] == "Used Cars"),
        "used_machinery": sum(1 for b in all_biz if b["category"] == "Used Machinery"),
        "businesses": all_biz
    }

@app.get("/")
async def root():
    return {"status": "running"}
```

**2.6** → Haz scroll hacia abajo → clic en **"Commit new file"** (botón verde)

**2.7** → Repite el proceso para crear otro archivo llamado `requirements.txt` con este contenido:
```
fastapi==0.104.1
uvicorn==0.24.0
httpx==0.25.1
```

**2.8** → Crea un tercer archivo llamado `Procfile` (sin extensión) con este contenido:
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

## 🚀 PASO 3: Subir el servidor a Railway (15 minutos)

Railway es como un "computador en la nube" donde tu código va a vivir y funcionar 24/7 gratis.

**3.1** → Ve a `railway.app` → **"Start a New Project"**

**3.2** → Selecciona **"Deploy from GitHub repo"**

**3.3** → Conecta tu cuenta de GitHub si no lo has hecho → Selecciona el repositorio `business-extractor`

**3.4** → Railway va a empezar a instalar todo automáticamente. Espera 2-3 minutos.

**3.5** → Cuando termine, ve a la pestaña **"Variables"** → clic en **"+ New Variable"** y agrega:
- Nombre: `GOOGLE_API_KEY`
- Valor: `AIzaSyB3x7k9mN2...` (tu key del Paso 1)

**3.6** → Ve a la pestaña **"Settings"** → busca **"Networking"** → clic en **"Generate Domain"**

**3.7** → Te va a dar una URL que se ve así:
`https://business-extractor-production.railway.app`

**⚠️ Guarda esta URL. La necesitas en el siguiente paso.**

**3.8** → Prueba que funciona: abre una pestaña nueva y ve a:
`https://TU-URL.railway.app/search?zip_code=77001`

Si ves un JSON con negocios, ¡todo funciona! ✅

---

## 🤖 PASO 4: Crear el Custom GPT en ChatGPT (15 minutos)

Esta es la parte donde creas el "agente" dentro de ChatGPT.

**4.1** → Ve a `chat.openai.com` → En el menú izquierdo busca **"Explore GPTs"** → **"+ Create"**

**4.2** → Verás dos pestañas: **"Create"** y **"Configure"**. Haz clic en **"Configure"**

**4.3** → Rellena los campos así:

- **Name:** `Business Finder USA`
- **Description:** `Encuentra negocios de carros usados y maquinaria usada por ZIP code en USA`

**4.4** → En el campo **"Instructions"** pega esto:
```
Eres un agente especializado en encontrar negocios de venta de 
CARROS USADOS y MAQUINARIA USADA en Estados Unidos.

Cuando el usuario te dé un ZIP code, llama AUTOMÁTICAMENTE 
a la función search con ese zip_code.

Presenta los resultados en este formato:

📍 ZIP: [código] — [Ciudad, Estado]
📊 Total: X negocios | 🚗 Carros: Y | 🏗️ Maquinaria: Z

🚗 CARROS USADOS:
[tabla con nombre, dirección, rating, reseñas, link]

🏗️ MAQUINARIA USADA:
[tabla con nombre, dirección, rating, reseñas, link]

Responde en español si el usuario escribe en español.
Acepta frases como "busca en 90210" o "ZIP 77001" o "negocios en Texas 75001".
