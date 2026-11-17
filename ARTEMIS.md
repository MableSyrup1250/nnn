# Artemis footswitch controls

This branch supports the Artemis FS1–FS5 terminal sequences directly, including
on the Linux console (`TERM=linux`). Normal nnn keyboard bindings still work.

| Switch | Action |
| --- | --- |
| FS1 | Previous entry |
| FS2 | Next entry |
| FS3 | Parent directory; cancel any open action/confirmation |
| FS4 | Enter highlighted directory, or accept the displayed action |
| FS5 | Cycle actions for the highlighted entry |

FS5 cycles **Open in nano → Select for move → Delete → Quit → Back to browsing**.
Moving the cursor or changing directories closes the action menu. The two bottom
rows show the controls and current action. Directory refreshes also close the
menu so a changed listing cannot silently retarget an operation.

To move a file or folder, choose **Select for move** and accept with FS4. Browse
normally with FS1–FS4. In the destination directory, press FS5 to choose **Move
here** and FS4 to accept. The destination is the directory currently displayed,
including an empty directory. While moving, FS5 also offers **Cancel move**,
**Quit**, and **Back to browsing**. Existing destination entries are never
replaced. A failed move keeps the source selected so you can retry or cancel.

**Delete** removes the highlighted file or folder (including its contents)
permanently. After accepting Delete, press FS4 again to confirm, or FS5/FS3 to
cancel. Moving the cursor also cancels confirmation. Operations act on the
entry selected when the menu opened, and reject a missing/replaced entry.

**Open in nano** accepts regular text files, including empty files, and rejects
likely binary files using nnn's text detection. Nano itself requires a keyboard
or the Artemis onscreen keyboard to edit, save, and exit (Ctrl+X). FS4 without an
open action enters folders; use the nano action to open a text file.

Appman builds the pinned checkout and installs `/usr/local/bin/artemis-nnn`;
it installs nano and the ncurses build dependencies too. Both Appman's Files
entry and the Artemis Files shortcut launch this build. Install or update Files
to pick up the changes. The system's `nnn` package is independent.

Build and test on Linux:

```sh
make
python3 -m unittest discover -s tests -v
```

The tests use pseudo-terminals and the real footswitch escape sequences. A stub
nano verifies the file argument without opening an interactive editor. Filesystem
operations use argument arrays, not shell commands, and GNU `mv -nT` for moves
(including across filesystems); GNU coreutils is provided by Raspberry Pi OS.
