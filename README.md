# MongoDB Atlas sensorprojekt

Projektet indeholder en REST API, der modtager IoT-målinger og gemmer dem i MongoDB Atlas, samt en simulator, der genererer nye sensormålinger og sender dem til API'en.

## Projektstruktur

- `api/`: REST API, målingsvalidering og MongoDB-adgang.
- `sensor_simulator/`: genererer målinger og sender dem til API'en.
- `dashboard/`: Streamlit-dashboard med grafer, filtre og simuleret turbinestyring.
- `turbine_control/`: tilstand og kommandoer for de simulerede turbiner.
- `tools/`: MongoDB-hjælpeværktøjer, herunder eksportscript og playground.
- `tests/`: automatiske tests.
- `Dockerfile`, `docker-compose.yml`, `requirements.txt` og `.env.example`: kørsel og konfiguration.

## Krav og installation

- Python 3
- En MongoDB Atlas connection string med adgang til databasen

Installer afhængighederne fra PowerShell i projektmappen:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Kør også scripts med projektets Python-miljø, så afhængighederne findes:

```powershell
.\.venv\Scripts\python.exe -m sensor_simulator.app --help
```

## MongoDB-forbindelse

API'en og MongoDB-eksportscriptet læser connection stringen fra en lokal `.env`-fil automatisk. API'en bruger også database- og collection-navnene. Opret filen ud fra skabelonen:

```powershell
Copy-Item .\.env.example .\.env
notepad .\.env
```

Erstat URI'en i `.env` med din egen connection string. Gem filen; derefter behøver du ikke indtaste den igen i terminalen. `.env` er føjet til `.gitignore` og bør ikke deles eller committes. Hvis adgangskoden indeholder specialtegn, skal de URL-kodes i connection stringen.

## Sensor-simulering

`sensor_simulator/app.py` genererer løbende realistiske målinger og sender dem som HTTP POST til API'ens `/measurements`-endpoint. Den roterer mellem `WT-001`, `WT-002` og `WT-003`. API'en validerer og gemmer hver måling i MongoDB. Tidsstemplet sættes til det aktuelle UTC-tidspunkt. Med standardintervallet på 5 sekunder får hver turbine en ny måling hvert 15. sekund.

Start først API'en i en terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Start derefter simulatoren i en anden terminal. Den sender én ny måling hvert 5. sekund og skifter turbine for hver måling:

```powershell
.\.venv\Scripts\python.exe -m sensor_simulator.app --repeat
```

Send én måling for hver af de tre turbiner og stop:

```powershell
.\.venv\Scripts\python.exe -m sensor_simulator.app --interval 0 --limit 3
```

Brug `--interval 0.5` for at ændre intervallet eller `--limit 100` for at begrænse antallet af målinger. `--api-url` eller miljøvariablen `API_URL` kan bruges til at angive API-adressen. Stop gentagelse med `Ctrl+C`.

## REST API

API'en modtager målinger fra simulatoren eller en IoT-enhed og gemmer dem i MongoDB. Sæt
`MONGODB_DATABASE` og `MONGODB_COLLECTION` i `.env` sammen med `MONGODB_URI`,
og start API'en fra PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload
```

API'en kører som standard på `http://127.0.0.1:8000`. Interaktiv dokumentation
findes på `http://127.0.0.1:8000/docs`.

- `GET /health` kontrollerer forbindelsen til MongoDB.
- `POST /measurements` modtager en måling med de samme felter som `data.json`.
- `GET /measurements?limit=100` henter de nyeste målinger. `limit` kan være 1-1000.
- `GET /turbines/control` viser simulatorens status for alle turbiner.
- `POST /turbines/{turbine_id}/control` med `{"command":"stop"}` eller `{"command":"start"}` ændrer simulatorens status.

Turbinestyringen er kun en demo: API'en gemmer tilstanden i hukommelsen, og den
nulstilles, når API'en genstartes. Simulatoren springer stoppede turbiner over,
og API'en afviser målinger for en simuleret stoppet turbine. Dette styrer ikke
fysisk turbineudstyr.

API'en er uden autentifikation og bør kun eksponeres lokalt eller på et beskyttet
netværk, indtil adgangskontrol er konfigureret.

### Kør API'en med Docker

Installer Docker Desktop, og sørg for, at Docker Engine kører. Opret `.env` ud
fra `.env.example`, og indsæt dine egne MongoDB Atlas-oplysninger som beskrevet
ovenfor. Byg og start derefter API'en fra projektmappen:

```powershell
docker compose up --build -d
```

Kontrollér status og logs:

```powershell
docker compose ps
docker compose logs -f api
```

API'en er tilgængelig på `http://localhost:8000`, og dokumentationen findes på
`http://localhost:8000/docs`. Stop containeren med:

```powershell
docker compose down
```

For at andre på samme lokale netværk kan tilgå API'en, find computerens IPv4-
adresse med `ipconfig`, og del `http://<IPv4-adresse>:8000/docs`. Tillad
eventuelt indgående TCP-trafik på port 8000 i Windows Firewall for det private
netværk. MongoDB Atlas skal også tillade udgående forbindelse fra værtsmaskinens
offentlige IP-adresse.

Denne opsætning er til et betroet lokalt netværk, ikke til offentlig
internetadgang. API'en har ingen autentifikation; viderestil ikke port 8000 fra
routeren til internettet uden først at tilføje adgangskontrol og HTTPS.

## Eksport fra MongoDB

Eksportér en collection til en JSON-fil:

```powershell
.\.venv\Scripts\python.exe .\tools\mongo_export.py --database DATABASENAVN --collection COLLECTIONNAVN --output .\export.json
```

Eksportscriptet henter som standard højst 1.000 dokumenter. Brug `--limit 0` for at hente alle dokumenter.

## Dashboard

Dashboardet henter målinger gennem API'ens `GET /measurements`-endpoint; det
forbinder ikke direkte til MongoDB. Start API'en først, og start derefter
dashboardet fra en anden PowerShell-terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

```powershell
.\.venv\Scripts\python.exe -m streamlit run .\dashboard\app.py
```

Åbn adressen, som Streamlit viser i terminalen (normalt `http://localhost:8501`).
Dashboardet henter data fra `http://127.0.0.1:8000/measurements`. Sæt eventuelt
`API_URL` i `.env` til en anden målings-API-adresse. Dashboardet viser målinger,
grafer og filtre; brug **Opdater data** for at hente nye målinger gennem API'en.
I **Simuleret turbinestyring** kan du stoppe eller starte hver turbine. Når en
turbine stoppes, stopper simulatoren med at sende dens målinger; historiske
målinger bliver ikke slettet.

## Sikkerhed

- Brug en databasebruger med mindst mulige nødvendige rettigheder.
- Opbevar connection stringen privat; læg den ikke i kildekode eller versionsstyring.
- Hvis en connection string eller adgangskode er blevet delt, skal den roteres i MongoDB Atlas.
