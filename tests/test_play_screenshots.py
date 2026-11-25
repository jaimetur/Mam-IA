"""tools/play_screenshots.py: an image is only rewritten when it really changes (rendering noise is not a change)."""
import sys
from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL")   # Pillow is a dev dependency (pip install -e ".[dev]")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))


def test_noise_is_not_a_change_but_a_new_word_is(tmp_path):
    import io

    from PIL import Image, ImageDraw

    import play_screenshots as ps
    base = Image.new("RGB", (400, 300), (246, 243, 246))
    ImageDraw.Draw(base).text((20, 20), "Hoy", fill=(35, 27, 41))
    noise = base.copy()
    for x in range(0, 400, 7):          # anti-aliasing noise: many pixels, a few levels each
        noise.putpixel((x, 30), tuple(min(255, c + 4) for c in noise.getpixel((x, 30))))
    word = base.copy()
    ImageDraw.Draw(word).rectangle((100, 100, 130, 115), fill=(201, 62, 102))   # a new word: a block of pixels
    assert ps.same_image(base, noise) and not ps.same_image(base, word)
    assert not ps.same_image(base, base.resize((200, 150)))

    path = tmp_path / "01-hoy.png"
    png = lambda im: (lambda b: (im.save(b, format="PNG"), b.getvalue())[1])(io.BytesIO())   # noqa: E731
    assert ps.keep(path, png(base)) and path.exists()
    before = path.stat().st_mtime_ns, path.read_bytes()
    assert ps.keep(path, png(noise)) is False and (path.stat().st_mtime_ns, path.read_bytes()) == before
    assert ps.keep(path, png(word)) is True and path.read_bytes() != before[1]
