import os
import tempfile
import unittest
from pathlib import Path

from folder_compare import compare_folders


class CompareFoldersTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.first = self.root / "first"
        self.second = self.root / "second"
        self.first.mkdir()
        self.second.mkdir()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_reports_missing_and_extra_files_and_empty_folders(self):
        (self.first / "left.txt").write_text("left", encoding="utf-8")
        (self.second / "right.txt").write_text("right", encoding="utf-8")
        (self.first / "empty").mkdir()

        differences, matching_files = compare_folders(self.first, self.second)

        self.assertEqual(matching_files, 0)
        self.assertEqual(
            {(item.path, item.status) for item in differences},
            {
                ("left.txt", "Only in Folder 1"),
                ("right.txt", "Only in Folder 2"),
                ("empty", "Only in Folder 1"),
            },
        )

    def test_reports_content_timestamp_and_permissions_differences(self):
        left = self.first / "same.txt"
        right = self.second / "same.txt"
        left.write_text("different contents", encoding="utf-8")
        right.write_text("other contents", encoding="utf-8")
        os.chmod(left, 0o666)
        os.chmod(right, 0o444)
        os.utime(left, ns=(1_000_000_000, 1_000_000_000))
        os.utime(right, ns=(2_000_000_000, 2_000_000_000))

        differences, matching_files = compare_folders(self.first, self.second)

        self.assertEqual(matching_files, 0)
        self.assertEqual(
            {item.status for item in differences},
            {"Contents differ", "Modified time differs", "Permissions differ"},
        )

    def test_counts_identical_contents_and_reports_case_difference(self):
        (self.first / "Name.txt").write_text("same", encoding="utf-8")
        (self.second / "name.txt").write_text("same", encoding="utf-8")
        timestamp = 1_000_000_000
        os.utime(self.first / "Name.txt", ns=(timestamp, timestamp))
        os.utime(self.second / "name.txt", ns=(timestamp, timestamp))

        differences, matching_files = compare_folders(self.first, self.second)

        self.assertEqual(matching_files, 1)
        self.assertEqual([item.status for item in differences], ["Name/case differs"])

    def test_reports_symbolic_link_target_difference(self):
        try:
            (self.first / "shortcut").symlink_to("first-target")
            (self.second / "shortcut").symlink_to("second-target")
        except (NotImplementedError, OSError):
            self.skipTest("Symbolic links are unavailable")

        differences, _ = compare_folders(self.first, self.second)

        self.assertEqual([item.status for item in differences], ["Link target differs"])

    def test_raises_for_missing_folder(self):
        with self.assertRaises(FileNotFoundError):
            compare_folders(self.first, self.root / "missing")


if __name__ == "__main__":
    unittest.main()
