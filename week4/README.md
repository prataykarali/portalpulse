# Week 4: Action Intelligence & AI SRE Copilot (M5 & M6)

## Strategic Objective
Week 4 focuses on the **Decision & Explanation Layer** of PortalPulse:
1. **Module 5 (M5: Tactical Action Intelligence Policy Network)**:
   - *"Given everything happening, what should PortalPulse recommend?"*
   - Deep PyTorch Multi-Layer Perceptron (MLP) with BatchNorm, Dropout, and Kaiming He initialization.
   - Hardware-accelerated on the **NVIDIA GeForce RTX 2050 GPU (4GB VRAM)** with CUDA.
   - Trained on 25,000 synthetic state-action tuples codified from SRE expert playbooks and `secure_action.md`.
   - Maps the 12D+ unified system state into probability distributions over 11 discrete tactical SRE actions.
   - Includes interactive Jupyter Notebook: `notebooks/M4_Action_Intelligence_MLP.ipynb`.
2. **Module 6 (M6: AI Operations Assistant & SRE Copilot)**:
   - *"Explain everything to the human operator in plain English."*
   - Context-aware LLM agent equipped with tool calling (`get_current_metrics`, `get_forecast`, `get_rca_diagnosis`, `get_action_recommendations`).
   - Grounded via RAG (Retrieval-Augmented Generation) in `secure_action.md` and system runbooks.

## Deliverables & Modules
- `backend/m4_action_intelligence/`: PyTorch Deep MLP policy architecture, GPU training loop, and inference engine.
- `notebooks/M4_Action_Intelligence_MLP.ipynb`: Interactive Jupyter training notebook with loss curves and confusion matrices.
- `backend/m5_assistant/`: LLM tool-calling copilot and RAG knowledge base.
