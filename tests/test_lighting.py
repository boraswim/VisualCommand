import numpy as np

from visualcommand import lighting


def _img(lo, hi, noise=6, seed=0):
    """A scene-like frame: a diagonal brightness gradient from lo to hi, plus sensor noise."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:240, 0:320]
    base = lo + (hi - lo) * (xx / 319 + yy / 239) / 2
    img = np.clip(base[..., None] + rng.normal(0, noise, (240, 320, 3)), 0, 255)
    return img.astype(np.uint8)


def test_dark_frame_is_low():
    assert lighting.analyze(_img(5, 60)) == lighting.LOW


def test_normal_frame_is_good():
    assert lighting.analyze(_img(30, 230)) == lighting.GOOD


def test_backlit_frame():
    img = np.full((240, 320, 3), 250, np.uint8)      # bright window everywhere...
    img[60:180, 80:240] = 40                          # ...dark person in the middle
    assert lighting.analyze(img) == lighting.BACKLIT


def test_flat_frame():
    assert lighting.analyze(_img(120, 145)) == lighting.FLAT


def test_enhancer_brightens_dark_frame():
    dark = _img(5, 60)
    out = lighting.Enhancer().apply(dark, lighting.LOW, "auto")
    assert out.mean() > dark.mean() + 30
    assert out.shape == dark.shape and out.dtype == np.uint8


def test_auto_mode_leaves_good_frames_alone():
    img = _img(30, 230)
    assert lighting.Enhancer().apply(img, lighting.GOOD, "auto") is img


def test_off_mode_never_changes_frames():
    img = _img(5, 60)
    assert lighting.Enhancer().apply(img, lighting.LOW, "off") is img
