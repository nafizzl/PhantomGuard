# 🛡️ PhantomGuard: Slide Deck Presentation Script

This document serves as the slide-by-slide outline and speaker script for the PhantomGuard presentation.

---

### 🖥️ Slide 1: Title & Hook
* **Slide Title**: PhantomGuard: The Trust Firewall for Autonomous AI Agents
* **Visuals**: A shield graphic protecting a terminal interface running an AI agent (Claude Code/Aider).
* **Bullet Points**:
  - Zero-Trust Agent Interception
  - Multi-Stage Verification Pipeline
  - Real-Time Supply Chain Defense
* **Speaker Script**: 
  > "As AI coding agents transition from generating code to autonomously executing it, they introduce a massive new security risk. Today, we present PhantomGuard—a real-time trust firewall designed to stop autonomous agents from installing malicious packages or visiting hijacked domains."

---

### 🖥️ Slide 2: The Core Problem
* **Slide Title**: The Threat: Phantom Squatting & Slopsquatting
* **Visuals**: Diagram showing an LLM hallucinating a package name, and an attacker registering it to distribute malware.
* **Bullet Points**:
  - **Agent Hallucinations**: Agents routinely invent package names or documentation URLs that do not exist.
  - **Phantom Squatting**: Attackers monitor LLM outputs and register these domains for phishing or hijack.
  - **Slopsquatting**: Threat actors upload malware to registries (npm, PyPI) under hallucinated package names.
* **Speaker Script**: 
  > "LLMs frequently hallucinate resources. If an agent tries to fetch a non-existent URL or install a non-existent package, an attacker can register that exact name and instantly compromise the developer's system. This is what we call Phantom Squatting and Slopsquatting."

---

### 🖥️ Slide 3: What's Novel & Unique (Our "Secret Sauce")
* **Slide Title**: The Hybrid Decision Pipeline
* **Visuals**: Pipeline flow diagram (Local Heuristics ➡️ AMD ROCm Embeddings ➡️ Gemma 4 SFT ➡️ Human-in-the-Loop).
* **Bullet Points**:
  - **Multi-Stage Filtering**: Bypasses heavy LLM processing for clear cases, minimizing latency.
  - **Usability vs Security**: DNS and active link checks immediately flag broken sites before querying AI.
  - **Dual-Model Trust**: Low-latency similarity search on AMD ROCm combined with deep-reasoning Gemma 4 classification on Fireworks.
* **Speaker Script**: 
  > "What makes PhantomGuard unique is its hybrid filtering. We don't just throw every request at an LLM. We filter out simple broken links first, use embedding models on local AMD ROCm GPUs for ultra-fast typosquat detection, and call a specialized fine-tuned Gemma 4 model only when deep semantic reasoning is needed."

---

### 🖥️ Slide 4: Implementation Details
* **Slide Title**: Under the Hood of the Interceptor
* **Visuals**: Code snippet showing the Python daemon and proxy port redirection.
* **Bullet Points**:
  - **Transparent HTTP MITM Proxy**: Intercepts outgoing package and network traffic on port `8000`.
  - **Surgical CLI Hooks**: Pre-tool-use hooks that validate agent actions before execution (exits `0` or `1`).
  - **Fireworks SFT Gemma 4**: Customized Google Gemma-4-26B adapter achieving 89.86% zero-shot accuracy.
* **Speaker Script**: 
  > "PhantomGuard runs as a local background daemon. It includes a transparent MITM proxy that intercepts agent HTTP requests, and surgical CLI hooks compatible with tools like Aider. Our fine-tuned SFT Gemma 4 model adapter runs serverless on Fireworks, providing highly accurate semantic classification."

---

### 🖥️ Slide 5: Future Work & Startup Evolution
* **Slide Title**: The Roadmap: Scaling & ROCm Enhancement
* **Visuals**: A roadmap graphic pointing towards enterprise security integration.
* **Bullet Points**:
  - **ROCm Similarity Scaling**: Run local sentence-transformer distance calculations in parallel with the LLM reasoning to double-check classification confidence.
  - **Pre-emptive Registration (Sinkholing)**: Automatically claim hallucinated domains and package placeholders before attackers do.
  - **Enterprise SASE Gateway**: Transition the local proxy into a cloud-hosted enterprise agent firewall.
* **Speaker Script**: 
  > "For future work, we plan to deeply integrate our local AMD ROCm embedding server to run distance calculations side-by-side with LLM reasoning. We are also building a pre-emptive sinkholing engine to auto-register hallucinated domains before threat actors can claim them, creating a complete enterprise security platform."
