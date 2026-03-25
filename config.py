# config.py
GATEWAY_PORT = 18789             # openclaw gateway WebSocket+HTTP 端口（旧版 bridge TCP 18790 已废弃）
MONITOR_INTERVAL = 300       # 监控检查间隔（秒）
STARTUP_TIMEOUT = 90         # 单次启动等待超时（秒）；gateway 需要连接远程服务，冷启动可能超过 30s
MAX_RETRY_COUNT = 3          # 最大启动/重启尝试次数（含首次）
CHECK_INTERVAL = 2           # 启动/重启等待时的检测间隔（秒）
STOP_WAIT = 5                # 执行stop命令后等待时间（秒）；等端口释放
SOCKET_TIMEOUT = 2           # 端口连接超时（秒）
AUTOSTART_KEY = "LaomaClawWatchdog"
GATEWAY_PROCESS_NAME = "node"              # 进程名（openclaw gateway 以 node 进程运行）
GATEWAY_PROCESS_CMDLINE = "openclaw"       # cmdline 关键词，用于精确定位正确的 node 进程
GATEWAY_START_CMD = "openclaw gateway"     # 启动命令
GATEWAY_STOP_CMD = "openclaw gateway stop"
APP_NAME = "老马OpenClaw小龙虾看门狗"
APP_VERSION = "1.0.0"
