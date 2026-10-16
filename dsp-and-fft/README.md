# Voice-controlled LEDs on the XIAO nRF52840 Sense

Say **"blue led on"**, **"switch off green"**, **"on blue"** ... and the board switches its green / blue LED.
Everything runs **on the board** (Cortex-M4F, 64 MHz, 256 KB RAM, 1 MB flash) using its built-in PDM microphone. No
cloud, no phone.

There are two working firmwares, built one after the other:

| App | How it works | Good at | Weak at |
|---|---|---|---|
| `voice_dsp` | Cut each word out by loudness -> 29 hand-made DSP features -> logistic regression | single words with small pauses (~91 % on held-out recordings), tiny and fast | natural sentences: words run together |
| `voice_cnn` | Log-mel spectrogram -> small 1D CNN on sliding 0.67 s windows -> streaming decoder -> command logic | sentences in any word order, filler words ignored | needs more speakers / more data (see Limitations) |

Measured on the real board with `pixi run cnn-test` (36 spoken prompts like "switch on blue", one speaker):
**90 % of keywords heard correctly, 93 % of colour+action prompts gave exactly the right LED command.**

---

## 1. What you need

* Seeed **XIAO nRF52840 Sense**, USB cable. macOS on Apple silicon (paths are macOS-specific).
* [`arduino-cli`](https://arduino.github.io/arduino-cli/) with the Seeed core and one library. The build uses the Arduino
  core's sources and toolchain but **not** the Arduino IDE (CMake + Ninja, see `cmake/`):
  ```
  arduino-cli core install Seeeduino:nrf52          # core 1.1.13 (see cmake/xiao_nrf52840.cmake)
  arduino-cli lib install "Seeed Arduino LSM6DS3"
  ```
* `cmake`, `ninja`, [`pixi`](https://pixi.sh) (Python environment for training / tools: numpy, scipy, scikit-learn,
  PyTorch, Textual, pyserial, JupyterLab).

## 2. Quick start

```
make APP=voice_cnn build            # compile   (APP = blink_demo | audio_capture | voice_dsp | voice_cnn)
make APP=voice_cnn flash            # upload (auto-detects /dev/cu.usbmodem*, does the 1200-baud reset itself)
make monitor                        # serial output, Ctrl-C to leave   (close it before running any pixi tool: one program per port)
pixi run cnn-test --minutes 4       # read prompts aloud, get a score
```

Each app builds into its own folder `build/<app>/`. If you **add a new `.cpp` to `common/`**, run
`make APP=<app> configure` once (CMake collects the file list at configure time).
If the board stops answering: double-tap its reset button (orange LED pulses = bootloader), then flash again.

## 3. Repository layout

```
apps/                 firmware (one folder per app, each has main.cpp)
  blink_demo/           original FreeRTOS demo (blink, button ISR, queue, mutex)
  audio_capture/        records 1 s clips from the mic on request (for building the dataset)
  voice_dsp/            DSP features + logistic regression  (model_params.h is generated)
  voice_cnn/            log-mel + 1D CNN + command logic
  voice_tflm/, voice_edge_impulse/   empty stubs (not implemented)
common/               code shared by the apps (also compiled on the PC for tests)
  audio_pdm.*           mic wrapper      led_control.*   LED task + command queue
  voice_features.*      29 DSP features  kws_cnn.*       log-mel front end, CNN, decoder
  cnn_params.h          GENERATED CNN weights (117 KB)
cmake/                toolchain + Arduino-core build rules       Makefile, CMakeLists.txt
tools/                Python: recording, training, export, tests (see section 5)
notebooks/            explore_dataset.ipynb (plots), train_classifier.ipynb (DSP model study),
                      sentence_cnn.ipynb (continuous speech: why cutting fails, the CNN, held-out results, live test)
models/               trained PyTorch checkpoints + normalisation
dataset/              isolated words, one folder per word (gitignored)
dataset_live/         board-captured word windows from tools/live_session.py
dataset_raw/          continuous audio sessions from tools/raw_session.py (gitignored)
```

## 4. How it was built, step by step

Each step names the tool that does it and what we learned. Numbers are held-out unless stated.

### Step 1 - Build the firmware without the Arduino IDE
`cmake/xiao_nrf52840.cmake` compiles the Seeed core (+ FreeRTOS, TinyUSB, PDM, I2C) into a static library and links your
`apps/<name>/main.cpp` against it. `blink_demo` was the first target: FreeRTOS tasks, a button interrupt, a queue and a
mutex (naming convention `vTask / xHandle / prv`).

### Step 2 - Record a dataset from the board's own microphone
* `apps/audio_capture` sends 1 s of 16 kHz audio over USB when the PC asks.
* `pixi run tui` (Textual TUI) or `pixi run record` (plain menus) manage words, record clips, play them back, delete
  (to `dataset/_trash/`, reversible) and mix background noise into an augmented copy.
* About 100 clips each of: **on, off, green, blue, noise** (claps, silence, typing).

Two hardware lessons that cost time:
* **The PDM driver switches the mic off for good if nobody reads it for ~16 ms**, and the first start after boot delivers
  one empty buffer then stalls. Firmware starts the mic inside the audio task and restarts it if no audio arrives for
  250 ms (`audio_pdm.h` documents this).
* **Every clip starts with a mic start-up artifact**: the DC level swings by hundreds of counts over the first second and
  the first few frames are noisy. Features therefore skip the first 20 frames and use per-frame DC removal.

### Step 3 - Isolated words: 29 DSP features + logistic regression (`voice_dsp`)
* `tools/voice_features.py` (Python) and `common/voice_features.cpp` (C++, identical results, checked by
  `tools/check_features.py`): band energies, spectral centroid, zero-crossing rate, crest factor, loudness above floor,
  and the same measures for the **start / middle / end third** of the word (the thirds separate "on" from "off" and "blue"
  from "green": +6 points over whole-word averages).
* `tools/train_export.py` trains z-score + logistic regression on all clips and writes `apps/voice_dsp/model_params.h`
  (a few hundred bytes of weights).
* Word cutting on the board: onset when frame RMS > 300 for 2 frames, end after 4 quiet frames (64 ms).
* Honest accuracy: ~91 % (blocks of 10 consecutive recordings held out). Random-clip splits give ~96 %, which is too
  optimistic because neighbouring clips are near-duplicates.
* `notebooks/train_classifier.ipynb` compares scalers (z-score, robust, min-max, quantile ...), checks outliers and
  correlated features, and runs drop-one / permutation importance. Findings: scaling matters (min-max and no scaling are
  clearly worse), most features help a little, no single feature is dispensable alone because the four band shares sum to ~1.

### Step 4 - Test on the real board, and find what breaks
* `pixi run live` prompts words/sentences, the board streams back each captured word, and the tool scores it and saves the
  windows to `dataset_live/` (filler words become class `other`).
* Result on sentences: the loudness-based cutter produced the right number of words in only ~40 % of prompts.
* `pixi run raw` records the board's **continuous** audio while you read prompts on a timer (no key presses), so tuning can
  continue offline. Analysis of that recording showed the hard limit: **quiet gaps inside single words are as long as the
  gaps between words in a sentence** (single words: 4-24 frames, 40 % of single-word prompts contain at least one gap of
  4+ frames; sentences: mostly 4-9 frames), so no loudness threshold can cut sentences correctly. (Small sample: 10
  single-word prompts; see `notebooks/sentence_cnn.ipynb`.)

### Step 5 - Sentences need a different approach (all numbers: 74 real prompts, exact keyword sequence)

| Approach | Exact | Keyword error |
|---|---|---|
| `voice_dsp` energy cutter + 29 features | 16 % | 65 % |
| Sliding windows, same hand-made features | 8 % | - |
| A second CNN that finds word boundaries, then the old model | 26-32 % | 48-56 % |
| scikit-learn MLP on log-mel, synthetic sentences only | 46-50 % | 35-43 % |
| 1D CNN, synthetic sentences only | 42-47 % | 33-40 % |
| **1D CNN, synthetic pre-training + fine-tuned on real sentences** | **81-84 %** | **9-11 %** |

How the winning model is trained (`tools/train_cnn.py`, `pixi run train-cnn`, ~10 min):
1. **Synthetic sentences**: isolated word recordings stitched together with random gaps, volumes and filler words, so the
   word positions are known exactly (`tools/kws.py`). Pre-train on windows cut from them.
2. **Real sentences have no word-time labels**, so they are found automatically: align the model's own window
   probabilities to the keywords of each prompt, in order (dynamic programming), then fine-tune on windows around those
   positions (keyword) and far from them (background).
3. Held-out check: hold out whole **prompt texts** (not random clips), so the test sentences have wording the model never
   saw. This gave the same result as random holding out, so it is not just memorising sentences.
4. Export: BatchNorm folded into the convolutions, weights written to `common/cnn_params.h`.

Model: log-mel 32 bands x 42 frames (0.67 s) -> 4 x Conv1d (32, 48, 64, 64 channels, kernel 3) -> mean+max over time ->
5 classes (background, blue, green, off, on). 30 k weights, ~460 k multiply-adds per decision.

### Step 6 - Put the CNN on the board (`voice_cnn`)
* `common/kws_cnn.cpp`: log-mel (FFT + mel filters), the CNN in plain float C++, and the streaming decoder (a keyword
  peak above 0.5 is confirmed after 3 windows with no higher peak). Plain C++ so it also compiles on the Mac.
* **`pixi run python tools/check_cnn.py`** compiles that same C++ on the PC and compares it with PyTorch on real
  recordings: max probability difference 4e-6, identical decoder events.
* `apps/voice_cnn/main.cpp`: audio task (mic -> log-mel row per 16 ms), CNN task (every 4 frames = 64 ms), and the
  **command logic**: a colour word selects the LED, "on/off" is the action, either order within ~2.5 s, other words ignored.
  A lone "on"/"off" acts on the last LED used (green at start). Serial prints `EV <word> <prob>` and `CMD <LED> <on|off>`.
* `pixi run cnn-test` reads prompts and scores the board **by aligning the whole keyword stream with the whole prompt
  stream** (edit distance), so speaking slightly early or late does not matter. An earlier timer-based version of the
  scoring mis-assigned events and showed 8 % while the real result was 90 %.

## 5. Reproduce everything, in order

```
# data (board running apps/audio_capture:  make APP=audio_capture flash)
pixi run tui                               # record words + noise into dataset/

# isolated-word firmware
pixi run train-export --classes noise off on     # or all classes; writes apps/voice_dsp/model_params.h
pixi run python tools/check_features.py          # C++ features == Python features
make APP=voice_dsp flash

# collect continuous speech (board running voice_dsp, which has the raw/stream modes)
pixi run live                              # optional: word windows labelled by prompts
pixi run raw --minutes 5                   # continuous audio + prompt timeline -> dataset_raw/

# sentence firmware
pixi run train-cnn                         # add --cv for held-out accuracy
pixi run python tools/check_cnn.py         # C++ == PyTorch
make APP=voice_cnn flash
pixi run cnn-test --minutes 4              # live score
```

| Tool | Purpose |
|---|---|
| `tools/dataset_tui.py`, `dataset_cli.py` | record / manage the word dataset |
| `tools/voice_features.py` | the 29 DSP features, board-style windowing, dataset loader |
| `tools/train_export.py` | train + export the DSP model |
| `tools/live_session.py`, `raw_session.py` | prompted capture from the real board (words / continuous) |
| `tools/kws.py`, `train_cnn.py` | log-mel, synthetic sentences, CNN, training + export |
| `tools/cnn_session.py` | live scoring of `voice_cnn` |
| `tools/check_features.py`, `check_cnn.py`, `host_test/` | C++-vs-Python parity tests |

Serial commands understood by `voice_dsp` (for the tools): `S` stream captured words, `R` stream raw audio, `G` force a
capture, `T` back to text.

## 6. Limitations - read before trusting the numbers

* **One speaker, one microphone, one room.** All recordings are one person's voice. Another voice will score lower; this has
  not been measured. The most valuable next test is a second person saying the prompts.
* The CNN was fine-tuned on **74 real sentences** from one 5-minute session; the same filler words (switch, turn, please,
  led, light, the) appear in training and test. Unseen filler words are untested.
* The headline 90 % / 93 % comes from one 36-prompt live session; treat it as "works well for its owner", not a benchmark.
* The CNN's real run time on the chip has not been recorded here (estimated 15-20 ms per decision; the firmware prints the
  measured value every 2 s as `cnn ... ms`).
* Detection is not instant: a keyword is reported ~0.3 s after it is spoken.
* A keyword said within ~190 ms of a stronger one can be dropped by the decoder (suspected cause of some misses; untested fix:
  allow a colour and an on/off word to overlap).
* `voice_tflm` and `voice_edge_impulse` are empty stubs. The hand-built CNN made them less urgent, but the three-way
  comparison originally planned has not been done.

## 7. Ideas not yet tried (each can be scored with the held-out-text protocol)

Delta features and level-invariant normalisation; window length / mel-band count; more realistic synthetic sentences
(overlapping, speed- and pitch-varied words); decoder threshold / hold / smoothing and per-word thresholds; word-order
hints; int8 quantisation (CMSIS-NN); more speakers.
