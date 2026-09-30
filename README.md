# Folder Compare

A small Windows-friendly Python app for checking whether two folders (including
their subfolders) differ. It does not copy, move, delete, or change files.

## Run

Install Python 3.10 or newer, then open PowerShell in this folder and run:

```powershell
python main.py
```

Choose the two folders and select **Compare folders**. Differences appear in
the table and can be saved as a CSV report.

The comparison includes:

- Files, folders (including empty folders), and relative paths
- File contents, using SHA-256 hashes
- File modified times and permission/read-only bits
- Symbolic-link targets, without following links
- File/folder type and path-name capitalization

Folder modified times are not compared because they change as files are added,
removed, or synchronized. Ownership, ACLs, OneDrive sharing settings, and other
cloud-only metadata are not checked. Comparing file contents reads every file;
OneDrive online-only files may be downloaded or made available locally while
the comparison runs.

If a folder cannot be read, or a file changes while it is being checked, the
app shows an error rather than claiming the folders match.

## Run tests

```powershell
python -m unittest -v
```
