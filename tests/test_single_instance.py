from __future__ import annotations

import os
import uuid
import unittest

from he_keyboard_mapper.single_instance import SingleInstance


class SingleInstanceTests(unittest.TestCase):
    def test_second_guard_detects_existing_process_lock(self) -> None:
        if os.name != "nt":
            self.skipTest("The desktop single-instance guard uses a Windows named mutex.")
        name = f"Local\\HallAnalogMapperTest-{uuid.uuid4()}"
        first = SingleInstance(name)
        second = SingleInstance(name)
        try:
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
        finally:
            second.release()
            first.release()


if __name__ == "__main__":
    unittest.main()
