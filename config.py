# config.py
GATEWAY_PORT = 18790
MONITOR_INTERVAL = 300       # 监控检查间隔（秒）
STARTUP_TIMEOUT = 30         # 单次启动等待超时（秒）
MAX_RETRY_COUNT = 3          # 最大启动/重启尝试次数（含首次）
CHECK_INTERVAL = 2           # 启动/重启等待时的检测间隔（秒）
STOP_WAIT = 3                # 执行stop命令后等待时间（秒）
SOCKET_TIMEOUT = 2           # 端口连接超时（秒）
AUTOSTART_KEY = "LaomaClawWatchdog"
GATEWAY_PROCESS_NAME = "openclawgateway"   # 进程名，用于psutil精确匹配
GATEWAY_START_CMD = "openclawgateway"      # 启动命令（与进程名相同，独立定义便于将来传参）
GATEWAY_STOP_CMD = "openclaw gateway stop"
APP_NAME = "老马OpenClaw小龙虾看门狗"
APP_VERSION = "1.0.0"
