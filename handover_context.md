# Handover Context: PhantomGuard State & Submission Roadmap

This document serves as the developer context for future coding sessions (e.g., using Aider, Claude Code, or Codex) to finalize and demonstrate PhantomGuard.

---

## 🛠️ Current State & Accomplishments

We successfully reorganized the workspace and completed the development of the standalone dependency package (`phantomguard-firewall`).

### 1. Reorganized Directory Split
- **`demo_app/`**: Contains the FastAPI proxy, Streamlit control dashboard, datasets, SFT training scripts, and simulation scripts.
- **`phantomguard_package/`**: Standalone, pip-installable python package. Installs the `phantomguard` command line utility globally.

### 2. Upgraded Interception Architecture
- **Surgical Hooks**: The `phantomguard hook` command acts as a PreToolUse validation gate for agent CLI tools (e.g., Claude Code), returning exit codes `0` (allow) or `1` (block).
- **Socket MITM Proxy**: The `phantomguard proxy` handles environment-level `HTTP_PROXY`/`HTTPS_PROXY` interception, redirecting requests to the local daemon.

### 3. Compliance & Failover Pipelines
- **AMD ROCm Embedding Server**: Runs `embed_server.py` inside the hackathon Jupyter Notebook to catch "conflation-style" typosquats.
- **2.0s Timeout**: If the AMD ROCm server is offline or times out, the local daemon automatically skips it and proceeds to the SFT model.
- **Fireworks SFT 404 Fallback**: Because custom PEFT/LoRA models on Fireworks require paid, dedicated deployments, the local verifier is configured with a serverless fallback:
  - If the custom Gemma 4 model returns a 404, it automatically fails over to the online model **`accounts/fireworks/models/deepseek-v4-pro`** (which is active on your credentials) using our preloaded security few-shot examples.

### 4. Robustness Updates
- **Windows Emoji Bug Fixed**: Stripped all unicode emojis from terminal output streams to prevent `cp1252` encoding crashes on default Windows shells.
- **Dotenv Path Resolution**: Changed `load_dotenv` in `config.py` to use `find_dotenv(usecwd=True)` and `override=True` so the local `.env` is always loaded from your project root.

---

## 🏁 Submission Day Step-by-Step Roadmap

When you are ready to record your demo video or present to the judges, follow this checklist:

### Step 1: Spin up the AMD Notebook Server
1. Paste and run the **`phantomguard_package/phantomguard/notebooks/embed_server.py`** code into a cell in your AMD ROCm Jupyter notebook.
2. In the notebook terminal, run a tunnel to get a public URL:
   ```bash
   ngrok http 5000
   ```
3. Copy the generated `https` URL and add it to your local workspace `.env` file:
   ```env
   AMD_NOTEBOOK_URL="https://your-ngrok-tunnel.ngrok-free.app"
   ```

### Step 2: Deploy your Custom Gemma Model (Temporarily)
1. Log in to your **[Fireworks AI Dashboard](https://fireworks.ai/)**.
2. Go to **Models** -> **User Models** -> Find **`ft-w4dd2z1a-xxn0j`**.
3. Click **Deploy**.
4. Once the status shows `READY`, the local daemon will automatically detect it and route the deep reasoning stage to your fine-tuned model instead of the Deepseek fallback.

### Step 3: Record the Demo Video
1. Start the daemon in your project terminal:
   ```powershell
   phantomguard start
   ```
2. Start the Streamlit Control Dashboard:
   ```powershell
   streamlit run demo_app/frontend/dashboard.py
   ```
3. Run the interactive coding agent simulation to watch live interventions:
   ```powershell
   python demo_app/scripts/simulate_agent.py
   ```
4. Record your screen showing:
   - Safe actions passing seamlessly in the terminal.
   - Squatted domains (e.g. `docs.github-extra-workflows.org`) halting the simulated agent.
   - You clicking **Approve** or **Block** on the Streamlit dashboard and watching the agent instantly resume or abort.
   - The trace logs showing the `compute_backend` tags (`amd_notebook_rocm` and `fireworks_lora`) in real time.

### Step 4: Clean Up & Undeploy
1. Stop the local daemon:
   ```powershell
   phantomguard stop
   ```
2. **Undeploy your SFT Model** on the Fireworks web console to avoid burning your remaining API credits.
3. Stop the tunnel cell in your Jupyter notebook.
