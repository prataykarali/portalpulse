# PortalPulse local live demo

The public prototype is at `https://portalpulse.antideploy.app/website`. To run locally, start from the repository root with `./scripts/start_demo.sh` and open `http://127.0.0.1:8000/website`. The script serves the website, API, and event stream from one local FastAPI process. `Ctrl+C` stops the local server.

## Laptop-safe controls

The demo does not generate traffic until **Start complete demo** is pressed. The control loop also idles while traffic is stopped or paused. The local generator has hard limits of **6 workers**, **12 requests per second**, and **100 seconds** per run. The 12-case story normally completes in about 86 seconds. The red **Stop load** button is available on every page and cancels request workers and clears injected faults without erasing the graphs. **Pause** pauses both traffic and model cycles; **Reset** clears the run and faults.

On hosts with a CPU package sensor, demo mode enforces a thermal guard. A new run is held at **85°C or higher**. An active run stops at **88°C or higher**. If the sensor is unavailable, the worker, rate, and time limits still apply. Start failures appear in the site as a control message. To change the server port, set `PORTALPULSE_DEMO_PORT`.

## What is measured

Virtual users describe scenario scale; they are not launched as thousands of processes. The graphs plot actual requests to the local IEMCRP simulator: request rate, latency percentiles, failures, recent DB pool peak, and queue pressure. The story includes baseline variation, result rush, DB pressure, HTTP 429 and 503 cases, recovery, and a second wave. M1 uses the same measured HTTP window that feeds the Traffic graphs. M2 XGBoost, M3 Isolation Forest, M4 root-cause model, and M5 PyTorch policy use loaded local model files; the runtime badges show inference or fallback status. M6 can reject a harmful action. M7's **executed** state means the local portal action ran; recovery is reported only after a later measured request window improves. A failed verification remains visible.

Decision and model evidence are under **AI Models**. Before and after measurements and incidents are under **Traffic**. The architecture diagram is generated with Archify and embedded on AI Models. PulseBot explains buttons and action outcomes.

## Nirantar scope

The **Why it matters** page links to a local overlay around the external Nirantar website. Its Tatkal notices are labeled as examples. The public Nirantar frontend at `https://bronze-tinsel-n8pb.here.now/` now has native red queue warnings, blue queue-control and M7 action cards, and green admission/recovery cards. Public fair-access requests use a prototype bridge hosted by PortalPulse; the browser flow from queued search to automatic admission was verified. PortalPulse's Nirantar M7 connector still controls its in-process bridge rather than the deployed Nirantar backend, so those M7 cards are labeled as simulator events. The rest of Nirantar's backend has not been deployed here. See `PORTALPULSE_INTEGRATION.md` in the Nirantar checkout for details.

## Checks

Run `python3 -m pytest -q tests/test_local_live_demo.py tests/test_module8_warnings.py tests/test_traffic_controller.py` for focused backend checks and `node --check website/live-demo.js` for the frontend script. The tests start only brief, bounded local traffic. Browser inspection can be done at `/website` and `/static/nirantar-live.html`.
