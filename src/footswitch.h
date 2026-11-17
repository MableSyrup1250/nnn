/* Artemis footswitch workflow. Included after nnn's browser helpers.
 * SPDX-License-Identifier: BSD-2-Clause
 */

static bool fs_same_entry(const char *path, const struct stat *saved)
{
	struct stat current;

	return lstat(path, &current) == 0 && current.st_dev == saved->st_dev
		&& current.st_ino == saved->st_ino;
}

static void fs_cycle(const char *path)
{
	if (fs_delete_confirm) {
		fs_delete_confirm = FALSE;
		fs_action = FS_BROWSE;
		return;
	}

	/* Pin the entry on opening the menu, never whichever row later replaces it. */
	if (fs_action == FS_BROWSE) {
		fs_target[0] = '\0';
		if (ndents) {
			mkpath(path, pdents[cur].name, fs_target);
			if (lstat(fs_target, &fs_target_stat) == -1)
				fs_target[0] = '\0';
		}
	}

	static const enum fs_action normal[] = { FS_NANO, FS_MOVE, FS_DELETE, FS_QUIT, FS_CANCEL };
	static const enum fs_action moving[] = { FS_HERE, FS_CANCEL_MOVE, FS_QUIT, FS_CANCEL };
	const enum fs_action *actions = fs_source[0] ? moving : normal;
	size_t count = fs_source[0] ? ELEMENTS(moving) : ELEMENTS(normal), index = 0;

	for (size_t i = 0; i < count; ++i)
		if (actions[i] == fs_action) {
			index = (i + 1) % count;
			break;
		}
	/* Empty directories still offer Quit and Back. */
	while (!fs_target[0] && (actions[index] == FS_NANO || actions[index] == FS_MOVE
				|| actions[index] == FS_DELETE))
		index = (index + 1) % count;
	fs_action = actions[index];
}

/* No shell interpolation or keyboard prompts, including for unusual filenames. */
static int fs_run(char *const argv[], bool interactive)
{
	if (interactive)
		exitcurses();

	pid_t pid = fork();
	int status = -1;

	if (pid == 0) {
		enable_signals();
		if (!interactive) {
			dup2(devnullfd, STDOUT_FILENO);
			dup2(devnullfd, STDERR_FILENO);
		}
		execvp(argv[0], argv);
		_exit(127);
	}
	if (pid > 0) {
		pid_t result;

		do {
			result = waitpid(pid, &status, 0);
		} while (result == -1 && errno == EINTR);
		if (result == -1)
			status = -1;
	}
	if (interactive)
		refresh();
	return status != -1 && WIFEXITED(status) ? WEXITSTATUS(status) : -1;
}

/* Return: -1 message, 0 menu, 1 reload, 2 quit, 3 navigate. */
static int fs_accept(char *path)
{
	enum fs_action action = fs_action;
	struct stat sb;
	char destination[PATH_MAX];
	int result;

	if (action == FS_BROWSE)
		return 3;
	if (action == FS_QUIT)
		return 2;
	if (action == FS_CANCEL || action == FS_CANCEL_MOVE) {
		if (action == FS_CANCEL_MOVE)
			fs_source[0] = '\0';
		fs_action = FS_BROWSE;
		return 0;
	}
	if (action == FS_HERE) {
		fs_action = FS_BROWSE;
		if (!fs_same_entry(fs_source, &fs_source_stat)) {
			printmsg("Move source changed or disappeared; cancel and select again");
			return -1;
		}
		if (strlen(path) + strlen(xbasename(fs_source)) + 2 > sizeof(destination)) {
			printmsg("Destination path is too long");
			return -1;
		}
		mkpath(path, xbasename(fs_source), destination);
		/* lstat also catches dangling symlinks; never replace an existing entry. */
		if (lstat(destination, &sb) == 0 || errno != ENOENT) {
			printmsg("Destination already exists or is inaccessible; choose another folder");
			return -1;
		}
		char *argv[] = { "mv", "-nT", "--", fs_source, destination, NULL };

		result = fs_run(argv, FALSE);
		/* GNU mv -n may report success when it skipped a collision. */
		if (result || lstat(fs_source, &sb) == 0 || errno != ENOENT) {
			printmsg("Move failed; source remains selected (check permissions/destination)");
			return -1;
		}
		fs_source[0] = '\0';
		return 1;
	}

	if (!fs_target[0] || !fs_same_entry(fs_target, &fs_target_stat)) {
		fs_action = FS_BROWSE;
		fs_delete_confirm = FALSE;
		printmsg("Entry changed or disappeared; select it again");
		return -1;
	}
	if (action == FS_DELETE && !fs_delete_confirm) {
		fs_delete_confirm = TRUE;
		return 0;
	}

	fs_action = FS_BROWSE;
	fs_delete_confirm = FALSE;
	if (action == FS_MOVE) {
		xstrsncpy(fs_source, fs_target, sizeof(fs_source));
		fs_source_stat = fs_target_stat;
		return 0;
	}
	if (action == FS_NANO) {
		if (stat(fs_target, &sb) == -1 || !S_ISREG(sb.st_mode)
		    || (sb.st_size && !is_text_file(fs_target))) {
			printmsg("Nano supports readable text files only");
			return -1;
		}
		char *argv[] = { "nano", "--", fs_target, NULL };

		if (fs_run(argv, TRUE)) {
			printmsg("Could not open nano; check it is installed and the file is accessible");
			return -1;
		}
		return 1;
	}
	if (action == FS_DELETE) {
		char *argv[] = { "rm", "-r", "--", fs_target, NULL };

		if (fs_run(argv, FALSE)) {
			printmsg("Delete failed (check file and folder permissions)");
			return -1;
		}
		return 1;
	}
	return 0;
}
