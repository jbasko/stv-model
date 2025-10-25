# main.py
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import List, Optional, Dict
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, constr


# --------- Models ----------
class CandidateIn(BaseModel):
    name: constr(strip_whitespace=True, min_length=1)
    color: Optional[str] = "#2f80ed"
    meta: Optional[str] = None


class Candidate(CandidateIn):
    id: str = Field(default_factory=lambda: uuid4().hex)


class BallotIn(BaseModel):
    rankings: List[constr(strip_whitespace=True, min_length=1)] = Field(..., description="Candidate IDs by preference")
    weight: int = Field(1, ge=1)


class Ballot(BallotIn):
    id: str = Field(default_factory=lambda: uuid4().hex)


class SimulationSettings(BaseModel):
    seats: int = Field(5, ge=5, le=10)


# --------- App ----------
app = FastAPI(title="STV Input API", version="0.1.0")

# CORS (useful if you open the HTML from a different origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------- In-memory stores ----------
SETTINGS = SimulationSettings(seats=5)
CANDIDATES: Dict[str, Candidate] = {
    "a": Candidate(id="a", name="A", color="#eb5757"),
    "b": Candidate(id="b", name="B", color="yellow"),
    "c": Candidate(id="c", name="C", color="#27ae60"),
    "d": Candidate(id="d", name="D", color="#2f80ed"),
    "e": Candidate(id="e", name="E", color="#9b51e0"),
    "f": Candidate(id="f", name="F", color="#f2994a"),
    "g": Candidate(id="g", name="G", color="#56ccf2"),
}

BALLOTS: Dict[str, Ballot] = {
    "a": Ballot(id="a", rankings=["a"], weight=7500),
    "ab": Ballot(id="ab", rankings=["a", "b"], weight=1500),
    "ag": Ballot(id="ag", rankings=["a", "g"], weight=500),
    "b": Ballot(id="b", rankings=["b"], weight=5800),
    "be": Ballot(id="be", rankings=["b", "e"], weight=5000),
    "c": Ballot(id="c", rankings=["c"], weight=9200),
    "d": Ballot(id="d", rankings=["d"], weight=2000),
    "dc": Ballot(id="dc", rankings=["d", "c"], weight=4000),
    "dcg": Ballot(id="dcg", rankings=["d", "c", "g"], weight=1000),
    "e": Ballot(id="e", rankings=["e"], weight=6800),
    "bf": Ballot(id="bf", rankings=["f"], weight=3000),
    "fa": Ballot(id="fa", rankings=["f", "a"], weight=3200),
    "fb": Ballot(id="fb", rankings=["f", "b"], weight=3000),
    "fc": Ballot(id="fc", rankings=["f", "c"], weight=800),
    "fd": Ballot(id="fd", rankings=["f", "d"], weight=200),
    "fe": Ballot(id="fe", rankings=["f", "e"], weight=1800),
    "ga": Ballot(id="ga", rankings=["g", "a"], weight=3000),
    "gabef": Ballot(id="gabef", rankings=["g", "a", "b", "e", "f"], weight=1700),
}

# --------- Static / index ----------
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
INDEX_HTML = STATIC_DIR / "index.html"

# Mount /static (serves index.html assets if you add any)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def root():
    if not INDEX_HTML.exists():
        # Minimal placeholder if you haven't copied your HTML yet
        return FileResponse(str(make_min_index()))
    return FileResponse(str(INDEX_HTML))


def make_min_index() -> Path:
    html = """<!doctype html>
<html lang="lv">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>STV ievade</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/css/tabler.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/css/tabler-flags.min.css">
</head>
<body class="p-3">
  <div class="container-xl">
    <h2>STV ievade</h2>
    <p class="text-secondary">Šis ir pagaidu fails. Nomaini ar savu pilno lapu: <code>static/index.html</code>.</p>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/js/tabler.min.js"></script>
</body>
</html>"""
    placeholder = STATIC_DIR / "index.html"
    placeholder.write_text(html, encoding="utf-8")
    return placeholder


# --------- Health ----------
@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


# --------- Settings ----------
@app.get("/settings", response_model=SimulationSettings, tags=["settings"])
def get_settings():
    return SETTINGS


@app.put("/settings", response_model=SimulationSettings, tags=["settings"])
def put_settings(s: SimulationSettings):
    global SETTINGS
    SETTINGS = s
    return SETTINGS


# --------- Candidates CRUD ----------
@app.get("/candidates", response_model=List[Candidate], tags=["candidates"])
def list_candidates():
    return list(CANDIDATES.values())


@app.post("/candidates", response_model=Candidate, status_code=201, tags=["candidates"])
def create_candidate(payload: CandidateIn):
    cand = Candidate(**payload.model_dump())
    CANDIDATES[cand.id] = cand
    return cand


@app.delete("/candidates/{candidate_id}", status_code=204, tags=["candidates"])
def delete_candidate(candidate_id: str):
    if candidate_id not in CANDIDATES:
        raise HTTPException(status_code=404, detail="Candidate not found")
    # also purge candidate from ballots' rankings (optional)
    del CANDIDATES[candidate_id]
    return


@app.delete("/candidates", status_code=204, tags=["candidates"])
def delete_all_candidates():
    CANDIDATES.clear()
    return


# --------- Ballots CRUD ----------
@app.get("/ballots", response_model=List[Ballot], tags=["ballots"])
def list_ballots():
    return list(BALLOTS.values())


@app.post("/ballots", response_model=Ballot, status_code=201, tags=["ballots"])
def create_ballot(payload: BallotIn):
    # optional light validation: ensure candidate IDs referenced exist
    unknown = [cid for cid in payload.rankings if cid not in CANDIDATES]
    if unknown:
        raise HTTPException(status_code=400, detail={"unknown_candidate_ids": unknown})
    ballot = Ballot(**payload.model_dump())
    BALLOTS[ballot.id] = ballot
    return ballot


@app.delete("/ballots/{ballot_id}", status_code=204, tags=["ballots"])
def delete_ballot(ballot_id: str):
    if ballot_id not in BALLOTS:
        raise HTTPException(status_code=404, detail="Ballot not found")
    del BALLOTS[ballot_id]
    return


@app.delete("/ballots", status_code=204, tags=["ballots"])
def delete_all_ballots():
    BALLOTS.clear()
    return


# --------- Placeholder for your server-side STV endpoint (wire your own model) ----------
# Example shape only; implement your STV logic behind it.
class SimRequest(BaseModel):
    seats: Optional[int] = Field(None, ge=1)
    include_rounds: bool = False


@app.post("/simulate", tags=["simulate"])
def simulate(req: SimRequest):
    # Replace this stub with a call into your STV engine.
    # You have access to CANDIDATES and BALLOTS in memory here.

    from stv_model import model as stv_model
    election = stv_model.Election(
        num_seats=req.seats or SETTINGS.seats,
    )

    for candidate in CANDIDATES.values():
        election.register_candidate(stv_model.Candidate(
            id=candidate.id,
        ))


    for i, ballot in enumerate(BALLOTS.values()):
        election.register_ballot(stv_model.Ballot(
            id=f"ballot_{i + 1}",
            prefs=tuple(ballot.rankings),
            strength=Decimal(ballot.weight),
        ))

    election.run_count()

    rounds = [{
        "index": 0,
        "events": [],
        "candidates": [  # Imitējam 0. kārtu, lai var attēlot sākuma stāvokli.
            {
                "id": cid,
                "name": CANDIDATES[cid].name,
                "votes": cand.tally_after_first,
                "transfers": cand.tally_after_first,
                "status": "running",
            } for cid, cand in election.candidates.items()
        ],
    }]
    for round_no in range(1, election.round_no + 1):
        rounds.append({
            "index": round_no,
            "events": election.event_logs[round_no - 1],
            "candidates": [
                {
                    "id": cid,
                    "name": CANDIDATES[cid].name,
                    "votes": int(cand.tallies[round_no - 1]),
                    "transfers": election.candidate_logs[round_no - 1][cid].transfer,
                    "status": election.candidate_logs[round_no - 1][cid].status,
                } for cid, cand in election.candidates.items()
            ]
        })

    return {
        "seats": req.seats or SETTINGS.seats,
        "candidates": list(CANDIDATES.values()),
        "ballots": list(BALLOTS.values()),
        "num_ballots": election.num_ballots,
        "quota": election.quota,
        "rounds": rounds,
    }

    # --------- Dev entrypoint ----------
    # Run: uvicorn main:app --reload
