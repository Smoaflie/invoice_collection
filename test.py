import time
import subprocess
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
import psutil


class ChangeHandler(FileSystemEventHandler):
    def __init__(self, command):
        self.command = command.split() if isinstance(command, str) else command
        self.process = None
        self.start_process()

    def _kill_process_tree(self):
        """彻底终止进程树"""
        if self.process is None:
            return

        try:
            parent = psutil.Process(self.process.pid)
            children = parent.children(recursive=True)
            for child in children:
                child.kill()
            parent.kill()
        except psutil.NoSuchProcess:
            pass
        self.process = None

    def start_process(self):
        self._kill_process_tree()  # 先终止旧进程树
        self.process = subprocess.Popen(
            self.command,
            shell=False,  # 禁用shell以直接启动进程
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,  # Windows需要
        )

    def on_any_event(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(".py"):
            self.start_process()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    command = sys.argv[2] if len(sys.argv) > 2 else "python gui.py"
    event_handler = ChangeHandler(command)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
