"""Blender 5.0 add-on for MFA-driven lip sync baking."""

from __future__ import annotations

from pathlib import Path
import subprocess
import typing

from .core import (
    build_align_one_command,
    interval_to_frame_range,
    parse_phone_intervals,
    phone_to_viseme,
)

bl_info = {
    "name": "MFA Lip Sync Baker",
    "author": "Montreal Forced Aligner contributors",
    "version": (0, 1, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > MFA Lip Sync",
    "description": "Bake lip-sync keyframes from Montreal Forced Aligner phone timings",
    "category": "Animation",
}

try:
    import bpy
except ImportError:  # pragma: no cover - only available inside Blender
    bpy = None


if bpy is not None:

    def _parse_custom_mapping(value: str) -> typing.Dict[str, str]:
        mapping: typing.Dict[str, str] = {}
        for raw_line in value.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            phone, viseme = line.split("=", 1)
            mapping[phone.strip()] = viseme.strip()
        return mapping


    def _viseme_pose_mapping(props: "MFA_LipSyncProperties") -> typing.Dict[str, str]:
        return {
            "rest": props.pose_name_rest,
            "AI": props.pose_name_ai,
            "E": props.pose_name_e,
            "O": props.pose_name_o,
            "U": props.pose_name_u,
            "FV": props.pose_name_fv,
            "MBP": props.pose_name_mbp,
            "L": props.pose_name_l,
            "WQ": props.pose_name_wq,
            "TH": props.pose_name_th,
        }


    def _apply_pose_from_action(
        armature_object: bpy.types.Object,
        action: bpy.types.Action,
        source_frame: float,
        target_frame: int,
    ) -> None:
        for fcurve in action.fcurves:
            value = fcurve.evaluate(source_frame)
            try:
                prop = armature_object.path_resolve(fcurve.data_path)
            except (AttributeError, ValueError, KeyError):
                continue
            if hasattr(prop, "__setitem__") and fcurve.array_index >= 0:
                prop[fcurve.array_index] = value
            else:
                continue
            armature_object.keyframe_insert(
                data_path=fcurve.data_path, index=fcurve.array_index, frame=target_frame
            )


    class MFA_LipSyncProperties(bpy.types.PropertyGroup):
        wav_path: bpy.props.StringProperty(
            name="WAV file", subtype="FILE_PATH", description="Path to input WAV file"
        )
        transcript_path: bpy.props.StringProperty(
            name="Transcript",
            subtype="FILE_PATH",
            description="Path to transcript text/lab file",
        )
        mfa_command: bpy.props.StringProperty(
            name="MFA command",
            default="mfa",
            description="Path to MFA executable or command name in PATH",
        )
        dictionary_path: bpy.props.StringProperty(
            name="Dictionary",
            subtype="FILE_PATH",
            description="MFA dictionary model name or path",
        )
        acoustic_model_path: bpy.props.StringProperty(
            name="Acoustic model",
            subtype="FILE_PATH",
            description="MFA acoustic model name or path",
        )
        output_directory: bpy.props.StringProperty(
            name="Output directory",
            subtype="DIR_PATH",
            description="Directory where MFA alignment output TextGrid will be written",
        )
        working_directory: bpy.props.StringProperty(
            name="Working directory",
            subtype="DIR_PATH",
            description="Optional MFA temporary directory",
        )
        pose_action: bpy.props.PointerProperty(
            name="Pose action",
            type=bpy.types.Action,
            description="Action containing mouth-shape pose markers",
        )
        custom_phone_mapping: bpy.props.StringProperty(
            name="Phone overrides",
            description="Optional PHONE=VISEME lines to override defaults",
            default="",
            options={"TEXTEDIT_UPDATE"},
        )
        pose_name_rest: bpy.props.StringProperty(name="rest", default="rest")
        pose_name_ai: bpy.props.StringProperty(name="AI", default="AI")
        pose_name_e: bpy.props.StringProperty(name="E", default="E")
        pose_name_o: bpy.props.StringProperty(name="O", default="O")
        pose_name_u: bpy.props.StringProperty(name="U", default="U")
        pose_name_fv: bpy.props.StringProperty(name="FV", default="FV")
        pose_name_mbp: bpy.props.StringProperty(name="MBP", default="MBP")
        pose_name_l: bpy.props.StringProperty(name="L", default="L")
        pose_name_wq: bpy.props.StringProperty(name="WQ", default="WQ")
        pose_name_th: bpy.props.StringProperty(name="TH", default="TH")
        unknown_viseme: bpy.props.StringProperty(
            name="Unknown fallback",
            default="rest",
            description="Viseme label to use for unknown phones",
        )


    class MFA_OT_BakeLipSync(bpy.types.Operator):
        bl_idname = "mfa_lipsync.bake_keys"
        bl_label = "Bake Keys"
        bl_description = "Run MFA alignment and bake viseme keyframes"

        def execute(self, context: bpy.types.Context):
            props = context.scene.mfa_lipsync
            active_object = context.active_object
            if active_object is None or active_object.type != "ARMATURE":
                self.report({"ERROR"}, "Select an active armature object.")
                return {"CANCELLED"}
            if props.pose_action is None:
                self.report({"ERROR"}, "Select a pose action containing pose markers.")
                return {"CANCELLED"}
            if not props.pose_action.pose_markers:
                self.report({"ERROR"}, "Pose action has no pose markers to sample.")
                return {"CANCELLED"}

            wav_path = Path(bpy.path.abspath(props.wav_path)).expanduser()
            transcript_path = Path(bpy.path.abspath(props.transcript_path)).expanduser()
            if not wav_path.exists() or wav_path.suffix.lower() != ".wav":
                self.report({"ERROR"}, "WAV file path is missing or invalid.")
                return {"CANCELLED"}
            if not transcript_path.exists():
                self.report({"ERROR"}, "Transcript file path is missing or invalid.")
                return {"CANCELLED"}
            if not props.dictionary_path.strip() or not props.acoustic_model_path.strip():
                self.report({"ERROR"}, "Dictionary and acoustic model are required.")
                return {"CANCELLED"}

            output_directory = (
                Path(bpy.path.abspath(props.output_directory)).expanduser()
                if props.output_directory.strip()
                else wav_path.parent
            )
            output_directory.mkdir(parents=True, exist_ok=True)
            textgrid_path = output_directory.joinpath(f"{wav_path.stem}.TextGrid")
            temporary_directory = None
            if props.working_directory.strip():
                temporary_directory = Path(bpy.path.abspath(props.working_directory)).expanduser()
                temporary_directory.mkdir(parents=True, exist_ok=True)

            command = build_align_one_command(
                mfa_command=props.mfa_command.strip() or "mfa",
                wav_path=wav_path,
                transcript_path=transcript_path,
                dictionary_path=props.dictionary_path,
                acoustic_model_path=props.acoustic_model_path,
                output_path=textgrid_path,
                temporary_directory=temporary_directory,
            )

            self.report({"INFO"}, "Running MFA alignment...")
            try:
                result = subprocess.run(command, text=True, capture_output=True)
            except OSError as exc:
                self.report({"ERROR"}, f"Could not execute MFA command: {exc}")
                return {"CANCELLED"}
            if result.returncode != 0:
                message = result.stderr.strip() or result.stdout.strip() or "Unknown MFA failure"
                self.report({"ERROR"}, f"MFA failed: {message[:400]}")
                return {"CANCELLED"}
            if not textgrid_path.exists():
                self.report({"ERROR"}, f"Expected alignment output was not found: {textgrid_path}")
                return {"CANCELLED"}

            try:
                intervals = parse_phone_intervals(textgrid_path)
            except (OSError, ValueError) as exc:
                self.report({"ERROR"}, f"Could not parse alignment output: {exc}")
                return {"CANCELLED"}

            marker_frames = {marker.name: marker.frame for marker in props.pose_action.pose_markers}
            viseme_to_pose = _viseme_pose_mapping(props)
            custom_mapping = _parse_custom_mapping(props.custom_phone_mapping)
            fps = context.scene.render.fps / max(context.scene.render.fps_base, 1e-6)
            frame_start = context.scene.frame_start
            missing_markers = set()

            for interval in intervals:
                viseme = phone_to_viseme(
                    interval.label,
                    phone_to_viseme_mapping=custom_mapping,
                    unknown_viseme=props.unknown_viseme,
                )
                pose_marker_name = viseme_to_pose.get(viseme, viseme)
                source_frame = marker_frames.get(pose_marker_name)
                if source_frame is None:
                    missing_markers.add(pose_marker_name)
                    continue
                target_frame, _ = interval_to_frame_range(
                    interval.start,
                    interval.end,
                    fps=fps,
                    frame_start=frame_start,
                )
                _apply_pose_from_action(
                    armature_object=active_object,
                    action=props.pose_action,
                    source_frame=source_frame,
                    target_frame=target_frame,
                )

            if missing_markers:
                missing = ", ".join(sorted(missing_markers))
                self.report({"WARNING"}, f"Baked with missing pose markers: {missing}")
            else:
                self.report({"INFO"}, "Lip sync keyframes baked successfully.")
            return {"FINISHED"}


    class MFA_PT_LipSyncPanel(bpy.types.Panel):
        bl_label = "MFA Lip Sync"
        bl_idname = "MFA_PT_LIP_SYNC"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "MFA Lip Sync"

        def draw(self, context: bpy.types.Context):
            layout = self.layout
            props = context.scene.mfa_lipsync
            layout.prop(props, "wav_path")
            layout.prop(props, "transcript_path")
            layout.separator()
            layout.prop(props, "mfa_command")
            layout.prop(props, "dictionary_path")
            layout.prop(props, "acoustic_model_path")
            layout.prop(props, "output_directory")
            layout.prop(props, "working_directory")
            layout.separator()
            layout.prop(props, "pose_action")
            mapping_box = layout.box()
            mapping_box.label(text="Viseme -> pose marker")
            mapping_box.prop(props, "pose_name_rest")
            mapping_box.prop(props, "pose_name_ai")
            mapping_box.prop(props, "pose_name_e")
            mapping_box.prop(props, "pose_name_o")
            mapping_box.prop(props, "pose_name_u")
            mapping_box.prop(props, "pose_name_fv")
            mapping_box.prop(props, "pose_name_mbp")
            mapping_box.prop(props, "pose_name_l")
            mapping_box.prop(props, "pose_name_wq")
            mapping_box.prop(props, "pose_name_th")
            mapping_box.prop(props, "unknown_viseme")
            layout.prop(props, "custom_phone_mapping")
            layout.operator(MFA_OT_BakeLipSync.bl_idname, icon="REC")


    CLASSES = (MFA_LipSyncProperties, MFA_OT_BakeLipSync, MFA_PT_LipSyncPanel)


    def register() -> None:
        for cls in CLASSES:
            bpy.utils.register_class(cls)
        bpy.types.Scene.mfa_lipsync = bpy.props.PointerProperty(type=MFA_LipSyncProperties)


    def unregister() -> None:
        del bpy.types.Scene.mfa_lipsync
        for cls in reversed(CLASSES):
            bpy.utils.unregister_class(cls)


else:

    def register() -> None:  # pragma: no cover
        raise RuntimeError("The MFA Lip Sync add-on can only be registered inside Blender.")


    def unregister() -> None:  # pragma: no cover
        return None
