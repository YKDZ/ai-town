# AI 小镇

在 AI 小镇的模拟系统中，每个居民都按照一个持续的行为循环运作。这个循环由大语言模型（LLM）驱动，使得每个居民能够根据其个性、记忆、时间和环境做出独立的决策。

通过命令启动项目，其打开一个 GUI 界面，显示一个 2D 的模拟小镇地图，小镇上住着几位 AI 居民，居民们的人物设定见 [人物设定](data/characters.json)。

小镇地图由中心广场、酒馆、图书馆和每户居民的家组成。

小镇地图有白天与黑夜轮转机制。每到黑夜，居民们就会在自己决定的时间回到自己的住所、上床睡觉；早上则会自己决定今天的日程。

故事的“主角”是 [格斯](data/characters.json)。他想要在三天后在小镇的中心广场举办一场联谊活动，并且想要让小镇的每个人都来参加。他在这三天内将会冲这这个目标规划自己的行为并努力实现它。

此项目意图在 GUI 中展示这三天内，小镇上每个居民的行为、他们间的交流过程以及最终一起联合达成目的的过程。

## 本地运行

1. 按照 [.env.example](.env.example) 创建一个 `.env` 文件
2. 安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)
3. `uv venv`
4. `uv sync`
5. `uv run main.py`
6. `uv run main.py --replay logs/simulation_log_xxx_xxx.json`