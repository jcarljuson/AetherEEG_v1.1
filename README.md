# AetherEEG
**Developed by Jcarl Juson**

This is AetherEEG

Currently optimized for NeuroSky MindWave headsets (eSense protocol), this application parses both raw brainwaves and pre-calculated focus metrics to provide a powerful analytical and interactive platform for researchers, developers, and enthusiasts.

---

## Core Features

* **Live Telemetry & Waveforms:** Seamless real-time plotting of absolute Raw EEG spikes, alongside live tracking of separated clinical rhythms: **Alpha, Beta, Delta, and Theta waves**.
* **Spectral Power Density:** An interactive, highly responsive 8-band frequency area plot mapping Delta, Theta, Low/High Alpha, Low/High Beta, and Low/Mid Gamma ranges simultaneously.
* **Mental State Tracking:** Real-time percentage (`%`) ring gauges for both **Attention** (focus/concentration) and **Meditation** (relaxation/calm) alongside dynamic status chips classifying the reading as Low, Neutral, or High.
* **Spatial Brain Mapping:** An animated visual representation of a human brain that dynamically illuminates specific lobes based on the localized frequency intensity of your ongoing brainwaves.
* **Brain-Controlled Mouse:** An experimental accessibility feature allowing you to control your actual Windows Desktop cursor utilizing your brainwaves! It maps the Attention/Meditation outputs directly to screen X and Y coordinates, and registers eye blinks as Mouse Clicks.
* **Drone Flight Simulator:** A built-in 3D physics simulator that lets you practice maintaining specific brainwave states to successfully pilot a simulated quadcopter.
* **Simulation Mode:** A completely synthetic internal data engine allowing you to demonstrate the app, test UI changes, and run the recording pipelines without needing physical hardware connected.

---

## Scientific Recording Pipeline

AetherEEG features a robust toolset built specifically for data collection and dataset generation for Machine Learning models or scientific study:

1. **Capture:** Click the **`⏺ Record EEG`** button at any time during a live session to begin aggressively buffering every single telemetry point to memory, alongside an absolute timestamp. 
2. **Review:** Clicking Stop immediately opens a dedicated **Review Dialog**. A massive interactive graph will render the entirety of your recorded timeline.
3. **Interactive Cropping:** Drag the blue `LinearRegionItem` handles over the graph to precisely isolate the specific event or time period you wish to save.
4. **Data Export:** Click **Save to CSV**. The app will slice the recording and export a perfectly formatted spreadsheet containing 12 columns (`Timestamp(s), Raw, Attention, Meditation, Delta, Theta, LowAlpha...`) ready for immediate analysis in Pandas, MATLAB, or Excel.

---

## How to Run the App

AetherEEG is designed to be completely plug-and-play. Choose whichever launch method works best for your environment!

### Option 1: The Native Windows Application (Recommended)
You do not need Python installed to run the standalone executable. 
Simply navigate into the project folder, open `dist/AetherEEG/`, and double-click **`AetherEEG.exe`**. 
> *Tip: You can right-click this `.exe` file and select "Send to > Desktop" to create a standard quick-launch shortcut!*

### Option 2: The Batch Shortcut
If you are developing the code and want to run the python source quickly:
Just double-click the **`run_aether.bat`** file in the root folder. It will seamlessly activate your local python virtual environment and launch the app in one click.

### Option 3: Command Line
For developers running from a terminal:
```bash
python src/app.py
```

---

## Troubleshooting & Important Notes

* **Flatlining Metrics (0%):** This is a hardware safety feature. If the internal **Signal Quality Indicator** (located above the Brain Map) reads anything other than *"Signal: Excellent"*, the headset forces the Attention and Meditation metrics to output exactly `0%` to prevent false data generation. *Adjust the metal sensor until it sits flush against your forehead.*
* **Administrator Privileges:** Due to deep OS-level integration, controlling your literal Windows Mouse Cursor with your brain (`Mouse Control` toggle) requires the application to be run as an Administrator to bypass Microsoft UIPI security protocols.
