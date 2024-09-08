import os
import json
import threading
import logging
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import unicodedata

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', stream=sys.stdout)

class ConfigHandler(FileSystemEventHandler):
    def __init__(self, config_path, callback):
        self.config_path = config_path
        self.callback = callback

    def on_modified(self, event):
        if event.src_path == self.config_path:
            logging.info("config.json이 변경되었습니다. 설정을 다시 로드합니다.")
            self.callback()

class MyHandler(FileSystemEventHandler):
    def __init__(self, root_path):
        self.root_path = os.path.abspath(root_path)
        self.renamed_folders = {}

    def normalize_name(self, path):
        abs_path = os.path.abspath(path)
        if abs_path == self.root_path:
            return path

        dir_name, name = os.path.split(abs_path)
        
        # NFC로 정규화
        normalized_name = unicodedata.normalize('NFC', name)
        new_path = os.path.join(dir_name, normalized_name)

        try:
            if os.path.exists(abs_path) and new_path != abs_path:
                os.rename(abs_path, new_path)
                print(f"이름 정규화: {abs_path} -> {new_path}")
                return new_path
            return path
        except Exception as e:
            print(f"이름 변경 중 오류 발생: {e}")
            return path

    def is_normalization_needed(self, name):
        return unicodedata.normalize('NFC', name) != name

    def on_any_event(self, event):
        if event.event_type in ['created', 'modified', 'moved']:
            if event.event_type == 'moved':
                path = event.dest_path
            else:
                path = event.src_path

            if self.is_normalization_needed(path):
                normalized_path = self.normalize_name(path)
                print(f"정규화 필요: {path} -> {normalized_path}")
            else:
                print(f"정규화 불필요: {path}")

    def on_created(self, event):
        new_path = self.normalize_name(event.src_path)
        if event.is_directory:
            print(f"폴더가 생성됨: {new_path}")
        else:
            print(f"파일이 생성됨: {new_path}")

    def on_deleted(self, event):
        if event.is_directory:
            print(f"폴더 삭제됨: {event.src_path}")
        else:
            print(f"파일이 삭제됨: {event.src_path}")

    def on_modified(self, event):
        new_path = self.normalize_name(event.src_path)
        if event.is_directory:
            print(f"폴더가 수정됨: {new_path}")
        else:
            print(f"파일이 수정됨: {new_path}")

    def on_moved(self, event):
        try:
            new_src_path = self.get_actual_path(event.src_path)
            new_dest_path = self.get_actual_path(event.dest_path)

            if self.is_normalization_needed(new_dest_path):
                new_dest_path = self.normalize_name(new_dest_path)

            if event.is_directory:
                print(f"폴더가 {new_src_path}에서 {new_dest_path}(으)로 이동됨")
                self.renamed_folders[event.src_path] = new_dest_path
            else:
                print(f"파일이 {new_src_path}에서 {new_dest_path}(으)로 이동됨")
        except Exception as e:
            print(f"이동 이벤트 처리 중 오류 발생: {e}")

    def get_actual_path(self, path):
        actual_path = path
        for old_path, new_path in self.renamed_folders.items():
            if actual_path.startswith(old_path):
                actual_path = actual_path.replace(old_path, new_path, 1)
        return actual_path

    def process_existing_files(self, path):
        for root, dirs, files in os.walk(path):
            for name in dirs + files:
                full_path = os.path.join(root, name)
                if self.is_normalization_needed(full_path):
                    self.normalize_name(full_path)

def load_config():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'config.json')
    with open(config_path, 'r') as config_file:
        return json.load(config_file)

class FolderWatcher:
    def __init__(self):
        self.observers = {}
        self.config = load_config()
        self.lock = threading.Lock()
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
        self.config_observer = None
        self.restart_event = threading.Event()

    def start(self):
        self.watch_folders()
        self.watch_config()
        
        while True:
            if self.restart_event.wait(1):  # 1초마다 재시작 이벤트 확인
                self.restart_event.clear()
                self._restart()
            
    def reload_config(self):
        with self.lock:
            new_config = load_config()
            if new_config != self.config:
                logging.info("새로운 설정을 감지했습니다. 모든 로직을 재시작합니다.")
                self.restart_event.set()  # 재시작 이벤트 설정
            else:
                logging.info("설정에 변화가 없습니다.")

    def _restart(self):
        self.stop()
        self.__init__()
        self.watch_folders()
        self.watch_config()

    def stop(self):
        for observer in self.observers.values():
            observer.stop()
        for observer in self.observers.values():
            observer.join()
        if self.config_observer:
            self.config_observer.stop()
            self.config_observer.join()
        self.observers.clear()
        logging.info("모든 감시를 중지했습니다.")

    def watch_folders(self):
        with self.lock:
            for folder in self.config['watch_folders']:
                self.start_watching_folder(folder)

    def start_watching_folder(self, folder):
        if not os.path.exists(folder):
            logging.warning(f"폴더가 존재하지 않습니다: {folder}")
            return

        event_handler = MyHandler(folder)
        logging.info(f"{folder} 폴더의 기존 파일 및 폴더 처리 중...")
        event_handler.process_existing_files(folder)
        logging.info(f"{folder} 폴더의 기존 파일 및 폴더 처리 완료")

        observer = Observer()
        observer.schedule(event_handler, folder, recursive=True)
        observer.start()
        self.observers[folder] = observer
        logging.info(f"{folder} 폴더 감시 시작")

    def stop_watching_folder(self, folder):
        if folder in self.observers:
            self.observers[folder].stop()
            self.observers[folder].join()
            del self.observers[folder]
            logging.info(f"{folder} 폴더 감시 중지")

    def watch_config(self):
        config_handler = ConfigHandler(self.config_path, self.reload_config)
        self.config_observer = Observer()
        self.config_observer.schedule(config_handler, os.path.dirname(self.config_path), recursive=False)
        self.config_observer.start()
        logging.info("config.json 파일 감시 시작")

    def stop(self):
        for observer in self.observers.values():
            observer.stop()
        for observer in self.observers.values():
            observer.join()
        if self.config_observer:
            self.config_observer.stop()
            self.config_observer.join()
        self.observers.clear()
        logging.info("모든 감시를 중지했습니다.")

if __name__ == "__main__":
    watcher = FolderWatcher()
    try:
        watcher.start()
    except KeyboardInterrupt:
        watcher.stop()
