"""Estado de sesión compartido por todas las secciones."""

from __future__ import annotations

import streamlit as st

from src.models.experiment import Experiment
from src.utils.validation import ValidationError, clamp_roi

DEFAULTS = {
    "experiments": {},
    "active_id": None,
    "frame_index": 0,
    "playing": False,
    "playback_delay_s": 0.8,
    "roi_x": 50,
    "roi_y": 35,
    "roi_w": 60,
    "roi_h": 50,
    "palette": "Inferno",
    "baseline_frames": 1,
}


def init_state() -> None:
    for key, value in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value if not isinstance(value, dict) else {}


def experiments() -> dict[str, Experiment]:
    return st.session_state.experiments


def active_experiment() -> Experiment | None:
    return experiments().get(st.session_state.active_id)


def activate(experiment: Experiment, start_playback: bool = False) -> None:
    experiments()[experiment.id] = experiment
    st.session_state.active_id = experiment.id
    st.session_state.frame_index = 0
    st.session_state.playing = bool(start_playback and experiment.has_time_series)
    st.session_state.pop("instante", None)
    st.session_state.pop("_playback_tick", None)
    _fit_roi(experiment)


def _fit_roi(experiment: Experiment) -> None:
    frames = experiment.numeric_frames
    if not frames:
        return
    height, width = frames[0].matrix.shape  # type: ignore[union-attr]
    try:
        x, y, roi_w, roi_h = clamp_roi(
            int(st.session_state.roi_x),
            int(st.session_state.roi_y),
            int(st.session_state.roi_w),
            int(st.session_state.roi_h),
            int(height),
            int(width),
        )
    except ValidationError:
        return
    st.session_state.roi_x = x
    st.session_state.roi_y = y
    st.session_state.roi_w = roi_w
    st.session_state.roi_h = roi_h
    for key, value in (("roi_x_input", x), ("roi_y_input", y), ("roi_w_input", roi_w), ("roi_h_input", roi_h)):
        if key in st.session_state:
            st.session_state[key] = value
