# Evidence for on-device AI and safe investigation workflows

## Evidence that phone inference is real

- **llama.cpp on Android:** the official Android guide documents CLI builds in Termux without root, lists the required packages, links an older interactive Pixel 5 demo, and warns that an excessive context size can exhaust memory and kill Termux. This is the strongest direct evidence for the architecture used here. https://github.com/ggml-org/llama.cpp/blob/master/docs/android.md
- **Google AI Edge Gallery:** this maintained experimental Google project demonstrates fully offline chat, speech recognition and synthesis, image questions, audio transcription, media search, mobile actions, and on-device benchmarks. It requires Android 12 or newer, so it is evidence for modern phones and **not an install option for the stock Hydrogen One Android 8.1 target**. https://github.com/google-ai-edge/gallery
- **MLC LLM on Android:** the Android guide describes native deployment, physical-phone testing, and mobile GPU execution. Its provided demo targets a Samsung S23 with Snapdragon 8 Gen 2, and it documents an Adreno prefill issue. It does not establish compatibility or performance for the Hydrogen One. https://llm.mlc.ai/docs/deploy/android.html
- **whisper.cpp:** the project lists Android support and offline speech recognition. Its published approximate memory figures are 273 MB for tiny, 388 MB for base, and 852 MB for small models. This supports a future voice module; voice is not implemented in this repository yet. https://github.com/ggml-org/whisper.cpp

## What the evidence does not prove

There is not yet a measured Hydrogen One benchmark for this project. A successful cloud x86 build and API test prove the software integration, not Snapdragon 835 speed, thermal behavior, memory headroom, or Android background stability. The first on-device run must measure model load time, tokens per second, peak memory, battery drain, and temperature during a sustained session.

A smaller local model also cannot reproduce the capability of much larger cloud models. Qwen2.5 1.5B is suitable for basic drafting and first-pass text work, but it can hallucinate, omit nuance, and misunderstand instructions.

## Realistic offline OSINT-adjacent uses

Use the node to analyze material that was lawfully collected before going offline:

1. Produce first-pass summaries of public contracts, audits, meeting records, and technical reports.
2. Draft lists of people, organizations, dates, payment terms, and possible timeline events for manual review.
3. Explain jargon and generate interview questions or leads for human follow-up.
4. Translate or rewrite already collected text, then compare every important passage with the original.
5. Search local notes and tasks for known terms. Current search is deterministic SQL text matching, not semantic retrieval.
6. Add offline transcription later through whisper.cpp, with separate on-device testing.

The Global Investigative Journalism Network describes early investigation triage such as contract summaries, extracting names and payment terms, summarizing public concerns, and explaining technical findings. It explicitly warns that generated output is not evidence or corroboration and should orient reporting rather than go directly into published copy. https://gijn.org/stories/using-chatgpt-quick-search-investigative-tool/

Bellingcat tested 52 previously unpublished photos and found that leading models improved at narrowing regions, with top models placing over half within 25 km. Exact coordinates remained unreliable, confident errors persisted, and independent human verification stayed essential. Those tests used much larger cloud or tool-equipped models; they do not show that this local 1.5B text model can perform geolocation. https://www.bellingcat.com/resources/2026/10/22/can-llms-supercharge-geolocations-our-tests-show-big-improvements-but-humans-remain-key/

## Evidentiary and privacy rules

- Preserve original files, source URLs, collection times, and cryptographic hashes. Treat generated summaries as disposable working notes.
- Verify every name, date, quotation, amount, page reference, coordinate, and claim against original sources.
- Do not represent a generated lead as a verified fact. Do not use generated output as the sole basis for an accusation or high-impact decision.
- Offline inference cannot collect live web pages. Collection requires a separate, lawful online step.
- Local processing reduces cloud exposure but does not replace device security, access control, backups, or sensitive-source handling procedures.

## Current feature boundary

The node currently accepts plain text only. PDF extraction, OCR, source-linked citations, voice, image analysis, automated collection, geolocation, and hardware control are future work, not current capabilities.
