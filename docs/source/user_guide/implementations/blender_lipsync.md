# Blender 5.0 lip-sync add-on

MFA includes a Blender 5.0 add-on package in `blender_addons/mfa_lip_sync` for automatic lip-sync baking.

## Install in Blender

1. Install MFA separately (CLI command `mfa` must be available, or use a full executable path).
2. Zip the `mfa_lip_sync` package directory so that the zip root contains `mfa_lip_sync/__init__.py`.
3. In Blender 5.0, open **Edit > Preferences > Add-ons > Install...** and install the zip.
4. Enable **MFA Lip Sync Baker**.

## Panel controls

The panel is available at **View3D > Sidebar > MFA Lip Sync** and includes:

- WAV input path
- Transcript input path (`.txt`/`.lab`)
- MFA command path/name
- Dictionary and acoustic model values for MFA
- Optional output and working directories
- Pose action selector for mouth-shape poses
- Configurable viseme -> pose marker mapping
- Optional `PHONE=VISEME` override text mapping
- **Bake Keys** button

## Pose library workflow

The add-on uses an Action with pose markers as the mouth-shape pose library.

Recommended viseme labels are:

- `rest`/silence
- `AI`
- `E`
- `O`
- `U`
- `FV`
- `MBP`
- `L`
- `WQ`
- `TH`

Create matching pose markers in the Action (or remap names in the UI).

## Baking behavior

When **Bake Keys** is pressed:

1. Input files and rig setup are validated.
2. `mfa align_one` is invoked.
3. The generated TextGrid phone tier is parsed.
4. Phone labels are normalized and mapped to visemes.
5. Phone timing is converted to frames using scene FPS.
6. Pose data is sampled from mapped marker frames and keyed on the selected armature.

## Error handling

The add-on reports user-facing errors for:

- Missing/invalid WAV or transcript files
- Missing active armature
- Missing pose Action or pose markers
- MFA command failures
- Missing or malformed alignment output
- Missing mapped pose markers (reported as warnings)

## Known limitations

- Requires a separate MFA installation and compatible dictionary/acoustic model.
- Phone intervals are currently keyed at start frames.
- Alignment quality depends on transcript, audio quality, and model/dictionary fit.
