import pathlib
import sys

# backend/ 를 sys.path 에 추가해 `import app...` 가 동작하도록 함
sys.path.insert(0, str(pathlib.Path(__file__).parent))
