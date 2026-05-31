import unittest

from health_reminder.platform.sound import _scale_pcm


class SoundTest(unittest.TestCase):
    def test_scale_pcm_16_bit(self):
        frames = b"\x00@\x00\xc0"
        self.assertEqual(_scale_pcm(frames, 2, 0.5), b"\x00 \x00\xe0")


if __name__ == "__main__":
    unittest.main()
