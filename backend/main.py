import asyncio
import uuid
import time
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

from backend.verifier.url_verifier import verify_url
from backend.verifier.package_verifier import verify_package
from backend.verifier.tool_verifier import verify_tool
from backend import config

app = FastAPI(title="PhantomGuard Agent Trust Firewall Backend")

# Enable CORS for UI integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory database of logs and pending reviews
TRUST_TRACE_LOGS: List[Dict[str, Any]] = []
PENDING_REVIEWS: Dict[str, Dict[str, Any]] = {}

# Active WebSocket connections
active_connections: List[WebSocket] = []

class VerifyRequest(BaseModel):
    action_type: str  # "url_fetch", "package_install", "tool_execution"
    target: str
    context: str = ""

class DecideRequest(BaseModel):
    action_id: str
    approved: bool

# Helper to broadcast updates to connected WebSockets
async def broadcast_ws(message: Dict[str, Any]):
    disconnected = []
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception:
            disconnected.append(connection)
    for conn in disconnected:
        active_connections.remove(conn)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "PhantomGuard Backend",
        "fine_tuned_enabled": config.USE_FINE_TUNED,
        "model": config.FINE_TUNED_MODEL if config.USE_FINE_TUNED else config.BASE_MODEL
    }

@app.post("/verify")
async def verify_action(req: VerifyRequest):
    """
    Intercepts and evaluates agent actions. If flagged as a threat, 
    blocks execution and triggers human-in-the-loop validation.
    """
    action_id = str(uuid.uuid4())
    timestamp = time.strftime("%H:%M:%S")
    
    # 1. Run the appropriate verifier
    if req.action_type == "url_fetch":
        res = verify_url(req.target, req.context)
    elif req.action_type == "package_install":
        res = verify_package(req.target, req.context)
    elif req.action_type == "tool_execution":
        res = verify_tool(req.target, req.context)
    else:
        raise HTTPException(status_code=400, detail="Invalid action_type")

    is_hallucination = res["is_hallucination"]
    confidence = res["confidence"]
    category = res.get("category", "none")
    reason = res["reason"]

    # 2. Formulate base log entry
    log_entry = {
        "action_id": action_id,
        "timestamp": timestamp,
        "action_type": req.action_type,
        "target": req.target,
        "context": req.context,
        "is_hallucination": is_hallucination,
        "confidence": confidence,
        "category": category,
        "reason": reason,
        "allowed": not is_hallucination,
        "decision_source": "automatic"
    }

    # 3. Handle Human-in-the-Loop Blocking (if classified as threat/hallucination/usability)
    if is_hallucination:
        # Create synchronization event for this blocking check
        event = asyncio.Event()
        PENDING_REVIEWS[action_id] = {
            "action_id": action_id,
            "timestamp": timestamp,
            "action_type": req.action_type,
            "target": req.target,
            "context": req.context,
            "category": category,
            "reason": reason,
            "confidence": confidence,
            "event": event,
            "approved": None
        }

        # Broadcast to WebSocket dashboard that a review is pending
        await broadcast_ws({
            "type": "new_pending",
            "data": {
                "action_id": action_id,
                "timestamp": timestamp,
                "action_type": req.action_type,
                "target": req.target,
                "category": category,
                "reason": reason,
                "confidence": confidence
            }
        })

        print(f"[Firewall Blocked] Awaiting human decision for action {action_id}...")
        
        # Wait for human decision (or timeout after 60 seconds)
        try:
            await asyncio.wait_for(event.wait(), timeout=60.0)
            approved = PENDING_REVIEWS[action_id]["approved"]
            decision_source = "human"
        except asyncio.TimeoutError:
            # Fail-secure: default to blocking if human doesn't respond
            approved = False
            decision_source = "timeout"
            print(f"[Firewall Timeout] Review {action_id} timed out. Defaulting to BLOCK.")

        # Clean up pending entry
        PENDING_REVIEWS.pop(action_id, None)

        log_entry["allowed"] = approved
        log_entry["decision_source"] = decision_source
        if not approved:
            log_entry["reason"] = f"[Blocked by {decision_source.upper()}] {reason}"

    # 4. Save and broadcast log
    TRUST_TRACE_LOGS.append(log_entry)
    await broadcast_ws({
        "type": "new_log",
        "data": log_entry
    })

    return {
        "allowed": log_entry["allowed"],
        "is_hallucination": is_hallucination,
        "confidence": confidence,
        "category": category,
        "decision_source": log_entry["decision_source"],
        "reason": log_entry["reason"]
    }

@app.get("/logs", response_model=List[Dict[str, Any]])
def get_logs():
    return TRUST_TRACE_LOGS

@app.get("/pending")
def get_pending():
    # Return serializable summary of pending actions (omitting Event objects)
    return [
        {
            "action_id": v["action_id"],
            "timestamp": v["timestamp"],
            "action_type": v["action_type"],
            "target": v["target"],
            "context": v["context"],
            "category": v["category"],
            "reason": v["reason"],
            "confidence": v["confidence"]
        } for v in PENDING_REVIEWS.values()
    ]

@app.post("/decide")
async def make_decision(req: DecideRequest):
    """
    Submits a human approval decision for a pending action.
    """
    if req.action_id not in PENDING_REVIEWS:
        raise HTTPException(status_code=404, detail="Pending action ID not found or expired.")
        
    pending = PENDING_REVIEWS[req.action_id]
    pending["approved"] = req.approved
    pending["event"].set()  # Unblock the waiting request thread
    
    await broadcast_ws({
        "type": "decision_made",
        "action_id": req.action_id,
        "approved": req.approved
    })
    
    return {"status": "success", "action_id": req.action_id, "approved": req.approved}

# WebSocket endpoint for real-time dashboard updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # Keep connection alive; handle incoming heartbeats or commands
            data = await websocket.receive_text()
            # Simple heartbeat ping-pong
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)
    except Exception:
        if websocket in active_connections:
            active_connections.remove(websocket)
