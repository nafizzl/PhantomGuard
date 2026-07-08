import streamlit as st
import requests
import json
import time

# Set up page config
st.set_page_config(
    page_title="PhantomGuard - Trust Trace Firewall Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium styling
st.markdown("""
<style>
    /* Main Layout Styling */
    .reportview-container {
        background: #0f172a;
    }
    
    /* Header Card */
    .header-card {
        background: linear-gradient(135deg, #1e1b4b 0%, #311042 100%);
        padding: 24px;
        border-radius: 12px;
        border: 1px solid #431407;
        margin-bottom: 24px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    .header-title {
        color: #f8fafc;
        font-size: 32px;
        font-weight: 700;
        margin-bottom: 4px;
    }
    .header-subtitle {
        color: #cbd5e1;
        font-size: 16px;
    }
    
    /* Pending Review Card */
    .pending-card {
        background: rgba(239, 68, 68, 0.15);
        border: 2px solid #ef4444;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
        100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
    }
</style>
""", unsafe_type="html")

BACKEND_URL = "http://127.0.0.1:8000"

# Header Banner
st.markdown("""
<div class="header-card">
    <div class="header-title">🛡️ PhantomGuard</div>
    <div class="header-subtitle">Real-time LLM Agent Trust Firewall & Security Interceptor</div>
</div>
""", unsafe_allow_html=True)

# Fetch current system status
try:
    status_res = requests.get(f"{BACKEND_URL}/")
    if status_res.status_code == 200:
        sys_status = status_res.json()
        model_name = sys_status.get("model", "Unknown")
        ft_enabled = sys_status.get("fine_tuned_enabled", False)
    else:
        sys_status = None
except Exception:
    sys_status = None

# Sidebar Configuration
with st.sidebar:
    st.markdown("### ⚙️ Firewall Control Center")
    if sys_status:
        st.success("🟢 Firewall Service Online")
        st.metric(label="Base Classifier Model", value="Gemma-4-26B (SFT LoRA)" if ft_enabled else "Gemma-4-26B (Few-Shot)")
        st.markdown(f"**Model Path:**\n`{model_name}`")
    else:
        st.error("🔴 Firewall Service Offline")
        st.info("Start the FastAPI backend server first!")
        
    st.markdown("---")
    st.markdown("### 📊 Metrics at a Glance")
    
    # Auto-refresh checkbox
    autorefresh = st.checkbox("Auto-refresh (1s)", value=True)

# Main Grid Layout
col1, col2 = st.columns([2, 1])

# Fetch logs & pending actions from backend
logs = []
pending = []

if sys_status:
    try:
        logs = requests.get(f"{BACKEND_URL}/logs").json()
        pending = requests.get(f"{BACKEND_URL}/pending").json()
    except Exception as e:
        st.error(f"Error fetching data from API: {e}")

# Calculate summary counts
total_intercepted = len(logs)
total_blocked = sum(1 for log in logs if not log["allowed"])
total_allowed = sum(1 for log in logs if log["allowed"])
usability_issues = sum(1 for log in logs if log["category"] == "usability")
security_threats = sum(1 for log in logs if log["category"] == "security")

with col2:
    st.markdown("### 🚨 Human-in-the-Loop Reviews")
    
    if not pending:
        st.info("✅ No actions currently blocked. Agent operating safely.")
    else:
        for action in pending:
            st.markdown(f"""
            <div class="pending-card">
                <span style="color:#ef4444; font-weight:bold; font-size:16px;">🛑 ACTION INTERCEPTED</span><br/>
                <b>Timestamp:</b> {action['timestamp']}<br/>
                <b>Action:</b> <code style="color:#cbd5e1;">{action['action_type']}</code><br/>
                <b>Target:</b> <code style="color:#f1f5f9; background:#334155; padding:2px 4px; border-radius:4px;">{action['target']}</code><br/>
                <b>Context:</b> <i>"{action['context']}"</i><br/>
                <b>Classified Risk:</b> <span style="color:#f87171; font-weight:bold;">{action['category'].upper()}</span><br/>
                <b>SFT Confidence:</b> {int(action['confidence']*100)}%<br/>
                <b>Reason:</b> {action['reason']}
            </div>
            """, unsafe_allow_html=True)
            
            # Interactive decisions
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("🟢 ALLOW ACTION", key=f"allow_{action['action_id']}", use_container_width=True):
                    requests.post(f"{BACKEND_URL}/decide", json={"action_id": action["action_id"], "approved": True})
                    st.success("Action allowed.")
                    st.rerun()
            with btn_col2:
                if st.button("🔴 BLOCK ACTION", key=f"block_{action['action_id']}", use_container_width=True):
                    requests.post(f"{BACKEND_URL}/decide", json={"action_id": action["action_id"], "approved": False})
                    st.error("Action blocked.")
                    st.rerun()

    # System Status Counters
    st.markdown("---")
    st.markdown("### 📈 Live Stats")
    metric_c1, metric_c2 = st.columns(2)
    with metric_c1:
        st.metric("Total Interceptions", total_intercepted)
        st.metric("Security Blocks", security_threats)
    with metric_c2:
        st.metric("Allowed Actions", total_allowed)
        st.metric("Usability Warnings", usability_issues)

with col1:
    st.markdown("### 📋 Trust Trace Logs")
    
    if not logs:
        st.markdown("*No traces recorded yet. Spawn the coding agent to begin intercepting actions.*")
    else:
        # Render a structured list of traces in reverse chronological order
        for log in reversed(logs):
            allowed_color = "#22c55e" if log["allowed"] else "#ef4444"
            allowed_label = "APPROVED" if log["allowed"] else "BLOCKED"
            
            icon = "🔗" if log["action_type"] == "url_fetch" else "📦" if log["action_type"] == "package_install" else "💻"
            
            # Label highlighting based on risk category
            if log["category"] == "security":
                risk_tag = '<span style="background:#b91c1c; color:white; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:bold;">SECURITY RISK</span>'
            elif log["category"] == "usability":
                risk_tag = '<span style="background:#ea580c; color:white; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:bold;">USABILITY FAILURE</span>'
            else:
                risk_tag = '<span style="background:#15803d; color:white; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:bold;">SAFE</span>'
                
            st.markdown(f"""
            <div style="background:#1e293b; padding:15px; border-radius:8px; border-left: 5px solid {allowed_color}; margin-bottom:12px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <b>{icon} {log['action_type'].upper()}</b>
                    <div>
                        {risk_tag}
                        <span style="color:{allowed_color}; font-weight:bold; margin-left:10px;">{allowed_label}</span>
                    </div>
                </div>
                <div style="margin-top:8px;">
                    <b>Target:</b> <code style="background:#0f172a; padding:2px 5px; border-radius:3px; color:#38bdf8;">{log['target']}</code>
                </div>
                <div style="font-size:13px; color:#94a3b8; margin-top:4px;">
                    <b>Context:</b> "{log['context']}"
                </div>
                <div style="font-size:12px; color:#cbd5e1; margin-top:8px; background:#0f172a; padding:8px; border-radius:4px;">
                    💡 <b>Evaluation (Conf: {int(log['confidence']*100)}%):</b> {log['reason']} (Source: {log['decision_source']})
                </div>
            </div>
            """, unsafe_allow_html=True)

# Auto-refresh loop
if autorefresh:
    time.sleep(1.5)
    st.rerun()
