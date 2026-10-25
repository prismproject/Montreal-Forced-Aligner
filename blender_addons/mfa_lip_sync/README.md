# MFA Lip Sync Blender Add-on (Blender 5.0)

This add-on provides automatic lip-sync baking in Blender 5.0 using Montreal Forced Aligner (MFA).

## Installation

1. Ensure Blender 5.0 and MFA are installed.
2. Package `blender_addons/mfa_lip_sync` as a zip (the zip root must contain `mfa_lip_sync/__init__.py`).
3. In Blender, open **Edit > Preferences > Add-ons > Install...** and select the zip.
4. Enable **MFA Lip Sync Baker**.

## Prerequisites

- `mfa` command available in PATH, or configure the full executable path in the add-on.
- An acoustic model and pronunciation dictionary that match your transcript language.
- A WAV file and matching transcript (`.txt`/`.lab`).

## Pose library setup

Use an Action as a mouth-shape pose library:

1. Create an Action that contains pose keyframes for your rig.
2. Add pose markers in that Action, naming them for the viseme labels used below.
3. Recommended labels: `rest`, `AI`, `E`, `O`, `U`, `FV`, `MBP`, `L`, `WQ`, `TH`.
4. In the panel, map each viseme label to the marker name you use.

## Usage

1. Select the speaking armature.
2. Open **View3D > Sidebar > MFA Lip Sync**.
3. Set WAV file, transcript file, MFA command, dictionary, acoustic model, and optional output/work directories.
4. Select the Action that contains your mouth-shape pose markers.
5. Optionally add `PHONE=VISEME` override lines.
6. Click **Bake Keys**.

The add-on runs `mfa align_one`, reads phone timings from the generated TextGrid, maps phones to visemes, and inserts keyframes at scene FPS timing.

## Notes and limitations

- MFA must be installed separately.
- The add-on currently keys each aligned phone at its start frame.
- Missing pose markers are skipped and reported as warnings.
- Unknown phones fall back to the configured fallback viseme (default: `rest`).
