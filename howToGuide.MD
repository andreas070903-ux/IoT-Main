# IoT Dashboard

Et dashboard til visning af sensordata. Projektet består af en FastAPI-backend, et Streamlit-dashboard og en MongoDB Atlas-database. Backend og dashboard kører i Docker.

## Forudsætninger

- [Git](https://git-scm.com/)
- [Python 3.12](https://www.python.org/downloads/) (64-bit)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Adgang til en MongoDB Atlas-database (connection string, brugernavn og adgangskode)

## Kom i gang

### 1. Clone Git-repoet

```powershell
git clone <repo-url>
cd <repo-mappe>
```

### 2. Opret og aktivér virtuelt miljø (venv)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Hvis PowerShell blokerer aktiveringen med en fejl om *execution policy*, så kør dette i samme vindue og aktivér igen:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Når miljøet er aktivt, står `(.venv)` forrest i terminalen.

### 3. Opret `.env`

Kopiér `.env.example` til `.env` og udfyld dine egne oplysninger:

```powershell
copy .env.example .env
```

```dotenv
MONGODB_URI=mongodb+srv://<brugernavn>:<adgangskode>@<cluster>.mongodb.net/
MONGODB_DATABASE=iot
MONGODB_COLLECTION=sensor_data
API_URL=http://127.0.0.1:8000/measurements
```

> `.env` indeholder adgangskoder og må **aldrig** committes til Git.

Husk også, at din IP-adresse skal være tilladt i Atlas under **Security → Network Access**.

### 4. Start Docker Desktop

Åbn Docker Desktop, og vent til den viser, at Docker kører.

### 5. Byg og start containerne

Fra projektets rodmappe:

```powershell
docker compose up -d --build
```

Se eventuelt loggen for at tjekke, at alt kører:

```powershell
docker compose logs -f
```

### 6. Åbn dashboardet

Åbn en browser og gå til:

**http://localhost:8501**

## Valgfrit: Generér testdata

Hvis databasen er tom, kan du generere data med sensorsimulatoren. Kør fra projektets rodmappe med venv aktiveret:

```powershell
python -m sensor_simulator.app --repeat
```

Simulatoren kører, indtil du stopper den med `Ctrl+C`. Genindlæs dashboardet for at se de nye data.

## Nyttige kommandoer

| Handling | Kommando |
|---|---|
| Stop containerne | `docker compose down` |
| Genstart efter ændring af `.env` | `docker compose up -d --force-recreate` |
| Genbyg efter kodeændringer | `docker compose up -d --build` |
| Se log fra API'en | `docker compose logs api` |

## Fejlfinding

- **`ModuleNotFoundError`**: Kør kommandoerne fra projektets rodmappe, og sørg for at venv er aktiveret.
- **HTTP 503 fra API'en**: Tjek `MONGODB_URI` i `.env`, at brugernavn og adgangskode er korrekte, og at din IP er tilladt i Atlas.
- **Tomt dashboard**: Der er ingen data i `iot.sensor_data`. Kør simulatoren som beskrevet ovenfor.