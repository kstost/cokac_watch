import os
import plistlib
import subprocess
import venv
import logging
import stat
from pathlib import Path

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

try:
    # 현재 작업 디렉토리 가져오기
    current_dir = Path.cwd()
    logging.info(f"현재 작업 디렉토리: {current_dir}")

    # 가상 환경 경로 설정 및 생성
    venv_path = current_dir / 'venv'
    if not venv_path.exists():
        logging.info("가상 환경을 생성합니다.")
        venv.create(venv_path, with_pip=True)
        logging.info("가상 환경이 생성되었습니다.")

    # 가상 환경의 pip를 사용하여 필요한 패키지 설치
    pip_path = venv_path / 'bin' / 'pip'
    run_command(f"{pip_path} install -r requirements.txt")

    # Python 스크립트 경로 확인
    python_script = current_dir / 'cokac_watch.py'
    if not python_script.exists():
        raise FileNotFoundError("'cokac_watch.py' 파일을 찾을 수 없습니다.")

    # 사용자 홈 디렉토리
    home_dir = Path.home()

    # plist 파일 내용 수정
    plist_content = {
        'Label': 'com.cokac.folderwatcher',
        'ProgramArguments': [str(venv_path / 'bin' / 'python'), str(python_script)],
        'RunAtLoad': True,
        'KeepAlive': True,
        'WorkingDirectory': str(current_dir),
        'EnvironmentVariables': {'PATH': f"{venv_path}/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"},
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

except Exception as e:
    logging.error(f"설치 중 오류 발생: {str(e)}")
    raise
