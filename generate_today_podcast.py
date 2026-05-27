import asyncio
from pathlib import Path

import edge_tts


SCRIPT = """你好，这里是 Earth Signal 的今日 1 分钟新闻播客。

今天关注的是城市能源管理。随着电动车、分布式光伏和极端天气同时增加，传统电网面对的波动越来越细，也越来越快。

一些欧洲城市正在测试 AI 调度系统，把天气预测、建筑用电、充电桩负载和电价信号放在一起分析，再给出削峰填谷建议。它不只是让某栋楼少用一点电，而是让整个街区在关键时段更平稳。

这件事重要，是因为未来的低碳城市不只靠更多清洁能源，也靠更聪明的分配方式。当能源被更精确地使用，居民账单、城市韧性和减排目标都会同时受益。

今天的信号是：更安静的电网背后，可能藏着更聪明的城市。"""


async def main() -> None:
    output_dir = Path(__file__).resolve().parent / "audio"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "today-podcast.mp3"
    communicate = edge_tts.Communicate(SCRIPT, voice="zh-CN-XiaoxiaoNeural", rate="+0%")
    await communicate.save(str(output_file))
    print(f"Generated {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
