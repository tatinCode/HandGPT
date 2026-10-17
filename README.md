# HandGPT

**Offline ASL handshape recognition on the Alif Ensemble E8, with a roadmap toward fingerspelling and a small whole-sign vocabulary.**

HandGPT aims to recognize camera-based signing entirely on-device using the Cortex-M55 High-Performance core and Arm Ethos-U85 NPU. The first milestone is a small static handshape classifier; later stages will assemble letters into words and explore recognizing selected whole signs.

> This is an early prototype, not a general ASL translator. ASL includes movement, location, facial expression, grammar, and context—not just handshapes or English word labels.

## Current status

The repository currently contains:

- [`main.cpp`](main.cpp): an ExecuTorch runner intended to execute an embedded MobileNetV2 model on a fixed test image, with Ethos-U85 initialization, completion polling, SEGGER RTT logging, fault diagnostics, and an LED heartbeat.
- [`firmware/vendor/alif_viewfinder`](firmware/vendor/alif_viewfinder): a fork of Alif's camera/display example, configured for **DevKit-E8-HP + MT9M114**. The user has confirmed a working preview on the attached screen.
- [`docs/camera-baseline.md`](docs/camera-baseline.md): the working hardware configuration, build/programming workflow, tool versions, and remaining verification checks.
- [`HandGPT_PROJECT_PLAN.md`](HandGPT_PROJECT_PLAN.md): the original bring-up plan and initial handshape MVP milestones; consult the baseline document for the current camera status.

**Camera-to-screen preview works; inference integration, a trained handshape model, fingerspelling, and whole-sign recognition are not implemented yet.** Successful on-board inference still needs to be verified; the existing runner performs ImageNet classification, not ASL recognition.

## Hardware and intended software stack

| Component | Role |
|---|---|
| Alif Ensemble E8 DevKit | Embedded platform |
| Cortex-M55 HP | Frame acquisition, preprocessing, and application logic |
| Arm Ethos-U85 | Acceleration of supported quantized model operations |
| MT9M114-105 AP-Vision camera | Working preview through the Viewfinder example |
| Attached display (ILI9806E driver selected) | Working camera preview; touch input not yet validated in firmware |
| PyTorch | Host-side model training and evaluation |
| ExecuTorch + Arm Ethos-U backend / Vela | Model export and on-device execution |
| SEGGER RTT or a verified serial channel | Predictions and diagnostic output |

Live inference is intended to work without an internet connection. Training and model export run on a development computer.

## Roadmap

### Stage 1 — Recognize static handshapes

Start with **A, B, C, L, Y**, plus a trained `NO_HAND` class and an explicit `UNKNOWN` rejection mechanism.

1. Verify board programming and the LED heartbeat.
2. Capture a readable camera frame.
3. Verify a known reference model on the physical E8.
4. Train and deploy the small handshape classifier.
5. Connect live frames to stable predictions and measure accuracy and latency.

Initial pipeline:

```text
Camera → crop/resize/preprocess → classifier → rejection/smoothing → label
```

### Stage 2 — Fingerspell words

Expand toward the **24 static ASL alphabet letters**. Add temporal recognition for the motion-dependent letters **J and Z** separately.

Individual predictions need a deliberate selection mechanism before they can become text. The initial interaction to test is:

- Hold a letter steadily to select it once.
- Return to a neutral/no-hand state before selecting another letter, including repeated letters such as `LL`.
- Provide explicit **space**, **delete**, and **clear** controls; their input method remains to be chosen.
- Keep uncertain predictions out of the text buffer and show selection feedback.

```text
Stable letter → selection/release logic → text buffer → spelled words
```

Fingerspelling words is not the same as recognizing whole ASL signs. Performance must be evaluated on complete spelling sequences, not just isolated letter images.

### Stage 3 — Recognize a small whole-sign vocabulary

Add a separate whole-sign mode, initially targeting **5–10 carefully selected, visually distinct signs** whose camera framing and motion can be captured reliably.

This stage requires **new labeled video sequences and likely a different model**. A letter classifier does not automatically become a whole-sign recognizer.

```text
Camera → short frame sequence → temporal model → rejection/stability → sign label
```

Reuse the camera pipeline, deployment infrastructure, and output interface where practical. Validate the temporal model's memory requirements, latency, and NPU operator support before committing to an architecture. Some signs require two hands, body position, or facial expression, so a tight single-hand crop will not be sufficient for every sign.

Continuous signing and sentence translation remain outside this roadmap's initial scope.

## Data and evaluation

- Collect data with participant consent and document image/video retention.
- Include different people, lighting conditions, backgrounds, hand sizes, skin tones, and handedness where practical.
- Split training and evaluation data by **person/session**, not adjacent video frames.
- Include empty scenes and unsupported gestures; `NO_HAND` alone does not solve unknown-sign rejection.
- Keep training and device preprocessing identical, including orientation, color order, tensor layout, and quantization.
- Report held-out accuracy, confusion matrices, false selections, latency, and memory use. For fingerspelling, also measure complete-word correctness; for whole signs, test transitions and periods with no sign.

## Building and running

Initialize the firmware example and its nested dependencies, then open it as its own VS Code folder:

```bash
git submodule update --init --recursive
code firmware/vendor/alif_viewfinder
```

The submodule URL uses SSH and requires GitHub SSH access. Select **DevKit-E8-HP / debug** and follow [`docs/camera-baseline.md`](docs/camera-baseline.md) to build and intentionally program the camera/display example. The pinned fork commit preserves the camera component selection and the active target.

**The inference runner is not yet a standalone buildable project.** Root-level `main.cpp` references model/image headers under `assets/`, board support, ExecuTorch, the Ethos-U driver, and SEGGER RTT that are not included here. It has not been integrated into Viewfinder's CMSIS project or memory layout.

Integrate the runner with the matching Alif/CMSIS project and verified SDK/toolchain versions. Follow the bring-up sequence and reference examples in [`HandGPT_PROJECT_PLAN.md`](HandGPT_PROJECT_PLAN.md), then record reproducible build, flash, and output-reading instructions once validated.

Do not assume the Blinky memory layout can accommodate inference. Review SRAM placement, model storage, and NPU access requirements. Use documented programming tasks intentionally: SETOOLS discovery/system-package operations described in the project plan can write to the device.

## Immediate goal

**Preserve the working preview, verify known-good stored-image inference, then prove both can coexist in one firmware image.** Five live handshape predictions come next, followed by reliable fingerspelling. Whole-sign recognition is a later, separately trained capability.
