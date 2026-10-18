# Camera/display + stored-image coexistence target

**The first user-reported board run failed before inference; no combined hardware PASS yet.** The revised single-buffer capture path requires another deliberate user-triggered write/test. This HP-only target is the first integration gate, not live-camera classification or an ASL model. See the [memory/peripheral/ownership audit and failure analysis](../../docs/camera-inference-audit.md#first-board-run-unsupported-dequeue-assumption-corrected).

## Build without device access

The accepted standalone stored-image build, model/reference artifacts, pinned runtime, Viewfinder submodule, and Ensemble 2.2.0/CMSIS 6.1.0 packs must already exist. This builder revalidates them; it does not silently export/rebuild/replace a baseline.

```bash
python3 -m tools.camera_inference_firmware \
  --layout hp-only-large --image ml/reference/images/cat.jpg --jobs 1
```

Add `--rebuild` for a clean integration build. Generated RTE files/assets/platform port/project files and outputs are isolated under `.work/inference/camera-inference-firmware/`. Existing smoke/stored-image firmware and programming directories are untouched. The generated success manifest remains `hardware_verified: false` and `programming_authorized: false`.

VS Code also offers **HandGPT: Build camera coexistence (no device access)** from the HandGPT root. It has no programming dependency.

```text
.work/inference/camera-inference-firmware/camera-inference.csolution.yml
.work/inference/camera-inference-firmware/out/camera-inference/DevKit-E8-HP/debug/camera-inference.elf
.work/inference/camera-inference-firmware/out/camera-inference/DevKit-E8-HP/debug/camera-inference.bin
.work/inference/camera-inference-firmware/camera-inference.map
.work/inference/camera-inference-firmware/manifest.json
```

The revised binary uses 4,719,808 bytes in the audited larger HP MRAM region, leaving 518,976 bytes before the reserved tail. The actual generated manifest, not these documentation numbers, governs future build checks.

## Intended hardware sequence — not yet verified

1. Request camera/display + HP NPU power while retaining both SRAM banks; initialize one shared UART/SysTick/platform port.
2. Capture and display three 480×480 MT9M114 ISP RGB888-planar snapshots on the 480×800 RGB565 panel. The simple CPU display path omits Viewfinder's graphics heap/logo and leaves the bottom 320 rows black.
   The revised path waits for full MI frame-end, processes statistics, and requires a successful pipeline stop before reading its known single buffer. It does not call `DQBUF`: the pinned CMSIS ISR does not populate the completed-buffer queue. Startup prints `single known buffer, no DQBUF` to distinguish this revision.
3. Pause camera capture with DMA stopped. Keep LCD scanout active and run the **unchanged cat-image self-test**, with the same all-logit comparison thresholds/reference bytes as the standalone image.
4. Require display scanline events during that self-test, then capture/display two more frames. Only then emit:

   ```text
   COEXIST SELFTEST PASS frames=5 display_events_during_test=... elapsed_ms=... IRQs=... jobs=... checked=1000
   ```

5. Continue preview, printing `PREVIEW frames=... scanlines=...` about once per second. A subsequent fault/timeout prints `COEXIST FAIL`; an earlier self-test PASS does not excuse a later failure.

There is **no camera-pixel classification**, no preprocessing for camera inference, no continuous NPU loop, no GPU acceleration, and no simultaneous camera capture during NPU execution. The top-5 labels still refer to the stored cat photo, not what is in front of the lens. New errors use 200–208; stored-model error codes are retained if that runner fails.

## Prepare and review without programming

The target-specific helper [`tools/prepare_camera_inference.py`](../../tools/prepare_camera_inference.py) has only `prepare` and `review` commands. It revalidates the camera build and its standalone stored-image prerequisite, source/generated/project/SDK/tool identities, model/reference bytes, comparison thresholds, and actual linked buffers/vectors/startup tables. Builds made before the extra provenance fields were added must first be rebuilt with the build command above; no standalone baseline rebuild is needed.

```bash
python3 -m tools.prepare_camera_inference prepare \
  --setools-root ~/alif/app-release-exec-linux \
  --image ml/reference/images/cat.jpg --hp-only-board

python3 -m tools.prepare_camera_inference review
```

`--hp-only-board` confirms that no HE/A32 firmware or reclaimed MRAM data needs preservation; it **does not authorize a write**. The helper clones the already configured SETOOLS 1.112.00 installation into a new ignored, mode-0700 stage under `.work/inference/camera-inference-programming/`. Only the clone's `app-gen-toc` runs. The installed toolkit, standalone packages, and their latest-package pointers are left unchanged.

The package selects `handgpt-camera-inference.bin` at **`0x80001000`**, unsigned XIP, with only **DEVICE + USER_APP (M55_HP, boot)**. Verification checks map rows/extents, actual binary TOC entries/tail/CRC, and the generated DEVICE bytes. The first 4 KiB remain reserved; the firmware must end before `0x80500000`, and DEVICE/certificates/ATOC must fit wholly within the reserved tail ending at `0x80580000`. Receipts bind the exact build/image/config/package and private toolkit files, including dependencies outside `build/`. Signing material and raw private logs must not be committed or shared.

The current package has been prepared and reviewed offline, including the programmer's default dry run (without `--write`):

| Object | Verified extent |
|---|---|
| Revised camera coexistence image, 4,719,808 bytes | `[0x80001000, 0x804814c0)` |
| DEVICE/certificates/ATOC, 3,888 bytes | `[0x8057f0d0, 0x80580000)` |

Image SHA-256: `c49f474e7b790e880f2a1af6e1ba02cfa78cf3ab65c03d37ef0bdfb424aa603b`. This is the revised no-`DQBUF` candidate, prepared in a new stage after the first reported hardware failure; previous receipts/attempt logs are retained. The standalone latest-package pointers/build manifest and protected installed-toolkit state remained unchanged. **No writer was run or serial port opened for this revision.** Revalidate the current receipt before any later user-triggered write; this record neither authorizes programming nor establishes hardware acceptance.

## Deliberate programming — separate confirmation-gated command

[`tools/program_camera_inference.py`](../../tools/program_camera_inference.py) defaults to review only:

```bash
python3 -m tools.program_camera_inference review

# Dry run: reviews the exact image/command; does not open or inspect the port.
python3 -m tools.program_camera_inference program --port /dev/ttyACM0
```

**Do not use `tools.program_stored_image`, `tools.program_smoke`, or the Viewfinder programming task for this target.** Those select other images/receipts. Never overwrite an older staged binary with this one or relax the existing guards. The new writer reuses only the existing serial-port validation and non-interactive child-process transport, not another target's package selection.

The following command **WRITES THE BOARD** and is for a separate, deliberate user action only. It replaces the current HP application, including standalone stored-image inference, and writes the matching baseline DEVICE configuration/boot table. It does not request full erase, system-package updates, provisioning, discovery, or debug stubs.

1. Close serial monitors and verify the intended E8 Rev A0 board, MT9M114 camera, and panel.
2. Disconnect board power/USB **before** selecting SW4 **SE**, then reconnect for SETOOLS.
3. In an interactive terminal, run:

   ```bash
   python3 -m tools.program_camera_inference program --port /dev/ttyACM0 --write
   ```

4. Review the printed identity and type exactly **`PROGRAM E8-HP CAMERA INFERENCE`** if you intend to write that package. Other targets' phrases, piped input, and abbreviated `--w` are not accepted. The complete build/package verification and serial-device identity check run again after confirmation. Do not change any input or the connected device during this process.

The only child writer command is the reviewed private toolkit's `app-write-mram -p -c <explicit-port>`; its stdin is disabled, so unexpected toolkit prompts cannot be approved. SETOOLS normally resets the device during programming. Each attempt gets a separate `program-*/attempt.json` and `program.log` under its preparation stage. A tool exit is **not hardware inference acceptance**, and receipts/build manifests remain unverified. Failure or interruption may leave MRAM partially written; inspect the private log rather than retrying or overriding a device mismatch blindly. Port metadata checks cannot prove the physical identity of the board.

## Hardware acceptance after a user-triggered write

Disconnect power before selecting SW4 **U4**, then reconnect. Capture the complete UART log at 115200 8N1, no flow control, for example:

```bash
picocom --baud 115200 --databits 8 --parity n --stopbits 1 --flow n \
  --imap lfcrlf /dev/ttyACM0
```

Require all of the following, then repeat from a full power cycle:

- Visually correct camera preview in the top 480×480 area, with the bottom 320 rows black.
- `COEXIST SELFTEST PASS`, `checked=1000`, and a completed NPU job/IRQ with no reported errors/timeouts.
- Continued `PREVIEW frames=... scanlines=...` progress and a responsive picture, with no later `COEXIST FAIL` or fault.

Share the application UART text and what the screen shows, **not** the private toolkit/signing files. Hardware validation of this target is still outstanding; only after it passes do we add exact-frame export/preprocessing and frozen-camera-frame classification against the host.

## Licensing

The power and driver sequence adaptations retain Alif notices. The reused sensor calibration sources and generated configuration/linker copies remain subject to the vendor's `firmware/vendor/alif_viewfinder/License.txt` and applicable SDK notices. This target does not relicense them.
