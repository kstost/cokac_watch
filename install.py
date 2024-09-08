import os
import plistlib
import subprocess
import venv
import logging
import stat
from pathlib import Path
import sys

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_command(command):
    try:
        result = subprocess.run(command, check=True, shell=True, capture_output=True, text=True)
        logging.info(f"명령어 실행 성공: {command}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        logging.error(f"명령어 실행 실패: {command}")
        logging.error(f"오류: {e}")
        logging.error(f"표준 출력: {e.stdout}")
        logging.error(f"표준 에러: {e.stderr}")
        raise

def create_and_activate_venv():
    venv_dir = os.path.join(os.getcwd(), 'venv')
    venv.create(venv_dir, with_pip=True)
    
    if sys.platform == 'win32':
        python_exe = os.path.join(venv_dir, 'Scripts', 'python.exe')
    else:
        python_exe = os.path.join(venv_dir, 'bin', 'python')
    
    os.environ['VIRTUAL_ENV'] = venv_dir
    os.environ['PATH'] = os.pathsep.join([os.path.dirname(python_exe), os.environ.get('PATH', '')])
    sys.prefix = venv_dir
    sys.executable = python_exe

    return sys.executable

try:
    # 현재 작업 디렉토리 가져오기
    current_dir = Path.cwd()
    logging.info(f"현재 작업 디렉토리: {current_dir}")

    # 가상 환경 생성 및 활성화
    venv_python = create_and_activate_venv()
    venv_python = Path(venv_python)  # venv_python을 Path 객체로 변환

    # pip 업그레이드 및 패키지 설치
    run_command(f"{venv_python} -m pip install --upgrade pip")
    run_command(f"{venv_python} -m pip install -r requirements.txt")

    # Python 스크립트 경로 확인
    python_script = current_dir / 'cokac_watch.py'
    if not python_script.exists():
        raise FileNotFoundError("'cokac_watch.py' 파일을 찾을 수 없습니다.")

    # 사용자 홈 디렉토리
    home_dir = Path.home()

    # plist 파일 내용 수정
    plist_content = {
        'Label': 'com.cokac.folderwatcher',
        'ProgramArguments': [
            '/bin/bash',
            '-c',
            f'source {venv_python.parent.parent}/bin/activate && python {python_script}'
        ],
        'RunAtLoad': True,
        'KeepAlive': True,
        'StandardOutPath': str(home_dir / 'Library/Logs/com.cokac.folderwatcher.log'),
        'StandardErrorPath': str(home_dir / 'Library/Logs/com.cokac.folderwatcher.err')
    }

    # plist 파일 생성 및 권한 설정
    plist_path = home_dir / 'Library/LaunchAgents/com.cokac.folderwatcher.plist'
    with plist_path.open('wb') as f:
        plistlib.dump(plist_content, f)
    # 소유자에게 읽기, 쓰기 권한, 그룹과 다른 사용자에게 읽기 권한 부여
    os.chmod(plist_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
    logging.info(f"plist 파일이 생성되고 권한이 설정되었습니다: {plist_path}")

    # 실행 파일 권한 확인 및 설정
    python_script_path = current_dir / 'cokac_watch.py'
    if python_script_path.exists():
        os.chmod(python_script_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)
        logging.info(f"Python 스크립트 권한이 설정되었습니다: {python_script_path}")
    else:
        logging.warning(f"Python 스크립트를 찾을 수 없습니다: {python_script_path}")

    # LaunchAgent 언로드 시도 (이미 로드되어 있을 경우를 대비)
    try:
        run_command(f"launchctl unload {plist_path}")
    except subprocess.CalledProcessError:
        logging.warning("LaunchAgent 언로드 실패. 이미 언로드되어 있거나 존재하지 않을 수 있습니다.")

    # LaunchAgent 로드
    run_command(f"launchctl load {plist_path}")

    logging.info("LaunchAgent가 로드되었습니다. 시스템을 재시작하거나 로그아웃 후 다시 로그인하면 프로그램이 자동으로 시작됩니다.")

    # 로그 확인 명령어 안내
    log_command = f"tail -f {home_dir}/Library/Logs/com.cokac.folderwatcher.log"
    err_command = f"tail -f {home_dir}/Library/Logs/com.cokac.folderwatcher.err"
    plist_command = f"cat {home_dir}/Library/LaunchAgents/com.cokac.folderwatcher.plist"
    
    logging.info("로그 파일을 확인하려면 다음 명령어를 사용하세요:")
    logging.info(log_command)
    logging.info("에러 로그를 확인하려면 다음 명령어를 사용하세요:")
    logging.info(err_command)
    logging.info("LaunchAgent plist 파일 내용을 확인하려면 다음 명령어를 사용하세요:")
    logging.info(plist_command)

except Exception as e:
    logging.error(f"설치 중 오류 발생: {str(e)}")
    raise

# venv_path 변수 정의
venv_path = Path('venv')
